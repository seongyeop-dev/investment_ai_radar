from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.database import SourceGrade


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class ReferenceSourceSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ReferenceSourceInput(ReferenceSourceSchema):
    name: str = Field(
        min_length=1,
        max_length=200,
    )
    source_grade: SourceGrade
    domain: str = Field(
        min_length=1,
        max_length=253,
    )
    official: bool = True
    enabled: bool = True
    feed_url: str | None = Field(
        default=None,
        max_length=1000,
    )
    provider_type: str | None = Field(
        default=None,
        max_length=50,
    )
    language: str = Field(
        default="und",
        min_length=1,
        max_length=12,
    )
    request_interval_seconds: int = Field(
        default=21600,
        ge=60,
        le=604800,
    )
    timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=120,
    )
    max_items: int = Field(
        default=50,
        ge=1,
        le=500,
    )
    original_source_name: str | None = Field(
        default=None,
        max_length=200,
    )


class ReferenceSourceImportRequest(ReferenceSourceInput):
    feed_url: str = Field(
        min_length=1,
        max_length=1000,
    )
    provider_type: str = Field(
        min_length=1,
        max_length=50,
    )
    confirm: bool = False


class ReferenceSourceDuplicateRead(ReferenceSourceSchema):
    duplicate: bool
    existing_source_id: UUID | None
    matched_fields: list[str]


class ReferenceSourceImportPreview(ReferenceSourceSchema):
    normalized_source: ReferenceSourceInput
    validation_warnings: list[str]
    duplicate: ReferenceSourceDuplicateRead
    would_create: bool
    confirmed: Literal[False] = False


class ReferenceSourceRead(ReferenceSourceSchema):
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
    original_source_name: str | None
    created_at: datetime
    updated_at: datetime
    active_subscription_count: int = 0
    total_subscription_count: int = 0


class ReferenceSourceImportConfirmed(ReferenceSourceSchema):
    source: ReferenceSourceRead
    validation_warnings: list[str]
    confirmed: Literal[True] = True


class ReferenceSourceList(ReferenceSourceSchema):
    items: list[ReferenceSourceRead]
    total: int
    limit: int
    offset: int


class ReferenceSourceUpdateRequest(ReferenceSourceSchema):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    source_grade: SourceGrade | None = None
    domain: str | None = Field(
        default=None,
        min_length=1,
        max_length=253,
    )
    official: bool | None = None
    enabled: bool | None = None
    feed_url: str | None = Field(
        default=None,
        max_length=1000,
    )
    provider_type: str | None = Field(
        default=None,
        max_length=50,
    )
    language: str | None = Field(
        default=None,
        min_length=1,
        max_length=12,
    )
    request_interval_seconds: int | None = Field(
        default=None,
        ge=60,
        le=604800,
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        le=120,
    )
    max_items: int | None = Field(
        default=None,
        ge=1,
        le=500,
    )
    original_source_name: str | None = Field(
        default=None,
        max_length=200,
    )
