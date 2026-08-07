from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.time import SystemClock
from app.database import Base
from app.models.database import UTCDateTime


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


class AnalystPublisherType(StrEnum):
    BROKER = "BROKER"
    RESEARCH_HOUSE = "RESEARCH_HOUSE"
    FINANCIAL_MEDIA = "FINANCIAL_MEDIA"
    INSTITUTION = "INSTITUTION"
    OTHER = "OTHER"


class AnalystAccessType(StrEnum):
    PUBLIC = "PUBLIC"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    PAYWALLED = "PAYWALLED"
    UNKNOWN = "UNKNOWN"


class AnalystDocumentType(StrEnum):
    REPORT = "REPORT"
    COMMENTARY = "COMMENTARY"
    INTERVIEW = "INTERVIEW"
    CONSENSUS = "CONSENSUS"
    OTHER = "OTHER"


class AnalystFreshnessStatus(StrEnum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class AnalystRelationType(StrEnum):
    PRIMARY = "PRIMARY"
    MENTIONED = "MENTIONED"


class AnalystMappingConfidence(StrEnum):
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class AnalystIngestMode(StrEnum):
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"


class AnalystUserState(StrEnum):
    NEW = "NEW"
    READ = "READ"
    ARCHIVED = "ARCHIVED"
    HIDDEN = "HIDDEN"


class AnalystTranslationStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NOT_NEEDED = "NOT_NEEDED"


class AnalystReferenceRecord(Base):
    __tablename__ = "analyst_references"
    __table_args__ = (
        UniqueConstraint(
            "canonical_url",
            name="uq_analyst_reference_canonical_url",
        ),
        UniqueConstraint(
            "source_fingerprint",
            name="uq_analyst_reference_source_fingerprint",
        ),
        UniqueConstraint(
            "source_id",
            "provider_item_id",
            name="uq_analyst_reference_source_provider_item",
        ),
        CheckConstraint(
            "("
            "ingest_mode = 'MANUAL' "
            "AND source_id IS NULL "
            "AND subscription_id IS NULL "
            "AND provider_item_id IS NULL"
            ") OR ("
            "ingest_mode = 'AUTOMATIC' "
            "AND source_id IS NOT NULL "
            "AND subscription_id IS NOT NULL "
            "AND provider_item_id IS NOT NULL"
            ")",
            name="ck_analyst_reference_ingest_origin",
        ),
        CheckConstraint(
            "length(title) > 0",
            name="ck_analyst_reference_title_not_empty",
        ),
        CheckConstraint(
            "public_abstract IS NULL OR length(public_abstract) <= 300",
            name="ck_analyst_reference_abstract_length",
        ),
        CheckConstraint(
            "translated_title_ko IS NULL OR length(translated_title_ko) <= 500",
            name="ck_analyst_reference_translated_title_length",
        ),
        CheckConstraint(
            "translated_abstract_ko IS NULL OR length(translated_abstract_ko) <= 300",
            name="ck_analyst_reference_translated_abstract_length",
        ),
        Index(
            "ix_analyst_references_translation_status",
            "translation_status",
        ),
        Index(
            "ix_analyst_references_published",
            "published_at",
        ),
        Index(
            "ix_analyst_references_publisher_published",
            "publisher_name",
            "published_at",
        ),
        Index(
            "ix_analyst_references_active_freshness",
            "is_active",
            "freshness_status",
        ),
        Index(
            "ix_analyst_references_subscription_published",
            "subscription_id",
            "published_at",
        ),
        Index(
            "ix_analyst_references_state_published",
            "user_state",
            "published_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_id,
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "sources.id",
            ondelete="RESTRICT",
        ),
    )
    subscription_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "reference_subscriptions.id",
            ondelete="RESTRICT",
        ),
    )
    provider_item_id: Mapped[str | None] = mapped_column(
        String(300),
    )
    ingest_mode: Mapped[AnalystIngestMode] = mapped_column(
        _enum(
            AnalystIngestMode,
            "analyst_ingest_mode",
        ),
        nullable=False,
        default=AnalystIngestMode.MANUAL,
    )
    user_state: Mapped[AnalystUserState] = mapped_column(
        _enum(
            AnalystUserState,
            "analyst_user_state",
        ),
        nullable=False,
        default=AnalystUserState.NEW,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )
    publisher_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    publisher_type: Mapped[AnalystPublisherType] = mapped_column(
        _enum(AnalystPublisherType, "analyst_publisher_type"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    analyst_name: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
    )
    canonical_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    access_type: Mapped[AnalystAccessType] = mapped_column(
        _enum(AnalystAccessType, "analyst_access_type"),
        nullable=False,
        default=AnalystAccessType.UNKNOWN,
    )
    document_type: Mapped[AnalystDocumentType] = mapped_column(
        _enum(AnalystDocumentType, "analyst_document_type"),
        nullable=False,
        default=AnalystDocumentType.OTHER,
    )
    publisher_rating_raw: Mapped[str | None] = mapped_column(String(200))
    publisher_target_price_raw: Mapped[str | None] = mapped_column(String(200))
    target_currency: Mapped[str | None] = mapped_column(String(12))
    public_abstract: Mapped[str | None] = mapped_column(String(300))
    source_language: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        default="und",
    )
    translated_title_ko: Mapped[str | None] = mapped_column(
        String(500),
    )
    translated_abstract_ko: Mapped[str | None] = mapped_column(
        String(300),
    )
    translation_status: Mapped[AnalystTranslationStatus] = mapped_column(
        _enum(
            AnalystTranslationStatus,
            "analyst_translation_status",
        ),
        nullable=False,
        default=AnalystTranslationStatus.NOT_REQUESTED,
    )
    translation_provider: Mapped[str | None] = mapped_column(
        String(100),
    )
    translation_error: Mapped[str | None] = mapped_column(
        String(500),
    )
    translated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
    )
    source_retrieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    freshness_status: Mapped[AnalystFreshnessStatus] = mapped_column(
        _enum(AnalystFreshnessStatus, "analyst_freshness_status"),
        nullable=False,
        default=AnalystFreshnessStatus.UNKNOWN,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    @validates("provider_item_id")
    def normalize_provider_item_id(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key

        if value is None:
            return None

        normalized = " ".join(value.split())

        if len(normalized) > 300:
            raise ValueError("provider_item_id must not exceed 300 characters")

        return normalized or None

    @validates("publisher_name", "title")
    def validate_required_text(self, key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{key} must not be empty")
        return normalized

    @validates("canonical_url")
    def validate_canonical_url(self, key: str, value: str) -> str:
        del key
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("canonical_url must be an absolute HTTP(S) URL")
        return normalized

    @validates("source_fingerprint")
    def validate_source_fingerprint(self, key: str, value: str) -> str:
        del key
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("source_fingerprint must be a 64-character SHA-256 hex value")
        return normalized

    @validates("public_abstract")
    def validate_public_abstract(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) > 300:
            raise ValueError("public_abstract must not exceed 300 characters")
        return normalized or None

    @validates("source_language")
    def normalize_source_language(
        self,
        key: str,
        value: str,
    ) -> str:
        del key
        normalized = value.strip().lower()

        if not normalized:
            return "und"

        if len(normalized) > 12:
            raise ValueError("source_language must not exceed 12 characters")

        return normalized

    @validates("translated_title_ko")
    def validate_translated_title_ko(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key

        if value is None:
            return None

        normalized = value.strip()

        if len(normalized) > 500:
            raise ValueError("translated_title_ko must not exceed 500 characters")

        return normalized or None

    @validates("translated_abstract_ko")
    def validate_translated_abstract_ko(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key

        if value is None:
            return None

        normalized = value.strip()

        if len(normalized) > 300:
            raise ValueError("translated_abstract_ko must not exceed 300 characters")

        return normalized or None

    @validates("translation_provider")
    def validate_translation_provider(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key

        if value is None:
            return None

        normalized = value.strip()

        if len(normalized) > 100:
            raise ValueError("translation_provider must not exceed 100 characters")

        return normalized or None

    @validates("translation_error")
    def validate_translation_error(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key

        if value is None:
            return None

        normalized = value.strip()

        if len(normalized) > 500:
            raise ValueError("translation_error must not exceed 500 characters")

        return normalized or None

    @validates("target_currency")
    def normalize_target_currency(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key
        return value.strip().upper() if value and value.strip() else None


class AnalystReferenceCoverageRecord(Base):
    __tablename__ = "analyst_reference_coverages"
    __table_args__ = (
        UniqueConstraint(
            "analyst_reference_id",
            "portfolio_item_id",
            name="uq_analyst_reference_coverage_portfolio",
        ),
        Index(
            "ix_analyst_reference_coverages_portfolio_created",
            "portfolio_item_id",
            "created_at",
        ),
        Index(
            "ix_analyst_reference_coverages_reference",
            "analyst_reference_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_id,
    )
    analyst_reference_id: Mapped[str] = mapped_column(
        ForeignKey(
            "analyst_references.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    portfolio_item_id: Mapped[str] = mapped_column(
        ForeignKey(
            "portfolio_items.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    relation_type: Mapped[AnalystRelationType] = mapped_column(
        _enum(AnalystRelationType, "analyst_relation_type"),
        nullable=False,
        default=AnalystRelationType.PRIMARY,
    )
    mapping_confidence: Mapped[AnalystMappingConfidence] = mapped_column(
        _enum(
            AnalystMappingConfidence,
            "analyst_mapping_confidence",
        ),
        nullable=False,
        default=AnalystMappingConfidence.NEEDS_REVIEW,
    )
    human_review_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )


class ReferenceDiscoveryCandidateStatus(StrEnum):
    DATE_UNVERIFIED = "DATE_UNVERIFIED"
    DATE_VERIFIED = "DATE_VERIFIED"
    PROMOTED = "PROMOTED"
    DISMISSED = "DISMISSED"


class ReferenceDiscoveryCandidateRecord(Base):
    __tablename__ = "reference_discovery_candidates"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "provider_item_id",
            name=("uq_reference_discovery_candidate_source_provider_item"),
        ),
        CheckConstraint(
            "length(title) > 0",
            name=("ck_reference_discovery_candidate_title_not_empty"),
        ),
        CheckConstraint(
            "seen_count >= 1",
            name=("ck_reference_discovery_candidate_seen_count_positive"),
        ),
        CheckConstraint(
            "public_abstract IS NULL OR length(public_abstract) <= 300",
            name=("ck_reference_discovery_candidate_abstract_length"),
        ),
        Index(
            "ix_reference_discovery_candidates_status_last_seen",
            "verification_status",
            "last_seen_at",
        ),
        Index(
            "ix_reference_discovery_candidates_subscription_last_seen",
            "subscription_id",
            "last_seen_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_id,
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey(
            "sources.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    subscription_id: Mapped[str] = mapped_column(
        ForeignKey(
            "reference_subscriptions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    provider_item_id: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    publisher_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    analyst_name: Mapped[str | None] = mapped_column(
        String(200),
    )
    canonical_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
    )
    verification_status: Mapped[ReferenceDiscoveryCandidateStatus] = mapped_column(
        _enum(
            ReferenceDiscoveryCandidateStatus,
            "reference_discovery_candidate_status",
        ),
        nullable=False,
        default=(ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED),
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )
    seen_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    public_abstract: Mapped[str | None] = mapped_column(
        String(300),
    )
    publisher_type: Mapped[AnalystPublisherType] = mapped_column(
        _enum(
            AnalystPublisherType,
            "reference_discovery_candidate_publisher_type",
        ),
        nullable=False,
        default=AnalystPublisherType.INSTITUTION,
    )
    access_type: Mapped[AnalystAccessType] = mapped_column(
        _enum(
            AnalystAccessType,
            "reference_discovery_candidate_access_type",
        ),
        nullable=False,
        default=AnalystAccessType.PUBLIC,
    )
    document_type: Mapped[AnalystDocumentType] = mapped_column(
        _enum(
            AnalystDocumentType,
            "reference_discovery_candidate_document_type",
        ),
        nullable=False,
        default=AnalystDocumentType.OTHER,
    )
    promoted_reference_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "analyst_references.id",
            ondelete="RESTRICT",
        ),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    @validates(
        "provider_item_id",
        "publisher_name",
        "title",
    )
    def validate_required_text(
        self,
        key: str,
        value: str,
    ) -> str:
        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError(f"{key} must not be empty")

        limits = {
            "provider_item_id": 300,
            "publisher_name": 200,
            "title": 500,
        }

        if len(normalized) > limits[key]:
            raise ValueError(f"{key} must not exceed {limits[key]} characters")

        return normalized

    @validates("analyst_name")
    def validate_analyst_name(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        del key

        if value is None:
            return None

        normalized = " ".join(value.split())

        if len(normalized) > 200:
            raise ValueError("analyst_name must not exceed 200 characters")

        return normalized or None

    @validates("canonical_url")
    def validate_candidate_url(
        self,
        key: str,
        value: str,
    ) -> str:
        del key

        normalized = value.strip()
        parsed = urlsplit(normalized)

        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("canonical_url must be an absolute HTTPS URL")

        return normalized


class ReferenceDiscoveryCandidateReviewAction(StrEnum):
    VERIFY_DATE = "VERIFY_DATE"
    PROMOTE = "PROMOTE"
    DISMISS = "DISMISS"


class ReferenceDiscoveryCandidateReviewRecord(Base):
    __tablename__ = "reference_discovery_candidate_review_history"
    __table_args__ = (
        CheckConstraint(
            "action IN ('VERIFY_DATE', 'PROMOTE', 'DISMISS')",
            name=("ck_reference_candidate_review_action"),
        ),
        CheckConstraint(
            "previous_status IN ('DATE_UNVERIFIED', 'DATE_VERIFIED', 'PROMOTED', 'DISMISSED')",
            name=("ck_reference_candidate_review_previous_status"),
        ),
        CheckConstraint(
            "new_status IN ('DATE_UNVERIFIED', 'DATE_VERIFIED', 'PROMOTED', 'DISMISSED')",
            name=("ck_reference_candidate_review_new_status"),
        ),
        CheckConstraint(
            "reason IS NULL OR length(reason) <= 1000",
            name=("ck_reference_candidate_review_reason_length"),
        ),
        CheckConstraint(
            "("
            "action = 'VERIFY_DATE' "
            "AND verified_published_at IS NOT NULL "
            "AND promoted_reference_id IS NULL "
            "AND new_status = 'DATE_VERIFIED'"
            ") OR ("
            "action = 'PROMOTE' "
            "AND verified_published_at IS NOT NULL "
            "AND promoted_reference_id IS NOT NULL "
            "AND new_status = 'PROMOTED'"
            ") OR ("
            "action = 'DISMISS' "
            "AND promoted_reference_id IS NULL "
            "AND new_status = 'DISMISSED'"
            ")",
            name=("ck_reference_candidate_review_action_payload"),
        ),
        Index(
            "ix_reference_candidate_review_candidate_created",
            "candidate_id",
            "created_at",
        ),
        Index(
            "ix_reference_candidate_review_action_created",
            "action",
            "created_at",
        ),
        Index(
            "ix_reference_candidate_review_promoted_reference",
            "promoted_reference_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_id,
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey(
            "reference_discovery_candidates.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    action: Mapped[ReferenceDiscoveryCandidateReviewAction] = mapped_column(
        _enum(
            ReferenceDiscoveryCandidateReviewAction,
            "reference_discovery_candidate_review_action",
        ),
        nullable=False,
    )
    previous_status: Mapped[ReferenceDiscoveryCandidateStatus] = mapped_column(
        _enum(
            ReferenceDiscoveryCandidateStatus,
            "reference_candidate_review_previous_status",
        ),
        nullable=False,
    )
    new_status: Mapped[ReferenceDiscoveryCandidateStatus] = mapped_column(
        _enum(
            ReferenceDiscoveryCandidateStatus,
            "reference_candidate_review_new_status",
        ),
        nullable=False,
    )
    verified_published_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
    )
    promoted_reference_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "analyst_references.id",
            ondelete="RESTRICT",
        ),
    )
    reason: Mapped[str | None] = mapped_column(
        String(1000),
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )
