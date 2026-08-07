import json
import logging
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.backoff import ReconnectBackoff
from app.core.freshness import FreshnessPolicy, FreshnessStatus, classify_freshness
from app.core.logging import JsonFormatter
from app.core.sequence import SequenceDecision, SequenceTracker
from app.core.time import FixedClock, SystemClock, require_aware_utc
from app.providers.status import ProviderState, ProviderStatus


def test_system_clock_returns_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)


def test_fixed_clock_normalizes_to_utc() -> None:
    supplied = datetime(2026, 7, 25, 12, tzinfo=timezone(timedelta(hours=9)))
    assert FixedClock(supplied).now() == datetime(2026, 7, 25, 3, tzinfo=UTC)


def test_naive_datetime_is_rejected() -> None:
    naive = datetime.fromisoformat("2026-07-25T12:00:00")
    with pytest.raises(ValueError, match="naive"):
        require_aware_utc(naive)
    with pytest.raises(ValueError, match="naive"):
        FixedClock(naive)


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(seconds=5), FreshnessStatus.LIVE),
        (timedelta(seconds=10), FreshnessStatus.DELAYED),
        (timedelta(seconds=10, microseconds=1), FreshnessStatus.STALE),
    ],
)
def test_freshness_boundaries(age: timedelta, expected: FreshnessStatus) -> None:
    now = datetime(2026, 7, 25, 3, tzinfo=UTC)
    result = classify_freshness(
        observed_at=now - age,
        current_time=now,
        live_threshold=5,
        delayed_threshold=10,
    )
    assert result.status is expected


def test_freshness_without_timestamp_is_not_available() -> None:
    result = classify_freshness(
        observed_at=None,
        current_time=datetime(2026, 7, 25, 3, tzinfo=UTC),
        live_threshold=5,
        delayed_threshold=10,
    )
    assert result.status is FreshnessStatus.NOT_AVAILABLE
    assert result.age_seconds is None
    assert result.reused_last_normal_value is False


def test_freshness_policy_uses_injected_clock() -> None:
    now = datetime(2026, 7, 25, 3, tzinfo=UTC)
    policy = FreshnessPolicy(
        live_threshold=timedelta(seconds=5),
        delayed_threshold=timedelta(seconds=10),
        clock=FixedClock(now),
    )
    assert policy.evaluate(now - timedelta(seconds=6)).status is FreshnessStatus.DELAYED


def test_sequence_first_increase_duplicate_and_regression() -> None:
    tracker = SequenceTracker()
    assert tracker.inspect("provider:trade", 10) is SequenceDecision.ACCEPTED
    assert tracker.inspect("provider:trade", 11) is SequenceDecision.ACCEPTED
    assert tracker.inspect("provider:trade", 11) is SequenceDecision.DUPLICATE
    assert tracker.inspect("provider:trade", 10) is SequenceDecision.REGRESSION


def test_backoff_has_expected_growth_and_cap() -> None:
    backoff = ReconnectBackoff(jitter_ratio=0)
    assert [backoff.delay(attempt) for attempt in range(6)] == [1, 2, 4, 8, 15, 15]


def test_backoff_jitter_never_exceeds_cap() -> None:
    backoff = ReconnectBackoff(jitter_ratio=1, random_value=lambda: 1)
    assert backoff.delay(3) == 15
    assert backoff.delay(100) == 15


def test_backoff_rejects_negative_attempt() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ReconnectBackoff().delay(-1)


def test_provider_reuse_requires_real_last_success() -> None:
    with pytest.raises(ValueError, match="actual last successful"):
        ProviderState(ProviderStatus.ERROR, reuses_last_success=True)

    state = ProviderState(
        ProviderStatus.STALE,
        last_success_at=datetime(2026, 7, 25, 3, tzinfo=UTC),
        reuses_last_success=True,
    )
    assert state.reuses_last_success is True


def test_structured_logging_masks_secrets() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer real-token",
        args=(),
        exc_info=None,
    )
    record.context = {
        "api_key": "real-api-key",
        "password": "real-password",
        "event": "provider_error",
    }
    payload = json.loads(JsonFormatter().format(record))
    encoded = json.dumps(payload)
    assert "real-token" not in encoded
    assert "real-api-key" not in encoded
    assert "real-password" not in encoded
    assert payload["context"]["event"] == "provider_error"
