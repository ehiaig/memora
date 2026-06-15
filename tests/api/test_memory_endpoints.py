from __future__ import annotations

import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.memory_service import MemoryContextResult, MemorySearchResult, MemoryService


def build_result(**overrides):
    payload = {
        "id": uuid4(),
        "user_id": "user-123",
        "project_id": "project-alpha",
        "raw_text": "User prefers FastAPI for backend work.",
        "importance_score": 0.8,
        "source": "chat",
        "tags": ["preference"],
        "metadata": {"channel": "support"},
        "access_count": 2,
        "created_at": datetime.now(UTC),
        "last_accessed_at": None,
        "expires_at": None,
        "distance": 0.15,
        "similarity_score": 0.92,
        "ranking_score": 0.86,
    }
    payload.update(overrides)
    return MemorySearchResult(**payload)


@pytest.mark.asyncio
async def test_search_returns_ranked_results(client, monkeypatch):
    monkeypatch.setattr(
        MemoryService,
        "search_memory",
        AsyncMock(return_value=[build_result()]),
    )

    response = await client.post(
        "/api/v1/memory/search",
        json={"user_id": "user-123", "query": "backend", "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["project_id"] == "project-alpha"
    assert body["results"][0]["ranking_score"] == pytest.approx(0.86)


@pytest.mark.asyncio
async def test_memory_routes_require_api_key() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/memory/search",
            json={"user_id": "user-123", "query": "backend", "limit": 5},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_context_returns_prompt_ready_payload(client, monkeypatch):
    result = MemoryContextResult(
        context_text="[1] score=0.860 source=chat project=project-alpha tags=preference\nUser prefers FastAPI for backend work.",
        used_chars=103,
        truncated_count=0,
        results=[build_result()],
    )
    monkeypatch.setattr(MemoryService, "build_context", AsyncMock(return_value=result))

    response = await client.post(
        "/api/v1/memory/context",
        json={"user_id": "user-123", "query": "backend architecture", "limit": 5, "max_chars": 500},
    )

    assert response.status_code == 200
    body = response.json()
    assert "FastAPI" in body["context_text"]
    assert body["used_chars"] == 103


@pytest.mark.asyncio
async def test_delete_returns_404_when_memory_missing(client, monkeypatch):
    monkeypatch.setattr(MemoryService, "delete_memory", AsyncMock(return_value=False))

    response = await client.request(
        "DELETE",
        f"/api/v1/memory/{uuid4()}",
        json={"user_id": "user-123"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_write_requires_project_id(client):
    response = await client.post(
        "/api/v1/memory/write",
        json={"user_id": "user-123", "text": "hello"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_inspect_returns_serialized_memories(client, monkeypatch):
    memory = SimpleNamespace(
        id=uuid4(),
        user_id="user-123",
        project_id="project-alpha",
        raw_text="User prefers FastAPI for backend work.",
        embedding=[0.01] * 1536,
        importance_score=0.8,
        source="chat",
        tags=["preference"],
        metadata_={"channel": "support"},
        access_count=1,
        last_accessed_at=None,
        expires_at=None,
        created_at=datetime.now(UTC),
    )
    monkeypatch.setattr(MemoryService, "inspect_memories", AsyncMock(return_value=[memory]))

    response = await client.post(
        "/api/v1/memory/inspect",
        json={"user_id": "user-123", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["memories"][0]["metadata"]["channel"] == "support"
