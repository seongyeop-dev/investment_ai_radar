from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.time import require_aware_utc


class ProviderStatus(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONNECTING = "CONNECTING"
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ProviderState:
    status: ProviderStatus
    last_success_at: datetime | None = None
    reuses_last_success: bool = False

    def __post_init__(self) -> None:
        if self.last_success_at is not None:
            object.__setattr__(
                self,
                "last_success_at",
                require_aware_utc(self.last_success_at),
            )
        if self.reuses_last_success and self.last_success_at is None:
            raise ValueError("reuses_last_success requires an actual last successful value")
        if (
            self.status in {ProviderStatus.NOT_CONFIGURED, ProviderStatus.CONNECTING}
            and self.reuses_last_success
        ):
            raise ValueError(f"{self.status} cannot reuse a last successful value")
