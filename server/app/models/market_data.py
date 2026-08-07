from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import SystemClock
from app.database import Base
from app.models.database import PreciseDecimal, UTCDateTime


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return SystemClock().now()


class QuoteFreshnessStatus(StrEnum):
    LIVE = "LIVE"
    RECENT = "RECENT"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class QuoteSourceStatus(StrEnum):
    READY = "READY"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    FAILED = "FAILED"


class QuoteSnapshotRecord(Base):
    __tablename__ = "quote_snapshots"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_quote_snapshot_fingerprint"),
        Index(
            "ix_quote_latest_provider_instrument",
            "provider",
            "instrument_id",
            "fetched_at",
        ),
        CheckConstraint("price > 0", name="ck_quote_snapshot_positive_price"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    instrument_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    provider_event_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_status: Mapped[str] = mapped_column(String(30), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_now)


class ProviderSyncStateRecord(Base):
    __tablename__ = "provider_sync_states"

    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    capability: Mapped[str] = mapped_column(String(40), primary_key=True)
    configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_now, onupdate=_now
    )


class MarketSessionCacheRecord(Base):
    __tablename__ = "market_session_cache"
    __table_args__ = (
        UniqueConstraint("market", "session_date", name="uq_market_session_cache"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    market: Mapped[str] = mapped_column(String(20), nullable=False)
    session_date: Mapped[str] = mapped_column(String(10), nullable=False)
    market_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    open_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    close_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    holiday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    early_close: Mapped[bool] = mapped_column(Boolean, nullable=False)
    schedule_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    library_version: Mapped[str] = mapped_column(String(30), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
