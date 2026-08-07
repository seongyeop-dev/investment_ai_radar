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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import SystemClock
from app.database import Base
from app.models.contracts import VerificationStatus
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


class BriefingType(StrEnum):
    CHANGE_BRIEFING = "CHANGE_BRIEFING"
    KRX_PRE_OPEN = "KRX_PRE_OPEN"
    KRX_POST_CLOSE = "KRX_POST_CLOSE"
    NASDAQ_PRE_OPEN = "NASDAQ_PRE_OPEN"
    NASDAQ_POST_CLOSE = "NASDAQ_POST_CLOSE"
    DAILY_DIGEST = "DAILY_DIGEST"
    CORRECTION_NOTICE = "CORRECTION_NOTICE"
    PROVIDER_HEALTH_NOTICE = "PROVIDER_HEALTH_NOTICE"
    MANUAL_PREVIEW = "MANUAL_PREVIEW"


class BriefingStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    SKIPPED_NO_CHANGE = "SKIPPED_NO_CHANGE"
    SENT = "SENT"
    PARTIALLY_SENT = "PARTIALLY_SENT"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class NotificationProvider(StrEnum):
    DISABLED = "DISABLED"
    SMTP = "SMTP"
    RESEND = "RESEND"
    FAKE = "FAKE"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DUPLICATE_BLOCKED = "DUPLICATE_BLOCKED"


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    ESTIMATED = "ESTIMATED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class OperatingMode(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    SAVING = "SAVING"
    MINIMAL = "MINIMAL"
    PAUSED = "PAUSED"


class BriefingRecord(Base):
    __tablename__ = "briefing_records"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_briefing_idempotency_key"),
        Index("ix_briefings_generated_status", "generated_at", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    briefing_type: Mapped[BriefingType] = mapped_column(
        _enum(BriefingType, "briefing_type"), nullable=False
    )
    status: Mapped[BriefingStatus] = mapped_column(
        _enum(BriefingStatus, "briefing_status"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    period_end: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    compact_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    material_change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    denial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    official_confirmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_verification_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    related_instrument_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=_now, onupdate=_now, nullable=False
    )


class BriefingItemRecord(Base):
    __tablename__ = "briefing_items"
    __table_args__ = (
        UniqueConstraint("state_fingerprint", name="uq_briefing_item_state"),
        Index("ix_briefing_items_briefing_priority", "briefing_id", "priority"),
        CheckConstraint(
            "trust_score >= 0 AND trust_score <= 100",
            name="ck_briefing_item_trust_score",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    briefing_id: Mapped[str] = mapped_column(
        ForeignKey("briefing_records.id", ondelete="CASCADE"), nullable=False
    )
    information_event_id: Mapped[str] = mapped_column(
        ForeignKey("information_events.id", ondelete="RESTRICT"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    short_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        _enum(VerificationStatus, "briefing_verification_status"), nullable=False
    )
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False)
    material_change: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_facts: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    source_links: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    official_reference_links: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)


class NotificationDeliveryRecord(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_delivery_idempotency_key"),
        Index("ix_delivery_status_attempted", "status", "attempted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    briefing_id: Mapped[str] = mapped_column(
        ForeignKey("briefing_records.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[NotificationProvider] = mapped_column(
        _enum(NotificationProvider, "notification_provider"), nullable=False
    )
    recipient_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[DeliveryStatus] = mapped_column(
        _enum(DeliveryStatus, "delivery_status"), nullable=False
    )
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=_now, onupdate=_now, nullable=False
    )


class NotificationPreferenceRecord(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(
            "daily_digest_hour >= 0 AND daily_digest_hour <= 23",
            name="ck_notification_daily_hour",
        ),
        CheckConstraint(
            "minimum_priority >= 0 AND minimum_priority <= 100",
            name="ck_notification_minimum_priority",
        ),
        CheckConstraint(
            "krx_pre_open_offset_minutes >= 0 AND krx_pre_open_offset_minutes <= 240",
            name="ck_notification_krx_pre_offset",
        ),
        CheckConstraint(
            "krx_post_close_offset_minutes >= 0 AND krx_post_close_offset_minutes <= 240",
            name="ck_notification_krx_post_offset",
        ),
        CheckConstraint(
            "nasdaq_pre_open_offset_minutes >= 0 AND nasdaq_pre_open_offset_minutes <= 240",
            name="ck_notification_nasdaq_pre_offset",
        ),
        CheckConstraint(
            "nasdaq_post_close_offset_minutes >= 0 AND nasdaq_post_close_offset_minutes <= 240",
            name="ck_notification_nasdaq_post_offset",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hourly_change_briefing_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    daily_digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    krx_pre_open_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    krx_post_close_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nasdaq_pre_open_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    nasdaq_post_close_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    immediate_material_change_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    correction_notice_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    provider_failure_notice_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Seoul")
    daily_digest_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    minimum_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    include_watchlist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_reentry_watch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    include_sold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    send_no_material_change_briefing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    krx_pre_open_offset_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=40
    )
    krx_post_close_offset_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    nasdaq_pre_open_offset_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    nasdaq_post_close_offset_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=_now, onupdate=_now, nullable=False
    )


class UsageSnapshotRecord(Base):
    __tablename__ = "usage_snapshots"
    __table_args__ = (Index("ix_usage_period_collected", "period", "collected_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    action_minutes_availability: Mapped[Availability] = mapped_column(
        _enum(Availability, "action_minutes_availability"), nullable=False
    )
    provider_reported_action_minutes: Mapped[int | None] = mapped_column(Integer)
    locally_estimated_compute_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    database_bytes_availability: Mapped[Availability] = mapped_column(
        _enum(Availability, "database_bytes_availability"), nullable=False
    )
    database_bytes: Mapped[int | None] = mapped_column(Integer)
    email_count_availability: Mapped[Availability] = mapped_column(
        _enum(Availability, "email_count_availability"), nullable=False
    )
    email_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collection_success_rate: Mapped[int | None] = mapped_column(Integer)
    scheduled_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delayed_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    operating_mode: Mapped[OperatingMode] = mapped_column(
        _enum(OperatingMode, "operating_mode"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
