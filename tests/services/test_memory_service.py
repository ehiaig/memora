from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.memory_service import MemoryContextResult, MemorySearchResult, MemoryService, MemoryValidationError


def build_result(**overrides) -> MemorySearchResult:
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
async def test_build_context_truncates_over_budget() -> None:
    service = MemoryService(session=object(), embedding_service=object())
    service._retrieve_ranked_memories = AsyncMock(
        return_value=[
            build_result(raw_text="A" * 160, ranking_score=0.9),
            build_result(raw_text="B" * 160, ranking_score=0.8),
        ]
    )
    service._mark_accessed_results = AsyncMock()

    result = await service.build_context(
        user_id="user-123",
        query="backend",
        project_id=None,
        limit=5,
        max_chars=220,
        include_expired=False,
    )

    assert isinstance(result, MemoryContextResult)
    assert result.truncated_count == 1
    assert "additional memories omitted" in result.context_text
    marked_results = service._mark_accessed_results.await_args.args[0]
    assert len(marked_results) == 1
    assert marked_results[0].raw_text == "A" * 160


@pytest.mark.asyncio
async def test_mark_accessed_results_updates_returned_metadata() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(access_count=2, last_accessed_at=None)]))),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    service = MemoryService(session=session, embedding_service=object())
    result = build_result(access_count=2, last_accessed_at=None)

    await service._mark_accessed_results([result])

    assert result.access_count == 3
    assert result.last_accessed_at is not None


def test_estimate_importance_prioritizes_preferences_and_tasks() -> None:
    service = MemoryService(session=object(), embedding_service=object())

    baseline = service._estimate_importance("Short note.")
    richer = service._estimate_importance("User prefers FastAPI and must follow up before the deadline.")

    assert richer > baseline


def test_expires_at_rejects_non_positive_ttl() -> None:
    service = MemoryService(session=object(), embedding_service=object())

    with pytest.raises(MemoryValidationError):
        service._expires_at(0)


def test_freshness_score_decays_with_age() -> None:
    service = MemoryService(session=object(), embedding_service=object())

    fresh = service._freshness_score(datetime.now(UTC))
    stale = service._freshness_score(datetime.now(UTC) - timedelta(days=90))

    assert fresh > stale
