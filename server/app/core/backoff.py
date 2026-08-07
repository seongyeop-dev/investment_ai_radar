from __future__ import annotations

import random
from collections.abc import Callable


class ReconnectBackoff:
    def __init__(
        self,
        *,
        base_seconds: float = 1.0,
        maximum_seconds: float = 15.0,
        jitter_ratio: float = 0.2,
        random_value: Callable[[], float] | None = None,
    ) -> None:
        if base_seconds <= 0 or maximum_seconds < base_seconds:
            raise ValueError("invalid backoff bounds")
        if not 0 <= jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")
        self._base = base_seconds
        self._maximum = maximum_seconds
        self._jitter_ratio = jitter_ratio
        self._random_value = random_value or random.random

    def delay(self, attempt: int) -> float:
        if attempt < 0:
            raise ValueError("attempt must be non-negative")
        bounded = min(self._maximum, self._base * (2**attempt))
        sample = self._random_value()
        if not 0 <= sample <= 1:
            raise ValueError("random_value must return a value between 0 and 1")
        jitter = bounded * self._jitter_ratio * sample
        return min(self._maximum, bounded + jitter)
