from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.core.time import Clock, SystemClock, require_aware_utc

type Threshold = float | int | timedelta


class FreshnessStatus(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    STALE = "STALE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    status: FreshnessStatus
    age_seconds: float | None
    reused_last_normal_value: bool = False


def _seconds(value: Threshold) -> float:
    seconds = value.total_seconds() if isinstance(value, timedelta) else float(value)
    if seconds < 0:
        raise ValueError("freshness thresholds must be non-negative")
    return seconds


def classify_freshness(
    *,
    observed_at: datetime | None,
    current_time: datetime,
    live_threshold: Threshold,
    delayed_threshold: Threshold,
    reused_last_normal_value: bool = False,
) -> FreshnessResult:
    now = require_aware_utc(current_time)
    live_seconds = _seconds(live_threshold)
    delayed_seconds = _seconds(delayed_threshold)
    if delayed_seconds <= live_seconds:
        raise ValueError("delayed_threshold must be greater than live_threshold")
    if observed_at is None:
        return FreshnessResult(
            FreshnessStatus.NOT_AVAILABLE,
            None,
            reused_last_normal_value=False,
        )

    observed = require_aware_utc(observed_at)
    age = max(0.0, (now - observed).total_seconds())
    if age <= live_seconds:
        status = FreshnessStatus.LIVE
    elif age <= delayed_seconds:
        status = FreshnessStatus.DELAYED
    else:
        status = FreshnessStatus.STALE
    return FreshnessResult(status, age, reused_last_normal_value)


class FreshnessPolicy:
    def __init__(
        self,
        *,
        live_threshold: Threshold,
        delayed_threshold: Threshold,
        clock: Clock | None = None,
    ) -> None:
        self._live_threshold = live_threshold
        self._delayed_threshold = delayed_threshold
        self._clock = clock or SystemClock()
        _seconds(live_threshold)
        if _seconds(delayed_threshold) <= _seconds(live_threshold):
            raise ValueError("delayed_threshold must be greater than live_threshold")

    def evaluate(
        self,
        observed_at: datetime | None,
        *,
        current_time: datetime | None = None,
        reused_last_normal_value: bool = False,
    ) -> FreshnessResult:
        return classify_freshness(
            observed_at=observed_at,
            current_time=current_time or self._clock.now(),
            live_threshold=self._live_threshold,
            delayed_threshold=self._delayed_threshold,
            reused_last_normal_value=reused_last_normal_value,
        )
