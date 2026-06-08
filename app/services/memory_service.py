from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
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
    metadata: dict
    created_at: datetime
    distance: float


class MemoryService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._session = session
        self._embedding_service = embedding_service or EmbeddingService()

    async def add_memory(self, user_id: str, text: str, metadata: dict) -> Memory:
        project_id = metadata.get("project_id")
        if not project_id:
            raise MemoryValidationError("metadata.project_id is required")

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
        user_id: str,
        query: str,
        limit: int,
    ) -> list[MemorySearchResult]:
        try:
            query_embedding = await self._embedding_service.embed_text(query)
        except EmbeddingProviderError as exc:
            raise MemoryServiceError("Failed to generate query embedding") from exc

        distance = Memory.embedding.cosine_distance(query_embedding)
        statement: Select[tuple[Memory, float]] = (
            select(Memory, distance.label("distance"))
            .where(Memory.user_id == user_id)
            .order_by(distance.asc())
            .limit(limit)
        )

        try:
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise MemoryServiceError("Failed to search memories") from exc

        rows = result.all()

        return [
            MemorySearchResult(
                id=memory.id,
                user_id=memory.user_id,
                project_id=memory.project_id,
                raw_text=memory.raw_text,
                importance_score=memory.importance_score,
                metadata=memory.metadata_,
                created_at=memory.created_at,
                distance=distance_value,
            )
            for memory, distance_value in rows
        ]
