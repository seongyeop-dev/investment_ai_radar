from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analyst_references import (
    AnalystFreshnessStatus,
    AnalystIngestMode,
    AnalystReferenceRecord,
)
from app.services.reference_freshness import (
    calculate_reference_freshness,
    normalize_utc,
)


@dataclass(frozen=True)
class ReferenceFreshnessRefreshSummary:
    examined: int
    updated: int
    current: int
    aging: int
    stale: int
    unknown: int


def refresh_automatic_reference_freshness(
    session: Session,
    *,
    subscription_id: str | None = None,
    now: datetime | None = None,
) -> ReferenceFreshnessRefreshSummary:
    """Recalculate active automatic reference freshness.

    The caller owns the transaction. This function never commits.
    """

    current = normalize_utc(now or datetime.now(UTC))

    statement = select(AnalystReferenceRecord).where(
        AnalystReferenceRecord.ingest_mode == AnalystIngestMode.AUTOMATIC,
        AnalystReferenceRecord.is_active.is_(True),
    )

    if subscription_id is not None:
        statement = statement.where(AnalystReferenceRecord.subscription_id == subscription_id)

    references = list(session.scalars(statement))

    status_counts = {status: 0 for status in AnalystFreshnessStatus}

    updated = 0

    for reference in references:
        calculated_status = calculate_reference_freshness(
            reference.published_at,
            now=current,
        )

        status_counts[calculated_status] += 1

        stored_status = AnalystFreshnessStatus(reference.freshness_status)

        if stored_status is calculated_status:
            continue

        reference.freshness_status = calculated_status
        updated += 1

    if updated:
        session.flush()

    return ReferenceFreshnessRefreshSummary(
        examined=len(references),
        updated=updated,
        current=status_counts[AnalystFreshnessStatus.CURRENT],
        aging=status_counts[AnalystFreshnessStatus.AGING],
        stale=status_counts[AnalystFreshnessStatus.STALE],
        unknown=status_counts[AnalystFreshnessStatus.UNKNOWN],
    )
