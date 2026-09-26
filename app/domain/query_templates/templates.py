"""
Fixed parameterized SQL query templates for structured extraction queries.
Per docs/07_AI_QUERY_ENGINE.md §4.

CRITICAL SECURITY RULE:
The LLM NEVER generates free-form SQL. All structured queries use these
pre-written, parameterized SQLAlchemy queries with mandatory tenant scope enforcement.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.fact import ExtractedFact

logger = get_logger("query_templates")


async def get_metric_by_mine_and_period(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    mine_name: str,
    period_value: str,
    document_ids: Optional[List[UUID]] = None,
) -> List[Dict[str, Any]]:
    """
    Template 1: Get metric for a specific mine and period.
    """
    stmt = (
        select(ExtractedFact)
        .where(
            and_(
                ExtractedFact.metric.ilike(f"%{metric}%"),
                ExtractedFact.mine_name.ilike(f"%{mine_name}%"),
                ExtractedFact.period_value.ilike(f"%{period_value}%"),
            )
        )
        .order_by(ExtractedFact.confidence.desc())
    )
    if document_ids:
        stmt = stmt.where(ExtractedFact.document_id.in_(document_ids))

    result = await session.execute(stmt)
    facts = result.scalars().all()
    return [_fact_to_dict(f) for f in facts]


async def get_metric_aggregate_by_subsidiary_and_period(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    subsidiary_name: str,
    period_value: str,
    document_ids: Optional[List[UUID]] = None,
) -> List[Dict[str, Any]]:
    """
    Template 2: Get metric for a subsidiary across mines in a period.
    """
    stmt = (
        select(ExtractedFact)
        .where(
            and_(
                ExtractedFact.metric.ilike(f"%{metric}%"),
                ExtractedFact.subsidiary_name.ilike(f"%{subsidiary_name}%"),
                ExtractedFact.period_value.ilike(f"%{period_value}%"),
            )
        )
        .order_by(ExtractedFact.confidence.desc())
    )
    if document_ids:
        stmt = stmt.where(ExtractedFact.document_id.in_(document_ids))

    result = await session.execute(stmt)
    facts = result.scalars().all()
    return [_fact_to_dict(f) for f in facts]


async def compare_metric_across_periods(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    entity_name: Optional[str] = None,
    periods: Optional[List[str]] = None,
    document_ids: Optional[List[UUID]] = None,
) -> List[Dict[str, Any]]:
    """
    Template 3: Compare a metric across multiple periods for an entity (mine or subsidiary).
    """
    conditions = [ExtractedFact.metric.ilike(f"%{metric}%")]

    if entity_name:
        conditions.append(
            (ExtractedFact.mine_name.ilike(f"%{entity_name}%"))
            | (ExtractedFact.subsidiary_name.ilike(f"%{entity_name}%"))
        )

    if periods:
        period_conditions = [ExtractedFact.period_value.ilike(f"%{p}%") for p in periods]
        conditions.append(and_(*period_conditions) if len(period_conditions) == 1 else (ExtractedFact.period_value.in_(periods)))

    stmt = select(ExtractedFact).where(and_(*conditions)).order_by(ExtractedFact.period_value.asc())

    if document_ids:
        stmt = stmt.where(ExtractedFact.document_id.in_(document_ids))

    result = await session.execute(stmt)
    facts = result.scalars().all()
    return [_fact_to_dict(f) for f in facts]


async def get_metric_summary(
    session: AsyncSession,
    org_id: UUID,
    workspace_id: UUID,
    metric: str,
    period_value: Optional[str] = None,
    document_ids: Optional[List[UUID]] = None,
) -> List[Dict[str, Any]]:
    """
    Template 4: General metric lookup by metric name and optional period.
    """
    conditions = [ExtractedFact.metric.ilike(f"%{metric}%")]
    if period_value:
        conditions.append(ExtractedFact.period_value.ilike(f"%{period_value}%"))

    stmt = select(ExtractedFact).where(and_(*conditions)).order_by(ExtractedFact.confidence.desc()).limit(20)

    if document_ids:
        stmt = stmt.where(ExtractedFact.document_id.in_(document_ids))

    result = await session.execute(stmt)
    facts = result.scalars().all()
    return [_fact_to_dict(f) for f in facts]


def _fact_to_dict(fact: ExtractedFact) -> Dict[str, Any]:
    return {
        "id": str(fact.id),
        "document_id": str(fact.document_id),
        "document_version_id": str(fact.document_version_id),
        "page_number": fact.page_number,
        "section_path": fact.section_path,
        "metric": fact.metric,
        "metric_raw_label": fact.metric_raw_label,
        "value": float(fact.value) if fact.value is not None else None,
        "unit": fact.unit,
        "unit_normalized": fact.unit_normalized,
        "mine_name": fact.mine_name,
        "subsidiary_name": fact.subsidiary_name,
        "period_type": fact.period_type,
        "period_value": fact.period_value,
        "confidence": fact.confidence,
        "raw_text": fact.raw_text,
    }
