from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.memory import MemoryRead
from app.services.memory_service import (
    MemorySearchResult,
    MemoryService,
    MemoryServiceError,
    MemoryValidationError,
)

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryWriteRequest(BaseModel):
    user_id: str
    text: str
    metadata: dict = Field(default_factory=dict)


class MemorySearchRequest(BaseModel):
    user_id: str
    query: str
    limit: int = Field(default=5, ge=1, le=100)


class MemorySearchItem(BaseModel):
    id: UUID
    user_id: str
    project_id: str
    raw_text: str
    importance_score: float
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    distance: float

    @classmethod
    def from_result(cls, result: MemorySearchResult) -> "MemorySearchItem":
        return cls(
            id=result.id,
            user_id=result.user_id,
            project_id=result.project_id,
            raw_text=result.raw_text,
            importance_score=result.importance_score,
            metadata=result.metadata,
            created_at=result.created_at,
            distance=result.distance,
        )


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchItem]


@router.post("/write", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
async def write_memory(
    payload: MemoryWriteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRead:
    service = MemoryService(session)

    try:
        memory = await service.add_memory(
            user_id=payload.user_id,
            text=payload.text,
            metadata=payload.metadata,
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
            limit=payload.limit,
        )
    except MemoryServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return MemorySearchResponse(
        results=[MemorySearchItem.from_result(result) for result in results]
    )
