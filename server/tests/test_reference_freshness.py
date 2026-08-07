from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.analyst_references import (
    AnalystFreshnessStatus,
)
from app.services.reference_freshness import (
    AGING_MAX_AGE,
    CURRENT_MAX_AGE,
    calculate_reference_freshness,
)

NOW = datetime(
    2026,
    7,
    31,
    8,
    30,
    tzinfo=UTC,
)


@pytest.mark.parametrize(
    ("published_at", "expected"),
    (
        (
            None,
            AnalystFreshnessStatus.UNKNOWN,
        ),
        (
            NOW + timedelta(seconds=1),
            AnalystFreshnessStatus.UNKNOWN,
        ),
        (
            NOW,
            AnalystFreshnessStatus.CURRENT,
        ),
        (
            NOW - CURRENT_MAX_AGE,
            AnalystFreshnessStatus.CURRENT,
        ),
        (
            NOW - CURRENT_MAX_AGE - timedelta(seconds=1),
            AnalystFreshnessStatus.AGING,
        ),
        (
            NOW - AGING_MAX_AGE,
            AnalystFreshnessStatus.AGING,
        ),
        (
            NOW - AGING_MAX_AGE - timedelta(seconds=1),
            AnalystFreshnessStatus.STALE,
        ),
    ),
)
def test_calculate_reference_freshness_boundaries(
    published_at: datetime | None,
    expected: AnalystFreshnessStatus,
) -> None:
    assert (
        calculate_reference_freshness(
            published_at,
            now=NOW,
        )
        is expected
    )


def test_naive_timestamp_is_interpreted_as_utc() -> None:
    published_at = (NOW - timedelta(days=30)).replace(tzinfo=None)

    result = calculate_reference_freshness(
        published_at,
        now=NOW,
    )

    assert result is AnalystFreshnessStatus.CURRENT


@pytest.mark.parametrize(
    ("published_at", "expected"),
    (
        (
            datetime(
                2026,
                4,
                9,
                7,
                0,
                tzinfo=UTC,
            ),
            AnalystFreshnessStatus.STALE,
        ),
        (
            datetime(
                2026,
                2,
                26,
                8,
                0,
                tzinfo=UTC,
            ),
            AnalystFreshnessStatus.STALE,
        ),
        (
            datetime(
                2025,
                12,
                9,
                8,
                0,
                tzinfo=UTC,
            ),
            AnalystFreshnessStatus.STALE,
        ),
    ),
)
def test_current_real_reference_preview_expectations(
    published_at: datetime,
    expected: AnalystFreshnessStatus,
) -> None:
    assert (
        calculate_reference_freshness(
            published_at,
            now=NOW,
        )
        is expected
    )
