"""
Unit tests for PostgreSQL async job queue.
Per docs/14_ASYNC_PROCESSING.md.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.job import JobTask
from app.workers.job_queue import complete_task, enqueue_task, fail_task


@pytest.mark.asyncio
async def test_enqueue_task():
    session = AsyncMock()
    task_type = "DOCUMENT_INGEST"
    payload = {"document_id": str(uuid4())}

    task = await enqueue_task(
        session=session,
        task_type=task_type,
        payload=payload,
        priority=10,
    )

    assert task.task_type == task_type
    assert task.priority == 10
    assert task.status == "PENDING"
    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_complete_task():
    session = AsyncMock()
    mock_task = JobTask(id=uuid4(), status="CLAIMED")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_result

    await complete_task(session, mock_task.id)

    assert mock_task.status == "COMPLETED"
    assert mock_task.completed_at is not None
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_fail_task_retries():
    session = AsyncMock()
    mock_task = JobTask(id=uuid4(), status="CLAIMED", retry_count=0, max_retries=3)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_result

    # First failure -> retry
    await fail_task(session, mock_task.id, "Connection timeout")
    assert mock_task.retry_count == 1
    assert mock_task.status == "PENDING"
    assert mock_task.error_message == "Connection timeout"

    # Max retries exceeded -> FAILED
    mock_task.retry_count = 2
    await fail_task(session, mock_task.id, "Permanent DB error")
    assert mock_task.retry_count == 3
    assert mock_task.status == "FAILED"
