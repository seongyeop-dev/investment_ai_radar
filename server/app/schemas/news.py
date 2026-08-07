from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import require_aware_utc
from app.models.contracts import VerificationStatus
from app.models.database import SourceGrade
from app.models.disclosures import (
    CertaintyLevel,
    LifecycleStatus,
    NewsProviderType,
    NewsSummaryStatus,
)
from app.schemas.instruments import InstrumentSummary


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class NewsSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, from_attributes=True
    )


class OfficialNewsReference(NewsSchema):
    id: UUID
    title: str
    official_url: str
    provider: str


class NewsRead(NewsSchema):
    id: UUID
    instrument_id: UUID
    portfolio_item_id: UUID | None
    source_id: UUID
    provider: NewsProviderType
    title: str
    source_name: str
    source_domain: str
    source_grade: SourceGrade
    original_url: str
    canonical_url: str
    published_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    short_summary: str | None
    summary_status: NewsSummaryStatus
    primary_claim: str
    certainty_level: CertaintyLevel
    verification_status: VerificationStatus
    trust_score: int
    independent_origin: bool
    duplicate_of_id: UUID | None
    material_change: bool
    stale_reused: bool
    lifecycle_status: LifecycleStatus
    information_event_id: UUID
    related_instrument: InstrumentSummary | None = None
    official_references: list[OfficialNewsReference] = Field(default_factory=list)
    changed_facts: list[dict[str, object]] = Field(default_factory=list)
    trust_score_explanation: str = "진실 확률이 아니라 현재 확보된 증거 강도입니다."


class NewsList(NewsSchema):
    items: list[NewsRead]
    total: int
    limit: int
    offset: int


class ImportantInformationImportRequest(NewsSchema):
    source_url: str = Field(min_length=1, max_length=1000)
    publisher_name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    published_at: datetime
    primary_claim: str = Field(min_length=1, max_length=2000)
    public_summary: str | None = Field(default=None, max_length=1000)
    portfolio_item_id: UUID
    language: str = Field(default="ko", min_length=2, max_length=12)
    material_change: bool = True
    confirm: bool = False

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        del cls
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("공개 링크는 HTTP 또는 HTTPS 절대주소여야 합니다.")
        return normalized

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        del cls
        return require_aware_utc(value)

    @field_validator(
        "publisher_name",
        "title",
        "primary_claim",
        "language",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        del cls
        normalized = value.strip()
        if not normalized:
            raise ValueError("필수 입력값은 비어 있을 수 없습니다.")
        return normalized

    @field_validator("public_summary")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        del cls
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ImportantInformationImportPortfolioItem(NewsSchema):
    id: UUID
    symbol: str
    name: str
    market: str


class ImportantInformationImportDuplicate(NewsSchema):
    duplicate: bool
    existing_reference_id: UUID | None


class ImportantInformationImportClassification(NewsSchema):
    source_name: str
    source_domain: str
    source_grade: SourceGrade
    official_source: bool
    predicted_verification_status: VerificationStatus


class ImportantInformationImportPreview(NewsSchema):
    normalized_url: str
    portfolio_item: ImportantInformationImportPortfolioItem
    duplicate: ImportantInformationImportDuplicate
    classification: ImportantInformationImportClassification
    would_create_source: bool
    would_create_instrument: bool
    validation_warnings: list[str] = Field(default_factory=list)
    would_create: bool
    confirmed: Literal[False] = False


class ImportantInformationImportConfirmed(NewsSchema):
    normalized_url: str
    reference: NewsRead
    information_event_id: UUID
    source_created: bool
    instrument_created: bool
    validation_warnings: list[str] = Field(default_factory=list)
    confirmed: Literal[True] = True
