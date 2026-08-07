from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.database import SourceGrade
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ReferenceSubscriptionSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ReferenceSubscriptionSourceRead(ReferenceSubscriptionSchema):
    id: UUID
    name: str
    source_type: str
    source_grade: SourceGrade
    domain: str
    official: bool
    enabled: bool
    feed_url: str | None
    provider_type: str | None
    language: str
    request_interval_seconds: int
    timeout_seconds: int
    max_items: int


class ReferenceSubscriptionSourceList(ReferenceSubscriptionSchema):
    items: list[ReferenceSubscriptionSourceRead]
    total: int
    limit: int
    offset: int


class ReferenceSubscriptionRead(ReferenceSubscriptionSchema):
    id: UUID
    source_id: UUID
    subject_type: ReferenceSubjectType
    display_name: str
    match_mode: ReferenceMatchMode
    match_terms: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    automatic_reference_count: int = 0
    source: ReferenceSubscriptionSourceRead


class ReferenceSubscriptionList(ReferenceSubscriptionSchema):
    items: list[ReferenceSubscriptionRead]
    total: int
    limit: int
    offset: int


class ReferenceSubscriptionUpdateRequest(ReferenceSubscriptionSchema):
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    match_mode: ReferenceMatchMode | None = None
    match_terms: list[str] | None = None
    enabled: bool | None = None


class ReferenceSubscriptionImportRequest(ReferenceSubscriptionSchema):
    source_id: UUID
    subject_type: ReferenceSubjectType
    display_name: str = Field(
        min_length=1,
        max_length=200,
    )
    match_mode: ReferenceMatchMode
    match_terms: list[str] = Field(
        default_factory=list,
    )
    confirm: bool = False


class ReferenceSubscriptionImportDuplicateRead(ReferenceSubscriptionSchema):
    duplicate: bool
    existing_subscription_id: UUID | None = None


class ReferenceSubscriptionImportResultBase(ReferenceSubscriptionSchema):
    normalized_display_name: str
    normalized_match_terms: list[str]
    source: ReferenceSubscriptionSourceRead | None
    validation_warnings: list[str] = Field(
        default_factory=list,
    )


class ReferenceSubscriptionImportPreview(ReferenceSubscriptionImportResultBase):
    duplicate: ReferenceSubscriptionImportDuplicateRead
    would_create: bool
    confirmed: Literal[False] = False


class ReferenceSubscriptionImportConfirmed(ReferenceSubscriptionImportResultBase):
    subscription: ReferenceSubscriptionRead
    confirmed: Literal[True] = True
