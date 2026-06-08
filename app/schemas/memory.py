from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryBase(BaseModel):
    user_id: str
    project_id: str
    raw_text: str
    importance_score: float = 0.0
    metadata: dict = Field(default_factory=dict)


class MemoryCreate(MemoryBase):
    embedding: list[float]


class MemoryRead(MemoryBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    embedding: list[float]
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
