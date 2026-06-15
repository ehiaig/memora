from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory
from app.services.embedding import EmbeddingProviderError, EmbeddingService


class MemoryServiceError(Exception):
    """Raised when the memory service cannot complete the request."""


class MemoryValidationError(MemoryServiceError):
    """Raised when request data is incomplete or invalid."""


@dataclass(slots=True)
class MemorySearchResult:
    id: UUID
    user_id: str
    project_id: str
    raw_text: str
    importance_score: float
    source: str
    tags: list[str]
    metadata: dict
    access_count: int
    created_at: datetime
    last_accessed_at: datetime | None
    expires_at: datetime | None
    distance: float
    similarity_score: float
    ranking_score: float


@dataclass(slots=True)
class MemoryContextResult:
    context_text: str
    used_chars: int
    truncated_count: int
    results: list[MemorySearchResult]


class MemoryService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._session = session
        self._embedding_service = embedding_service or EmbeddingService()

    async def add_memory(
        self,
        *,
        user_id: str,
        project_id: str,
        text: str,
        metadata: dict,
        source: str,
        tags: list[str],
        importance_score: float | None,
        ttl_days: int | None,
    ) -> Memory:
        if not project_id:
            raise MemoryValidationError("project_id is required")

        try:
            embedding = await self._embedding_service.embed_text(text)
        except EmbeddingProviderError as exc:
            raise MemoryServiceError("Failed to generate memory embedding") from exc

        memory = Memory(
            user_id=user_id,
            project_id=project_id,
            raw_text=text,
            embedding=embedding,
            metadata_=metadata,
            source=source,
            tags=tags,
            importance_score=importance_score if importance_score is not None else self._estimate_importance(text),
            expires_at=self._expires_at(ttl_days),
        )

        self._session.add(memory)

        try:
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryServiceError("Failed to persist memory") from exc

        await self._session.refresh(memory)
        return memory

    async def search_memory(
        self,
        *,
        user_id: str,
        query: str,
        limit: int,
        project_id: str | None = None,
        include_expired: bool = False,
    ) -> list[MemorySearchResult]:
        results = await self._retrieve_ranked_memories(
            user_id=user_id,
            query=query,
            limit=limit,
            project_id=project_id,
            include_expired=include_expired,
        )
        await self._mark_accessed_results(results)
        return results

    async def build_context(
        self,
        *,
        user_id: str,
        query: str,
        limit: int,
        max_chars: int,
        project_id: str | None = None,
        include_expired: bool = False,
    ) -> MemoryContextResult:
        results = await self._retrieve_ranked_memories(
            user_id=user_id,
            query=query,
            limit=limit,
            project_id=project_id,
            include_expired=include_expired,
        )

        included_results: list[MemorySearchResult] = []
        lines: list[str] = []
        used_chars = 0
        truncated_count = 0

        for index, result in enumerate(results, start=1):
            tags = ", ".join(result.tags) if result.tags else "none"
            snippet = (
                f"[{index}] score={result.ranking_score:.3f} source={result.source} "
                f"project={result.project_id} tags={tags}\n{result.raw_text}"
            )
            addition = f"\n\n{snippet}" if lines else snippet
            if used_chars + len(addition) > max_chars:
                truncated_count += 1
                continue
            included_results.append(result)
            lines.append(snippet)
            used_chars += len(addition)

        await self._mark_accessed_results(included_results)

        if truncated_count:
            used_chars = min(max_chars, used_chars + len(f"\n\n[{truncated_count} additional memories omitted]"))

        context_text = "\n\n".join(lines)
        if truncated_count:
            suffix = f"\n\n[{truncated_count} additional memories omitted]"
            if len(context_text) + len(suffix) <= max_chars:
                context_text += suffix

        return MemoryContextResult(
            context_text=context_text,
            used_chars=used_chars,
            truncated_count=truncated_count,
            results=results,
        )

    async def inspect_memories(
        self,
        *,
        user_id: str,
        limit: int,
        project_id: str | None = None,
        include_expired: bool = True,
    ) -> list[Memory]:
        statement = select(Memory).where(Memory.user_id == user_id)
        if project_id:
            statement = statement.where(Memory.project_id == project_id)
        if not include_expired:
            statement = statement.where(self._active_memory_clause())
        statement = statement.order_by(Memory.created_at.desc()).limit(limit)

        try:
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise MemoryServiceError("Failed to inspect memories") from exc

        return list(result.scalars().all())

    async def delete_memory(self, *, memory_id: UUID, user_id: str) -> bool:
        statement = select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
        )

        try:
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise MemoryServiceError("Failed to load memory for deletion") from exc

        memory = result.scalar_one_or_none()
        if memory is None:
            return False

        await self._session.delete(memory)

        try:
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryServiceError("Failed to delete memory") from exc

        return True

    async def _retrieve_ranked_memories(
        self,
        *,
        user_id: str,
        query: str,
        limit: int,
        project_id: str | None,
        include_expired: bool,
    ) -> list[MemorySearchResult]:
        try:
            query_embedding = await self._embedding_service.embed_text(query)
        except EmbeddingProviderError as exc:
            raise MemoryServiceError("Failed to generate query embedding") from exc

        distance = Memory.embedding.cosine_distance(query_embedding)
        candidate_limit = min(max(limit * 5, 10), 100)
        statement: Select[tuple[Memory, float]] = (
            select(Memory, distance.label("distance"))
            .where(Memory.user_id == user_id)
            .order_by(distance.asc())
            .limit(candidate_limit)
        )

        if project_id:
            statement = statement.where(Memory.project_id == project_id)
        if not include_expired:
            statement = statement.where(self._active_memory_clause())

        try:
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise MemoryServiceError("Failed to search memories") from exc

        rows = result.all()
        ranked = [self._to_search_result(memory, distance_value) for memory, distance_value in rows]
        ranked.sort(key=lambda item: item.ranking_score, reverse=True)
        return ranked[:limit]

    async def _mark_accessed_results(self, results: list[MemorySearchResult]) -> None:
        if not results:
            return

        statement = select(Memory).where(Memory.id.in_([result.id for result in results]))
        try:
            query_result = await self._session.execute(statement)
        except SQLAlchemyError:
            return

        accessed_at = datetime.now(UTC)
        for memory in query_result.scalars().all():
            memory.access_count += 1
            memory.last_accessed_at = accessed_at

        try:
            await self._session.commit()
        except SQLAlchemyError:
            await self._session.rollback()
            return

        for result in results:
            result.access_count += 1
            result.last_accessed_at = accessed_at

    def _to_search_result(self, memory: Memory, distance: float) -> MemorySearchResult:
        similarity_score = self._similarity_from_distance(distance)
        freshness_score = self._freshness_score(memory.created_at)
        access_score = min(memory.access_count / 10, 1.0)
        ranking_score = (
            similarity_score * 0.65
            + memory.importance_score * 0.2
            + freshness_score * 0.1
            + access_score * 0.05
        )

        return MemorySearchResult(
            id=memory.id,
            user_id=memory.user_id,
            project_id=memory.project_id,
            raw_text=memory.raw_text,
            importance_score=memory.importance_score,
            source=memory.source,
            tags=list(memory.tags or []),
            metadata=memory.metadata_,
            access_count=memory.access_count,
            created_at=memory.created_at,
            last_accessed_at=memory.last_accessed_at,
            expires_at=memory.expires_at,
            distance=float(distance),
            similarity_score=similarity_score,
            ranking_score=ranking_score,
        )

    def _active_memory_clause(self):
        return or_(Memory.expires_at.is_(None), Memory.expires_at > datetime.now(UTC))

    @staticmethod
    def _similarity_from_distance(distance: float) -> float:
        bounded_distance = min(max(float(distance), 0.0), 2.0)
        return max(0.0, 1.0 - (bounded_distance / 2.0))

    @staticmethod
    def _freshness_score(created_at: datetime) -> float:
        now = datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_days = max((now - created_at).total_seconds() / 86400, 0)
        return math.exp(-age_days / 30)

    @staticmethod
    def _expires_at(ttl_days: int | None) -> datetime | None:
        if ttl_days is None:
            return None
        if ttl_days <= 0:
            raise MemoryValidationError("ttl_days must be greater than 0")
        return datetime.now(UTC) + timedelta(days=ttl_days)

    @staticmethod
    def _estimate_importance(text: str) -> float:
        normalized = text.lower()
        score = 0.35

        signals = {
            "preference": ("prefer", "likes", "dislikes", "always", "never"),
            "task": ("todo", "task", "deadline", "follow up", "must"),
            "correction": ("actually", "correction", "wrong", "instead"),
        }

        for keywords in signals.values():
            if any(keyword in normalized for keyword in keywords):
                score += 0.15

        score += min(len(text) / 500, 0.2)
        return min(score, 0.95)
