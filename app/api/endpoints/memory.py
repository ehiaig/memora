from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.db.session import get_db_session
from app.schemas.memory import MemoryRead
from app.services.memory_service import (
    MemoryContextResult,
    MemorySearchResult,
    MemoryService,
    MemoryServiceError,
    MemoryValidationError,
)

router = APIRouter(prefix="/memory", tags=["memory"], dependencies=[Depends(require_api_key)])


class MemoryWriteRequest(BaseModel):
    user_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: str = Field(default="user", min_length=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    importance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    ttl_days: int | None = Field(default=None, ge=1)


class MemorySearchRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    project_id: str | None = None
    limit: int = Field(default=5, ge=1, le=100)
    include_expired: bool = False


class MemoryContextRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    project_id: str | None = None
    limit: int = Field(default=8, ge=1, le=100)
    max_chars: int = Field(default=2000, ge=200, le=20000)
    include_expired: bool = False


class MemoryInspectRequest(BaseModel):
    user_id: str = Field(min_length=1)
    project_id: str | None = None
    limit: int = Field(default=25, ge=1, le=200)
    include_expired: bool = True


class MemoryDeleteRequest(BaseModel):
    user_id: str = Field(min_length=1)


class MemorySearchItem(BaseModel):
    id: UUID
    user_id: str
    project_id: str
    raw_text: str
    importance_score: float
    source: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    access_count: int
    created_at: datetime
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None
    distance: float
    similarity_score: float
    ranking_score: float

    @classmethod
    def from_result(cls, result: MemorySearchResult) -> "MemorySearchItem":
        return cls(
            id=result.id,
            user_id=result.user_id,
            project_id=result.project_id,
            raw_text=result.raw_text,
            importance_score=result.importance_score,
            source=result.source,
            tags=result.tags,
            metadata=result.metadata,
            access_count=result.access_count,
            created_at=result.created_at,
            last_accessed_at=result.last_accessed_at,
            expires_at=result.expires_at,
            distance=result.distance,
            similarity_score=result.similarity_score,
            ranking_score=result.ranking_score,
        )


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchItem]


class MemoryContextResponse(BaseModel):
    context_text: str
    used_chars: int
    truncated_count: int
    results: list[MemorySearchItem]

    @classmethod
    def from_result(cls, result: MemoryContextResult) -> "MemoryContextResponse":
        return cls(
            context_text=result.context_text,
            used_chars=result.used_chars,
            truncated_count=result.truncated_count,
            results=[MemorySearchItem.from_result(item) for item in result.results],
        )


class MemoryInspectResponse(BaseModel):
    memories: list[MemoryRead]


@router.post("/write", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
async def write_memory(
    payload: MemoryWriteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRead:
    service = MemoryService(session)

    try:
        memory = await service.add_memory(
            user_id=payload.user_id,
            project_id=payload.project_id,
            text=payload.text,
            metadata=payload.metadata,
            source=payload.source,
            tags=payload.tags,
            importance_score=payload.importance_score,
            ttl_days=payload.ttl_days,
        )
    except MemoryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MemoryServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return MemoryRead.model_validate(memory)


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(
    payload: MemorySearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MemorySearchResponse:
    service = MemoryService(session)

    try:
        results = await service.search_memory(
            user_id=payload.user_id,
            query=payload.query,
            project_id=payload.project_id,
            limit=payload.limit,
            include_expired=payload.include_expired,
        )
    except MemoryServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return MemorySearchResponse(results=[MemorySearchItem.from_result(result) for result in results])


@router.post("/context", response_model=MemoryContextResponse)
async def build_context(
    payload: MemoryContextRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MemoryContextResponse:
    service = MemoryService(session)

    try:
        result = await service.build_context(
            user_id=payload.user_id,
            query=payload.query,
            project_id=payload.project_id,
            limit=payload.limit,
            max_chars=payload.max_chars,
            include_expired=payload.include_expired,
        )
    except MemoryServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return MemoryContextResponse.from_result(result)


@router.post("/inspect", response_model=MemoryInspectResponse)
async def inspect_memories(
    payload: MemoryInspectRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MemoryInspectResponse:
    service = MemoryService(session)

    try:
        memories = await service.inspect_memories(
            user_id=payload.user_id,
            project_id=payload.project_id,
            limit=payload.limit,
            include_expired=payload.include_expired,
        )
    except MemoryServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return MemoryInspectResponse(memories=[MemoryRead.model_validate(memory) for memory in memories])


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    payload: MemoryDeleteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    service = MemoryService(session)

    try:
        deleted = await service.delete_memory(memory_id=memory_id, user_id=payload.user_id)
    except MemoryServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
