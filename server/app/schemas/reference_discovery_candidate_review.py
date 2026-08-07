from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.core.time import require_aware_utc
from app.models.analyst_references import (
    ReferenceDiscoveryCandidateReviewAction,
    ReferenceDiscoveryCandidateStatus,
)
from app.schemas.reference_discovery_candidates import (
    ReferenceDiscoveryCandidateRead,
    ReferenceDiscoveryCandidateSchema,
)


def _normalized_optional_reason(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = " ".join(value.split())

    return normalized or None


class ReferenceDiscoveryCandidateVerifyDateRequest(ReferenceDiscoveryCandidateSchema):
    published_at: datetime
    reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("published_at")
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        del cls
        return require_aware_utc(value)

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str | None,
    ) -> str | None:
        del cls
        return _normalized_optional_reason(value)


class ReferenceDiscoveryCandidatePromoteRequest(ReferenceDiscoveryCandidateSchema):
    confirm: bool = False
    reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str | None,
    ) -> str | None:
        del cls
        return _normalized_optional_reason(value)


class ReferenceDiscoveryCandidateDismissRequest(ReferenceDiscoveryCandidateSchema):
    confirm: bool = False
    reason: str = Field(
        min_length=1,
        max_length=1000,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str,
    ) -> str:
        del cls

        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError("reason must not be empty")

        return normalized


class ReferenceDiscoveryCandidateReviewHistoryRead(ReferenceDiscoveryCandidateSchema):
    id: UUID
    candidate_id: UUID
    action: ReferenceDiscoveryCandidateReviewAction
    previous_status: ReferenceDiscoveryCandidateStatus
    new_status: ReferenceDiscoveryCandidateStatus
    verified_published_at: datetime | None
    promoted_reference_id: UUID | None
    reason: str | None
    created_at: datetime


class ReferenceDiscoveryCandidateReviewHistoryList(ReferenceDiscoveryCandidateSchema):
    items: list[ReferenceDiscoveryCandidateReviewHistoryRead]
    total: int
    limit: int
    offset: int


class ReferenceDiscoveryCandidateReviewResult(ReferenceDiscoveryCandidateSchema):
    candidate: ReferenceDiscoveryCandidateRead
    history: ReferenceDiscoveryCandidateReviewHistoryRead
    reference_id: UUID | None
    reference_created: bool
    reference_duplicate: bool
