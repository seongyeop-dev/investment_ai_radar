from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import require_aware_utc
from app.models.contracts import VerificationStatus
from app.models.database import SourceGrade
from app.models.disclosures import LifecycleStatus, ProviderName, SummaryStatus
from app.schemas.instruments import InstrumentSummary


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class DisclosureSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, from_attributes=True
    )


class PortfolioDisclosureReference(DisclosureSchema):
    id: UUID
    name: str
    symbol: str
    position_status: str
    tracking_status: str


class DisclosureRead(DisclosureSchema):
    id: UUID
    instrument_id: UUID
    event_id: UUID
    provider: ProviderName
    provider_document_id: str
    accession_number: str | None
    receipt_number: str | None
    form_type: str | None
    report_type: str | None
    title: str
    company_name: str
    official_url: str
    published_at: datetime
    first_seen_at: datetime
    fetched_at: datetime
    verified_at: datetime | None
    verification_status: VerificationStatus
    source_grade: SourceGrade
    summary: str | None
    summary_status: SummaryStatus
    key_facts: list[dict[str, object]]
    material_change: bool
    correction_of_id: UUID | None
    lifecycle_status: LifecycleStatus
    related_instrument: InstrumentSummary | None = None
    related_portfolio_items: list[PortfolioDisclosureReference] = Field(default_factory=list)


class DisclosureList(DisclosureSchema):
    items: list[DisclosureRead]
    total: int
    limit: int
    offset: int


class OfficialDisclosureImportRequest(DisclosureSchema):
    official_url: str = Field(min_length=1, max_length=1000)
    title: str = Field(min_length=1, max_length=500)
    published_at: datetime
    claim: str = Field(min_length=1, max_length=2000)
    summary: str | None = Field(default=None, max_length=2000)
    portfolio_item_id: UUID
    form_type: str | None = Field(default=None, max_length=50)
    material_change: bool = False
    confirm: bool = False

    @field_validator("official_url")
    @classmethod
    def validate_official_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("공식 원문은 HTTP 또는 HTTPS 절대 주소여야 합니다.")
        return value.strip()

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class OfficialDisclosureImportPortfolioItem(DisclosureSchema):
    id: UUID
    symbol: str
    name: str
    market: str


class OfficialDisclosureImportDuplicate(DisclosureSchema):
    duplicate: bool
    existing_disclosure_id: UUID | None = None


class OfficialDisclosureImportClassification(DisclosureSchema):
    provider: ProviderName
    provider_label: str
    source_grade: SourceGrade
    predicted_verification_status: VerificationStatus


class OfficialDisclosureImportPreview(DisclosureSchema):
    normalized_url: str
    provider_document_id: str
    portfolio_item: OfficialDisclosureImportPortfolioItem
    duplicate: OfficialDisclosureImportDuplicate
    classification: OfficialDisclosureImportClassification
    would_create_instrument: bool
    validation_warnings: list[str] = Field(default_factory=list)
    would_create: bool
    confirmed: Literal[False] = False


class OfficialDisclosureImportConfirmed(DisclosureSchema):
    normalized_url: str
    disclosure: DisclosureRead
    information_event_id: UUID
    instrument_created: bool
    validation_warnings: list[str] = Field(default_factory=list)
    confirmed: Literal[True] = True


class InformationEventRead(DisclosureSchema):
    id: UUID
    event_key: str
    instrument_id: UUID
    event_type: str
    normalized_claim: str
    first_seen_at: datetime
    last_seen_at: datetime
    latest_material_change_at: datetime | None
    lifecycle_status: LifecycleStatus
    verification_status: VerificationStatus
    source_count: int
    official_source_count: int
    news_reference_count: int = 0
    independent_origin_count: int = 0
    stale_reuse_count: int = 0
    latest_news_at: datetime | None = None
    latest_official_at: datetime | None = None
    changed_facts: list[dict[str, object]] = Field(default_factory=list)
    corrected_at: datetime | None = None
    denied_at: datetime | None = None
    current_summary: str | None
    material_change: bool


class InformationEventList(DisclosureSchema):
    items: list[InformationEventRead]
    total: int
    limit: int
    offset: int


class EventNewsReference(DisclosureSchema):
    id: UUID
    title: str
    source_name: str
    canonical_url: str
    published_at: datetime
    verification_status: VerificationStatus
    material_change: bool
    stale_reused: bool
    independent_origin: bool


class InformationEventDetail(InformationEventRead):
    related_instrument: InstrumentSummary | None = None
    official_references: list[DisclosureRead] = Field(default_factory=list)
    news_references: list[EventNewsReference] = Field(default_factory=list)
