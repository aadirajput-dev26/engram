"""
PostgreSQL-backed async job queue using SELECT ... FOR UPDATE SKIP LOCKED.
Per docs/14_ASYNC_PROCESSING.md §2-3.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.job import JobTask, ProcessingJob

logger = get_logger("job_queue")


async def enqueue_task(
    session: AsyncSession,
    task_type: str,
    payload: Dict[str, Any],
    job_id: Optional[UUID] = None,
    priority: int = 0,
) -> JobTask:
    """Enqueue a new task into PostgreSQL queue."""
    task = JobTask(
        id=uuid.uuid4(),
        job_id=job_id,
        task_type=task_type,
        payload=payload,
        status="PENDING",
        priority=priority,
        retry_count=0,
        max_retries=3,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    logger.info("Enqueued task %s (type=%s, priority=%d)", task.id, task_type, priority)
    return task


async def claim_next_task(
    session: AsyncSession,
    worker_id: str,
    task_types: Optional[List[str]] = None,
) -> Optional[JobTask]:
    """
    Claim the next available pending task using SELECT ... FOR UPDATE SKIP LOCKED.
    Safe for multiple concurrent workers without double-claiming.
    """
    stmt = (
        select(JobTask)
        .where(JobTask.status == "PENDING")
        .order_by(JobTask.priority.desc(), JobTask.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if task_types:
        stmt = stmt.where(JobTask.task_type.in_(task_types))

    res = await session.execute(stmt)
    task = res.scalar_one_or_none()

    if task:
        task.status = "CLAIMED"
        task.claimed_by = worker_id
        task.claimed_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()
        await session.refresh(task)
        logger.info("Worker %s claimed task %s (type=%s)", worker_id, task.id, task.task_type)

    return task


async def complete_task(
    session: AsyncSession,
    task_id: UUID,
) -> None:
    """Mark a claimed task as completed."""
    stmt = select(JobTask).where(JobTask.id == task_id)
    res = await session.execute(stmt)
    task = res.scalar_one_or_none()
    if task:
        task.status = "COMPLETED"
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()
        logger.info("Task %s completed successfully", task_id)


async def fail_task(
    session: AsyncSession,
    task_id: UUID,
    error_message: str,
) -> None:
    """Mark a task as failed, re-queuing if retries remain."""
    stmt = select(JobTask).where(JobTask.id == task_id)
    res = await session.execute(stmt)
    task = res.scalar_one_or_none()
    if task:
        task.retry_count += 1
        task.error_message = error_message
        if task.retry_count < task.max_retries:
            task.status = "PENDING"
            task.claimed_by = None
            task.claimed_at = None
            logger.warning(
                "Task %s failed (attempt %d/%d), re-queued: %s",
                task_id, task.retry_count, task.max_retries, error_message,
            )
        else:
            task.status = "FAILED"
            task.completed_at = datetime.datetime.now(datetime.timezone.utc)
            logger.error("Task %s permanently failed after %d retries: %s", task_id, task.retry_count, error_message)
        await session.commit()
