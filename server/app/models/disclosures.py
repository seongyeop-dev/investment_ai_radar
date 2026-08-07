from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.time import SystemClock
from app.database import Base
from app.models.contracts import VerificationStatus
from app.models.database import AssetType, Currency, SourceGrade, UTCDateTime


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return SystemClock().now()


def _enum(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        validate_strings=True,
        create_constraint=True,
    )


class InstrumentVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    DELISTED = "DELISTED"


class ProviderName(StrEnum):
    OPENDART = "OPENDART"
    SEC_EDGAR = "SEC_EDGAR"
    UPBIT = "UPBIT"
    BINANCE = "BINANCE"
    MANUAL = "MANUAL"
    SYSTEM_BASELINE = "SYSTEM_BASELINE"


class ProviderStatus(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    READY = "READY"
    RUNNING = "RUNNING"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    FAILED = "FAILED"
    ERROR = "ERROR"


class MappingStatus(StrEnum):
    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"
    UNRESOLVED = "UNRESOLVED"
    CONFLICTING = "CONFLICTING"
    UNSUPPORTED = "UNSUPPORTED"
    STALE = "STALE"


class MappingMatchMethod(StrEnum):
    EXACT_STOCK_CODE = "EXACT_STOCK_CODE"
    EXACT_TICKER_EXCHANGE = "EXACT_TICKER_EXCHANGE"
    EXACT_PROVIDER_SYMBOL = "EXACT_PROVIDER_SYMBOL"
    MANUAL_CONFIRMED = "MANUAL_CONFIRMED"
    NAME_CANDIDATE = "NAME_CANDIDATE"
    NONE = "NONE"


class LifecycleStatus(StrEnum):
    ACTIVE = "ACTIVE"
    UPDATED = "UPDATED"
    CORRECTED = "CORRECTED"
    DENIED = "DENIED"
    STALE = "STALE"
    ARCHIVED = "ARCHIVED"


class CollectionStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DRY_RUN = "DRY_RUN"


class CollectionRunType(StrEnum):
    INSTRUMENT_SYNC = "INSTRUMENT_SYNC"
    DISCLOSURE_SYNC = "DISCLOSURE_SYNC"
    RETENTION_CLEANUP = "RETENTION_CLEANUP"
    NEWS_SYNC = "NEWS_SYNC"
    BRIEFING_GENERATION = "BRIEFING_GENERATION"
    EMAIL_DELIVERY = "EMAIL_DELIVERY"
    USAGE_SNAPSHOT = "USAGE_SNAPSHOT"
    RADAR_CYCLE = "RADAR_CYCLE"


class SummaryStatus(StrEnum):
    NOT_GENERATED = "NOT_GENERATED"
    STRUCTURED = "STRUCTURED"


class NewsProviderType(StrEnum):
    RSS = "RSS"
    ATOM = "ATOM"
    OFFICIAL_IR_FEED = "OFFICIAL_IR_FEED"
    MANUAL_REFERENCE = "MANUAL_REFERENCE"
    DISABLED_DISCOVERY_PROVIDER = "DISABLED_DISCOVERY_PROVIDER"


class NewsSummaryStatus(StrEnum):
    NOT_GENERATED = "NOT_GENERATED"
    METADATA_ONLY = "METADATA_ONLY"
    RULE_BASED = "RULE_BASED"
    OFFICIAL_REFERENCE_BASED = "OFFICIAL_REFERENCE_BASED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class CertaintyLevel(StrEnum):
    CONFIRMED = "CONFIRMED"
    ANNOUNCED = "ANNOUNCED"
    PLANNED = "PLANNED"
    UNDER_REVIEW = "UNDER_REVIEW"
    PROPOSED = "PROPOSED"
    POSSIBLE = "POSSIBLE"
    SPECULATIVE = "SPECULATIVE"
    UNSUPPORTED = "UNSUPPORTED"


class InstrumentRecord(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        Index(
            "uq_instruments_active_market_symbol",
            "market",
            "canonical_symbol",
            unique=True,
            sqlite_where=text("active = 1"),
            postgresql_where=text("active = true"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    canonical_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    local_name: Mapped[str | None] = mapped_column(String(200))
    exchange: Mapped[str | None] = mapped_column(String(50))
    market: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(3), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        _enum(Currency, "instrument_currency"),
        nullable=False,
    )
    asset_type: Mapped[AssetType] = mapped_column(
        _enum(AssetType, "asset_type"),
        nullable=False,
        default=AssetType.UNKNOWN,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verification_status: Mapped[InstrumentVerificationStatus] = mapped_column(
        _enum(InstrumentVerificationStatus, "instrument_verification_status"),
        nullable=False,
        default=InstrumentVerificationStatus.UNVERIFIED,
    )
    verification_source: Mapped[str | None] = mapped_column(String(50))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delisted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    @validates("canonical_symbol", "market", "exchange", "country")
    def normalize_identifier(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if key in {"canonical_symbol", "market", "country"} and not normalized:
            raise ValueError(f"{key} must not be empty")
        return normalized


class InstrumentProviderMappingRecord(Base):
    __tablename__ = "instrument_provider_mappings"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_company_id",
            name="uq_instrument_mapping_provider_company",
        ),
        Index(
            "ix_instrument_mapping_provider_symbol",
            "provider",
            "provider_symbol",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider: Mapped[ProviderName] = mapped_column(
        _enum(ProviderName, "instrument_provider"),
        nullable=False,
    )
    provider_symbol: Mapped[str | None] = mapped_column(String(32))
    provider_company_id: Mapped[str] = mapped_column(String(80), nullable=False)
    cik: Mapped[str | None] = mapped_column(String(10))
    corp_code: Mapped[str | None] = mapped_column(String(8))
    stock_code: Mapped[str | None] = mapped_column(String(6))
    accession_prefix: Mapped[str | None] = mapped_column(String(40))
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    official_name: Mapped[str | None] = mapped_column(String(300))
    mapping_status: Mapped[MappingStatus] = mapped_column(
        _enum(MappingStatus, "instrument_mapping_status"),
        nullable=False,
        default=MappingStatus.VERIFIED,
    )
    match_method: Mapped[MappingMatchMethod] = mapped_column(
        _enum(MappingMatchMethod, "instrument_mapping_match_method"),
        nullable=False,
        default=MappingMatchMethod.NONE,
    )
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    conflict_reason: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    @validates("provider_symbol")
    def normalize_provider_symbol(self, key: str, value: str | None) -> str | None:
        del key
        return value.strip().upper() if value else None

    @validates("cik")
    def validate_cik(self, key: str, value: str | None) -> str | None:
        del key
        if value is not None and (len(value) != 10 or not value.isdigit()):
            raise ValueError("CIK must be a ten-digit string")
        return value

    @validates("corp_code")
    def validate_corp_code(self, key: str, value: str | None) -> str | None:
        del key
        if value is not None and (len(value) != 8 or not value.isdigit()):
            raise ValueError("corpCode must be an eight-digit string")
        return value

    @validates("stock_code")
    def validate_stock_code(self, key: str, value: str | None) -> str | None:
        del key
        if value is not None and (len(value) != 6 or not value.isdigit()):
            raise ValueError("stockCode must be a six-digit string")
        return value


class InformationEventRecord(Base):
    __tablename__ = "information_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_information_event_key"),
        Index("ix_information_events_instrument_last_seen", "instrument_id", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_claim: Mapped[str] = mapped_column(Text, nullable=False)
    claim_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    latest_material_change_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        _enum(LifecycleStatus, "event_lifecycle_status"),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        _enum(VerificationStatus, "event_verification_status"),
        nullable=False,
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    official_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    news_reference_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    independent_origin_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale_reuse_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_news_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    latest_official_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    changed_facts: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    corrected_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    denied_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    current_summary: Mapped[str | None] = mapped_column(String(2000))
    material_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )


class DisclosureRecord(Base):
    __tablename__ = "disclosure_records"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_document_id",
            name="uq_disclosure_provider_document",
        ),
        UniqueConstraint("official_url", name="uq_disclosure_official_url"),
        Index("ix_disclosures_instrument_published", "instrument_id", "published_at"),
        Index("ix_disclosures_accession", "provider", "accession_number"),
        Index("ix_disclosures_receipt", "provider", "receipt_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("information_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[ProviderName] = mapped_column(
        _enum(ProviderName, "disclosure_provider"),
        nullable=False,
    )
    provider_document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    accession_number: Mapped[str | None] = mapped_column(String(40))
    receipt_number: Mapped[str | None] = mapped_column(String(40))
    form_type: Mapped[str | None] = mapped_column(String(50))
    report_type: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    official_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verification_status: Mapped[VerificationStatus] = mapped_column(
        _enum(VerificationStatus, "disclosure_verification_status"),
        nullable=False,
    )
    source_grade: Mapped[SourceGrade] = mapped_column(
        _enum(SourceGrade, "disclosure_source_grade"),
        nullable=False,
    )
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(2000))
    summary_status: Mapped[SummaryStatus] = mapped_column(
        _enum(SummaryStatus, "summary_status"),
        nullable=False,
        default=SummaryStatus.NOT_GENERATED,
    )
    key_facts: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    material_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correction_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("disclosure_records.id", ondelete="RESTRICT")
    )
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        _enum(LifecycleStatus, "disclosure_lifecycle_status"),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )


class EvidenceItemRecord(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("evidence_hash", name="uq_evidence_hash"),
        Index("ix_evidence_event_created", "event_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("information_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    disclosure_id: Mapped[str | None] = mapped_column(
        ForeignKey("disclosure_records.id", ondelete="RESTRICT")
    )
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"))
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    independent_origin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    contradicts_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)


class CollectionRunRecord(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (Index("ix_collection_runs_provider_started", "provider", "started_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    provider: Mapped[ProviderName] = mapped_column(
        _enum(ProviderName, "collection_provider"),
        nullable=False,
    )
    run_type: Mapped[CollectionRunType] = mapped_column(
        _enum(CollectionRunType, "collection_run_type"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[CollectionStatus] = mapped_column(
        _enum(CollectionStatus, "collection_status"),
        nullable=False,
    )
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scheduled_for: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_milliseconds: Mapped[int | None] = mapped_column(Integer)
    delay_milliseconds: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool | None] = mapped_column(Boolean)
    partial_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    material_change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retention_deleted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_compute_seconds: Mapped[int | None] = mapped_column(Integer)
    cursor_before: Mapped[str | None] = mapped_column(String(500))
    cursor_after: Mapped[str | None] = mapped_column(String(500))
    error_summary: Mapped[str | None] = mapped_column(String(1000))
    result_details: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)


class ProviderCursorRecord(Base):
    __tablename__ = "provider_cursors"

    provider: Mapped[ProviderName] = mapped_column(
        _enum(ProviderName, "cursor_provider"),
        primary_key=True,
    )
    scope: Mapped[str] = mapped_column(String(100), primary_key=True)
    cursor_value: Mapped[str | None] = mapped_column(String(500))
    last_successful_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    overlap_window_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )


class TemporaryDocumentRecord(Base):
    __tablename__ = "temporary_documents"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_document_id",
            name="uq_temporary_document_provider_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    provider: Mapped[ProviderName] = mapped_column(
        _enum(ProviderName, "temporary_document_provider"),
        nullable=False,
    )
    provider_document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)


class NewsReferenceRecord(Base):
    __tablename__ = "news_references"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_item_id",
            name="uq_news_provider_item",
        ),
        UniqueConstraint(
            "canonical_url_hash",
            name="uq_news_canonical_url_hash",
        ),
        CheckConstraint(
            "trust_score >= 0 AND trust_score <= 100",
            name="ck_news_trust_score_range",
        ),
        Index(
            "ix_news_instrument_published",
            "instrument_id",
            "published_at",
        ),
        Index("ix_news_claim_fingerprint", "claim_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    portfolio_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("portfolio_items.id", ondelete="SET NULL")
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[NewsProviderType] = mapped_column(
        _enum(NewsProviderType, "news_provider_type"), nullable=False
    )
    provider_item_id: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(253), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    canonical_url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    original_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="und")
    snippet: Mapped[str | None] = mapped_column(String(1000))
    short_summary: Mapped[str | None] = mapped_column(String(1000))
    summary_status: Mapped[NewsSummaryStatus] = mapped_column(
        _enum(NewsSummaryStatus, "news_summary_status"), nullable=False
    )
    primary_claim: Mapped[str] = mapped_column(String(2000), nullable=False)
    claim_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        _enum(VerificationStatus, "news_verification_status"), nullable=False
    )
    source_grade: Mapped[SourceGrade] = mapped_column(
        _enum(SourceGrade, "news_source_grade"), nullable=False
    )
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False)
    certainty_level: Mapped[CertaintyLevel] = mapped_column(
        _enum(CertaintyLevel, "news_certainty_level"), nullable=False
    )
    independent_origin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    original_origin_key: Mapped[str] = mapped_column(String(500), nullable=False)
    duplicate_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("news_references.id", ondelete="RESTRICT")
    )
    information_event_id: Mapped[str] = mapped_column(
        ForeignKey("information_events.id", ondelete="RESTRICT"), nullable=False
    )
    material_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stale_reused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        _enum(LifecycleStatus, "news_lifecycle_status"), nullable=False
    )
    official_reference_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    changed_facts: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=_now, onupdate=_now, nullable=False
    )


class NewsClaimRecord(Base):
    __tablename__ = "news_claims"
    __table_args__ = (Index("ix_news_claims_fingerprint", "claim_fingerprint"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    news_reference_id: Mapped[str] = mapped_column(
        ForeignKey("news_references.id", ondelete="RESTRICT"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("information_events.id", ondelete="RESTRICT"), nullable=False
    )
    claim_type: Mapped[str] = mapped_column(String(80), nullable=False)
    claim_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    normalized_claim: Mapped[str] = mapped_column(String(2000), nullable=False)
    claim_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    certainty_level: Mapped[CertaintyLevel] = mapped_column(
        _enum(CertaintyLevel, "news_claim_certainty_level"), nullable=False
    )
    supports_official_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("disclosure_records.id", ondelete="RESTRICT")
    )
    contradicts_official_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("disclosure_records.id", ondelete="RESTRICT")
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        _enum(VerificationStatus, "news_claim_verification_status"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
