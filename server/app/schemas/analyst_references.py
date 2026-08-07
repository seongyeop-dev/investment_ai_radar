from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystIngestMode,
    AnalystMappingConfidence,
    AnalystPublisherType,
    AnalystRelationType,
    AnalystTranslationStatus,
    AnalystUserState,
)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class AnalystReferenceSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class AnalystReferenceCoverageRead(AnalystReferenceSchema):
    id: UUID
    analyst_reference_id: UUID
    portfolio_item_id: UUID
    relation_type: AnalystRelationType
    mapping_confidence: AnalystMappingConfidence
    human_review_required: bool
    created_at: datetime


class AnalystReferenceRead(AnalystReferenceSchema):
    id: UUID
    source_id: UUID | None
    subscription_id: UUID | None
    provider_item_id: str | None
    ingest_mode: AnalystIngestMode
    user_state: AnalystUserState
    discovered_at: datetime
    publisher_name: str
    publisher_type: AnalystPublisherType
    title: str
    analyst_name: str | None
    published_at: datetime
    canonical_url: str
    access_type: AnalystAccessType
    document_type: AnalystDocumentType
    publisher_rating_raw: str | None
    publisher_target_price_raw: str | None
    target_currency: str | None
    public_abstract: str | None
    source_language: str
    translated_title_ko: str | None
    translated_abstract_ko: str | None
    translation_status: AnalystTranslationStatus
    translation_provider: str | None
    translation_error: str | None
    translated_at: datetime | None
    source_retrieved_at: datetime | None
    source_fingerprint: str
    freshness_status: AnalystFreshnessStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime
    coverages: list[AnalystReferenceCoverageRead] = Field(default_factory=list)


class AnalystReferenceList(AnalystReferenceSchema):
    items: list[AnalystReferenceRead]
    total: int
    limit: int
    offset: int


class AnalystReferenceImportLinkRequest(AnalystReferenceSchema):
    source_url: str = Field(min_length=1, max_length=1000)
    publisher_name: str = Field(min_length=1, max_length=200)
    publisher_type: AnalystPublisherType
    title: str = Field(min_length=1, max_length=500)
    analyst_name: str | None = Field(default=None, max_length=200)
    published_at: datetime
    access_type: AnalystAccessType
    document_type: AnalystDocumentType
    publisher_rating_raw: str | None = Field(
        default=None,
        max_length=200,
    )
    publisher_target_price_raw: str | None = Field(
        default=None,
        max_length=200,
    )
    target_currency: str | None = Field(
        default=None,
        max_length=12,
    )
    public_abstract: str | None = Field(
        default=None,
        max_length=300,
    )
    portfolio_item_ids: list[UUID] = Field(min_length=1)
    confirm: bool = False

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        del cls
        normalized = value.strip()

        try:
            parsed = urlsplit(normalized)
            hostname = parsed.hostname
        except ValueError as exc:
            raise ValueError("source_url must be an absolute HTTP(S) URL") from exc

        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not hostname
            or any(character.isspace() for character in hostname)
        ):
            raise ValueError("source_url must be an absolute HTTP(S) URL")

        if parsed.username is not None or parsed.password is not None:
            raise ValueError("source_url must not include URL credentials")

        return normalized

    @field_validator("publisher_name", "title")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        del cls
        normalized = value.strip()

        if not normalized:
            raise ValueError("value must not be empty")

        return normalized

    @field_validator(
        "analyst_name",
        "publisher_rating_raw",
        "publisher_target_price_raw",
        "public_abstract",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        del cls

        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @field_validator("target_currency")
    @classmethod
    def normalize_target_currency(
        cls,
        value: str | None,
    ) -> str | None:
        del cls

        if value is None:
            return None

        normalized = value.strip().upper()
        return normalized or None

    @field_validator("published_at")
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        del cls

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must include timezone information")

        return value


class AnalystReferenceImportPortfolioItemRead(AnalystReferenceSchema):
    id: UUID
    symbol: str
    name: str
    market: str
    is_archived: bool


class AnalystReferenceImportDuplicateRead(AnalystReferenceSchema):
    canonical_url_duplicate: bool
    source_fingerprint_duplicate: bool
    canonical_url_reference_id: UUID | None = None
    source_fingerprint_reference_id: UUID | None = None


class AnalystReferenceImportLinkResultBase(AnalystReferenceSchema):
    normalized_url: str
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    portfolio_items: list[AnalystReferenceImportPortfolioItemRead]
    validation_warnings: list[str] = Field(default_factory=list)


class AnalystReferenceImportLinkPreview(AnalystReferenceImportLinkResultBase):
    duplicate: AnalystReferenceImportDuplicateRead
    would_create: bool
    confirmed: Literal[False] = False


class AnalystReferenceImportLinkConfirmed(AnalystReferenceImportLinkResultBase):
    reference: AnalystReferenceRead
    coverages: list[AnalystReferenceCoverageRead]
    confirmed: Literal[True] = True
