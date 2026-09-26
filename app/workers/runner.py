"""
Async worker process runner.
Per docs/14_ASYNC_PROCESSING.md §3.

Polls the PostgreSQL job queue, claims tasks via SKIP LOCKED,
and dispatches execution to the appropriate pipeline service.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys
import uuid
from typing import Optional
from uuid import UUID

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.domain.reports.report_service import generate_report_draft
from app.domain.topics.topic_service import run_topic_analysis
from app.services.document_service import process_document_pipeline
from app.workers.job_queue import claim_next_task, complete_task, fail_task

logger = get_logger("worker_runner")


async def execute_task(task) -> None:
    """Dispatch and execute a claimed task."""
    task_type = task.task_type
    payload = task.payload or {}
    logger.info("Executing task %s (type=%s)", task.id, task_type)

    async with async_session_factory() as session:
        try:
            if task_type == "DOCUMENT_INGEST":
                # Ingest pipeline task
                doc_id = UUID(payload["document_id"])
                version_id = UUID(payload["document_version_id"])
                job_id = UUID(payload["job_id"])
                file_path = payload["file_path"]
                await process_document_pipeline(
                    session=session,
                    job_id=job_id,
                    document_id=doc_id,
                    document_version_id=version_id,
                    file_path=file_path,
                )

            elif task_type == "TOPIC_ANALYSIS":
                job_id = UUID(payload["job_id"])
                org_id = UUID(payload["org_id"])
                workspace_id = UUID(payload["workspace_id"])
                doc_ids_raw = payload.get("document_ids")
                doc_ids = [UUID(d) for d in doc_ids_raw] if doc_ids_raw else None
                num_topics = payload.get("num_topics", 5)
                await run_topic_analysis(
                    db=session,
                    job_id=job_id,
                    org_id=org_id,
                    workspace_id=workspace_id,
                    document_ids=doc_ids,
                    num_topics=num_topics,
                )

            elif task_type == "REPORT_GENERATE":
                job_id = UUID(payload["job_id"])
                org_id = UUID(payload["org_id"])
                workspace_id = UUID(payload["workspace_id"])
                report_type = payload["report_type"]
                parameters = payload.get("parameters", {})
                output_format = payload.get("output_format", "docx")
                await generate_report_draft(
                    db=session,
                    job_id=job_id,
                    org_id=org_id,
                    workspace_id=workspace_id,
                    report_type=report_type,
                    parameters=parameters,
                    output_format=output_format,
                )

            else:
                logger.error("Unknown task type: %s", task_type)
                await fail_task(session, task.id, f"Unknown task type: {task_type}")
                return

            await complete_task(session, task.id)

        except Exception as exc:
            logger.exception("Failed executing task %s: %s", task.id, exc)
            await fail_task(session, task.id, str(exc))


async def run_worker_loop(worker_id: Optional[str] = None, poll_interval: float = 2.0) -> None:
    """Continuous worker loop polling the queue."""
    w_id = worker_id or f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    logger.info("Starting worker loop: %s", w_id)
    stop_event = asyncio.Event()

    def handle_stop(*args):
        logger.info("Worker received stop signal, draining...")
        stop_event.set()

    # Register signals on platforms that support them
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_stop)
        except Exception:
            pass

    while not stop_event.is_set():
        try:
            async with async_session_factory() as session:
                task = await claim_next_task(session, worker_id=w_id)
            if task:
                await execute_task(task)
            else:
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error in worker polling loop: %s", exc)
            await asyncio.sleep(poll_interval)

    logger.info("Worker %s shut down cleanly", w_id)


if __name__ == "__main__":
    asyncio.run(run_worker_loop())
