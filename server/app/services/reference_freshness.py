from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.analyst_references import (
    AnalystFreshnessStatus,
)

CURRENT_MAX_AGE = timedelta(days=30)
AGING_MAX_AGE = timedelta(days=90)


def normalize_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    Existing SQLite rows may contain naive values. Those values are treated
    as UTC because the reference ingestion pipeline stores UTC timestamps.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def calculate_reference_freshness(
    published_at: datetime | None,
    *,
    now: datetime | None = None,
) -> AnalystFreshnessStatus:
    """Classify a public reference using only its publication timestamp."""

    if published_at is None:
        return AnalystFreshnessStatus.UNKNOWN

    reference_now = normalize_utc(now or datetime.now(UTC))
    normalized_published_at = normalize_utc(published_at)

    if normalized_published_at > reference_now:
        return AnalystFreshnessStatus.UNKNOWN

    age = reference_now - normalized_published_at

    if age <= CURRENT_MAX_AGE:
        return AnalystFreshnessStatus.CURRENT

    if age <= AGING_MAX_AGE:
        return AnalystFreshnessStatus.AGING

    return AnalystFreshnessStatus.STALE
