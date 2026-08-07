from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystPublisherType,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.database import SourceGrade
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ReferenceDiscoveryCandidateSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ReferenceDiscoveryCandidateSourceRead(ReferenceDiscoveryCandidateSchema):
    id: UUID
    name: str
    domain: str
    source_grade: SourceGrade
    official: bool
    enabled: bool
    feed_url: str | None


class ReferenceDiscoveryCandidateSubscriptionRead(ReferenceDiscoveryCandidateSchema):
    id: UUID
    display_name: str
    subject_type: ReferenceSubjectType
    match_mode: ReferenceMatchMode
    enabled: bool


class ReferenceDiscoveryCandidateRead(ReferenceDiscoveryCandidateSchema):
    id: UUID
    source_id: UUID
    subscription_id: UUID
    provider_item_id: str
    publisher_name: str
    title: str
    analyst_name: str | None
    canonical_url: str
    published_at: datetime | None
    verification_status: ReferenceDiscoveryCandidateStatus
    first_seen_at: datetime
    last_seen_at: datetime
    seen_count: int
    public_abstract: str | None
    publisher_type: AnalystPublisherType
    access_type: AnalystAccessType
    document_type: AnalystDocumentType
    promoted_reference_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    source: ReferenceDiscoveryCandidateSourceRead
    subscription: ReferenceDiscoveryCandidateSubscriptionRead


class ReferenceDiscoveryCandidateList(ReferenceDiscoveryCandidateSchema):
    items: list[ReferenceDiscoveryCandidateRead]
    total: int
    limit: int
    offset: int
