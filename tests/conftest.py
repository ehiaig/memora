from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://memora:memora@db:5432/memora")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("MEMORA_API_KEY", "memora-test-key")
os.environ.setdefault("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "1536")

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"x-api-key": os.environ["MEMORA_API_KEY"]},
    ) as async_client:
        yield async_client


@pytest.fixture
def memory_factory() -> Any:
    def _create(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": uuid4(),
            "user_id": "user-123",
            "project_id": "project-alpha",
            "raw_text": "User prefers FastAPI for backend work.",
            "importance_score": 0.8,
            "source": "chat",
            "tags": ["preference"],
            "metadata": {"channel": "support"},
            "access_count": 0,
            "created_at": datetime.now(UTC),
            "last_accessed_at": None,
            "expires_at": None,
            "distance": 0.12,
            "similarity_score": 0.94,
            "ranking_score": 0.88,
        }
        payload.update(overrides)
        return payload

    return _create
