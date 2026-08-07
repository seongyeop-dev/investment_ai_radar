from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class FixedClock:
    value: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", require_aware_utc(self.value))

    def now(self) -> datetime:
        return self.value


def require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetime is not allowed")
    return value.astimezone(UTC)


def restore_utc(value: datetime) -> datetime:
    """Restore UTC at the database serialization boundary.

    SQLite discards timezone offsets even for timezone-aware columns. Application
    inputs must use ``require_aware_utc`` instead of this database-only helper.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
