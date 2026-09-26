"""
Fixed parameterized SQL query templates for structured extraction queries.
Per docs/07_AI_QUERY_ENGINE.md.

NOTE: ExtractedFact model has been removed. These templates now return empty
results until the structured extraction feature is re-implemented.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger("query_templates")


async def get_metric_by_mine_and_period(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    mine_name: str,
    period_value: str,
    document_ids=None,
):
    logger.debug("get_metric_by_mine_and_period called (stub)")
    return []


async def get_metric_aggregate_by_subsidiary_and_period(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    subsidiary_name: str,
    period_value: str,
    document_ids=None,
):
    logger.debug("get_metric_aggregate_by_subsidiary_and_period called (stub)")
    return []


async def compare_metric_across_periods(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    entity_name=None,
    periods=None,
    document_ids=None,
):
    logger.debug("compare_metric_across_periods called (stub)")
    return []


async def get_metric_summary(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    period_value=None,
    document_ids=None,
):
    logger.debug("get_metric_summary called (stub)")
    return []