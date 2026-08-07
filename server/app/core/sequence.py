from __future__ import annotations

from enum import StrEnum


class SequenceDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REGRESSION = "REGRESSION"
    RETROGRADE = "REGRESSION"


class SequenceTracker:
    """Track independent monotonically increasing provider streams.

    Reset acceptance is intentionally absent. A provider restart must establish a
    new stream identity; silently accepting a lower value on the same stream would
    hide replayed or out-of-order data.
    """

    def __init__(self) -> None:
        self._latest_by_stream: dict[str, int] = {}

    def inspect(self, stream: str, sequence: int) -> SequenceDecision:
        if not stream or sequence < 0:
            raise ValueError("stream must be non-empty and sequence must be non-negative")
        previous = self._latest_by_stream.get(stream)
        if previous is None or sequence > previous:
            self._latest_by_stream[stream] = sequence
            return SequenceDecision.ACCEPTED
        if sequence == previous:
            return SequenceDecision.DUPLICATE
        return SequenceDecision.REGRESSION
