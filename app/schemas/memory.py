from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryBase(BaseModel):
    user_id: str
    project_id: str
    raw_text: str
    importance_score: float = 0.0
    source: str = "user"
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    access_count: int = 0
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None


class MemoryCreate(MemoryBase):
    embedding: list[float]


class MemoryRead(MemoryBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    embedding: list[float]
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
