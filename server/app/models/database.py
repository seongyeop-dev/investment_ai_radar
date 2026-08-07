from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.types import DateTime, TypeDecorator

from app.core.time import SystemClock, require_aware_utc, restore_utc
from app.database import Base


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


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        return require_aware_utc(value) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return restore_utc(value) if value is not None else None


class PreciseDecimal(TypeDecorator[Decimal]):
    """Use PostgreSQL NUMERIC and lossless text-backed Decimal on SQLite."""

    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int, scale: int) -> None:
        super().__init__()
        self.precision = precision
        self.scale = scale

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(80))
        return dialect.type_descriptor(Numeric(self.precision, self.scale))

    def process_bind_param(self, value: Decimal | None, dialect: Any) -> Decimal | str | None:
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("float is not allowed for Decimal fields")
        decimal_value = value if isinstance(value, Decimal) else Decimal(value)
        if dialect.name == "sqlite":
            return format(decimal_value, "f")
        return decimal_value

    def process_result_value(self, value: Any, dialect: Any) -> Decimal | None:
        del dialect
        return Decimal(str(value)) if value is not None else None


class HoldingStatus(StrEnum):
    HOLDING = "HOLDING"
    WATCHLIST = "WATCHLIST"
    SOLD = "SOLD"
    REENTRY_WATCH = "REENTRY_WATCH"


class InvestmentHorizon(StrEnum):
    SCALP = "SCALP"
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"
    UNSET = "UNSET"


class Currency(StrEnum):
    KRW = "KRW"
    USD = "USD"
    USDT = "USDT"
    OTHER = "OTHER"


class AssetType(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    ADR = "ADR"
    CRYPTO = "CRYPTO"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"
    FX = "FX"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class SourceGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class RecommendationMode(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"
    UNSET = "UNSET"


class RiskStyle(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"
    CUSTOM = "CUSTOM"


class RiskProfileSource(StrEnum):
    CUSTOM = "CUSTOM"
    DATA_ASSISTED = "DATA_ASSISTED"


class PrimaryGoal(StrEnum):
    CAPITAL_PRESERVATION = "CAPITAL_PRESERVATION"
    INCOME = "INCOME"
    BALANCED_GROWTH = "BALANCED_GROWTH"
    GROWTH = "GROWTH"
    CUSTOM = "CUSTOM"


class AveragingDownPolicy(StrEnum):
    DISABLED = "DISABLED"
    CONDITIONAL = "CONDITIONAL"
    ALLOWED = "ALLOWED"


class SaleTransactionType(StrEnum):
    PARTIAL_SALE = "PARTIAL_SALE"
    FULL_SALE = "FULL_SALE"
    HISTORICAL_SALE = "HISTORICAL_SALE"


class SaleTransactionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    VOIDED = "VOIDED"


class PositionStatus(StrEnum):
    EMPTY = "EMPTY"
    HOLDING = "HOLDING"
    CLOSED = "CLOSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class TrackingStatus(StrEnum):
    NONE = "NONE"
    WATCHLIST = "WATCHLIST"
    REENTRY_WATCH = "REENTRY_WATCH"


class TransactionSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class PositionTransactionType(StrEnum):
    OPENING_BALANCE = "OPENING_BALANCE"
    NORMAL = "NORMAL"
    HISTORICAL_IMPORT = "HISTORICAL_IMPORT"


class TransactionSourceType(StrEnum):
    USER_ENTRY = "USER_ENTRY"
    MIGRATED_SNAPSHOT = "MIGRATED_SNAPSHOT"
    MIGRATED_SALE = "MIGRATED_SALE"
    HISTORICAL_IMPORT = "HISTORICAL_IMPORT"


class PositionTransactionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    VOIDED = "VOIDED"


class PortfolioItemRecord(Base):
    __tablename__ = "portfolio_items"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('EQUITY', 'ETF', 'ADR', 'CRYPTO', 'OTHER')",
            name="portfolio_asset_type",
        ),
        CheckConstraint(
            "CAST(quantity AS NUMERIC) >= 0",
            name="ck_portfolio_quantity_nonnegative",
        ),
        CheckConstraint(
            "average_price IS NULL OR CAST(average_price AS NUMERIC) >= 0",
            name="ck_portfolio_average_price_nonnegative",
        ),
        CheckConstraint(
            "holding_status != 'HOLDING' OR CAST(quantity AS NUMERIC) > 0",
            name="ck_portfolio_holding_positive_quantity",
        ),
        CheckConstraint(
            "target_allocation IS NULL OR "
            "(CAST(target_allocation AS NUMERIC) >= 0 "
            "AND CAST(target_allocation AS NUMERIC) <= 100)",
            name="ck_portfolio_target_allocation_range",
        ),
        CheckConstraint(
            "max_loss_percent IS NULL OR "
            "(CAST(max_loss_percent AS NUMERIC) >= 0 "
            "AND CAST(max_loss_percent AS NUMERIC) <= 100)",
            name="ck_portfolio_max_loss_range",
        ),
        CheckConstraint(
            "notes IS NULL OR length(notes) <= 4000",
            name="ck_portfolio_notes_length",
        ),
        Index(
            "uq_portfolio_items_active_market_symbol",
            "market",
            "symbol",
            unique=True,
            sqlite_where=text("archived_at IS NULL"),
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    instrument_id: Mapped[str | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="SET NULL"),
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    market: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        _enum(Currency, "currency"),
        nullable=False,
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(
            AssetType,
            name="portfolio_asset_type_values",
            native_enum=False,
            validate_strings=True,
            create_constraint=False,
        ),
        nullable=False,
    )
    holding_status: Mapped[HoldingStatus] = mapped_column(
        _enum(HoldingStatus, "holding_status"),
        nullable=False,
    )
    position_status: Mapped[PositionStatus] = mapped_column(
        _enum(PositionStatus, "position_status"),
        nullable=False,
        default=PositionStatus.EMPTY,
    )
    tracking_status: Mapped[TrackingStatus] = mapped_column(
        _enum(TrackingStatus, "tracking_status"),
        nullable=False,
        default=TrackingStatus.NONE,
    )
    quantity: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    average_price: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    investment_horizon: Mapped[InvestmentHorizon] = mapped_column(
        _enum(InvestmentHorizon, "investment_horizon"),
        nullable=False,
        default=InvestmentHorizon.UNSET,
    )
    strategy: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    target_allocation: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    max_loss_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    notes: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    @validates("symbol", "market")
    def normalize_identifier(self, key: str, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError(f"{key} must not be empty")
        return normalized


class SaleTransactionRecord(Base):
    __tablename__ = "sale_transactions"
    __table_args__ = (
        CheckConstraint(
            "CAST(quantity AS NUMERIC) > 0",
            name="ck_sale_quantity_positive",
        ),
        CheckConstraint(
            "CAST(sale_price AS NUMERIC) > 0",
            name="ck_sale_price_positive",
        ),
        CheckConstraint(
            "CAST(purchase_average_price_snapshot AS NUMERIC) > 0",
            name="ck_sale_purchase_average_positive",
        ),
        CheckConstraint(
            "CAST(fee_amount AS NUMERIC) >= 0",
            name="ck_sale_fee_nonnegative",
        ),
        CheckConstraint(
            "CAST(tax_amount AS NUMERIC) >= 0",
            name="ck_sale_tax_nonnegative",
        ),
        CheckConstraint(
            "CAST(quantity_before AS NUMERIC) >= 0 AND CAST(quantity_after AS NUMERIC) >= 0",
            name="ck_sale_quantity_snapshots_nonnegative",
        ),
        CheckConstraint(
            "(transaction_type = 'HISTORICAL_SALE' AND historical_import = true) "
            "OR (transaction_type != 'HISTORICAL_SALE' AND historical_import = false)",
            name="ck_sale_historical_type",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' AND voided_at IS NULL AND void_reason IS NULL) "
            "OR (status = 'VOIDED' AND voided_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(void_reason) > 0)",
            name="ck_sale_void_state",
        ),
        Index(
            "ix_sale_transactions_portfolio_sold_at",
            "portfolio_item_id",
            "sold_at",
        ),
        Index(
            "ix_sale_transactions_portfolio_status_created",
            "portfolio_item_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    portfolio_item_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ledger_transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("position_transactions.id", ondelete="RESTRICT"),
        unique=True,
    )
    transaction_type: Mapped[SaleTransactionType] = mapped_column(
        _enum(SaleTransactionType, "sale_transaction_type"),
        nullable=False,
    )
    sold_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    purchase_average_price_snapshot: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    currency: Mapped[Currency] = mapped_column(
        _enum(Currency, "sale_currency"),
        nullable=False,
    )
    fee_amount: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    gross_proceeds: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    cost_basis: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    realized_return_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    quantity_before: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    quantity_after: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    historical_import: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(4000))
    status: Mapped[SaleTransactionStatus] = mapped_column(
        _enum(SaleTransactionStatus, "sale_transaction_status"),
        nullable=False,
    )
    voided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    void_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )


class PositionTransactionRecord(Base):
    __tablename__ = "position_transactions"
    __table_args__ = (
        CheckConstraint(
            "CAST(quantity AS NUMERIC) > 0",
            name="ck_position_transaction_quantity_positive",
        ),
        CheckConstraint(
            "CAST(unit_price AS NUMERIC) > 0",
            name="ck_position_transaction_price_positive",
        ),
        CheckConstraint(
            "CAST(fee_amount AS NUMERIC) >= 0 AND CAST(tax_amount AS NUMERIC) >= 0",
            name="ck_position_transaction_costs_nonnegative",
        ),
        CheckConstraint(
            "CAST(quantity_before AS NUMERIC) >= 0 AND CAST(quantity_after AS NUMERIC) >= 0",
            name="ck_position_transaction_snapshots_nonnegative",
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="ck_position_transaction_sequence_positive",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' AND voided_at IS NULL AND void_reason IS NULL) "
            "OR (status = 'VOIDED' AND voided_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(void_reason) > 0)",
            name="ck_position_transaction_void_state",
        ),
        UniqueConstraint(
            "portfolio_item_id",
            "idempotency_key",
            name="uq_position_transaction_portfolio_idempotency",
        ),
        Index(
            "ix_position_transactions_portfolio_traded",
            "portfolio_item_id",
            "traded_at",
            "created_at",
            "id",
        ),
        Index(
            "ix_position_transactions_portfolio_status",
            "portfolio_item_id",
            "status",
            "sequence_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    portfolio_item_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_side: Mapped[TransactionSide] = mapped_column(
        _enum(TransactionSide, "position_transaction_side"),
        nullable=False,
    )
    transaction_type: Mapped[PositionTransactionType] = mapped_column(
        _enum(PositionTransactionType, "position_transaction_type"),
        nullable=False,
    )
    traded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    currency: Mapped[Currency] = mapped_column(
        _enum(Currency, "position_transaction_currency"),
        nullable=False,
    )
    fee_amount: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    gross_amount: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    quantity_before: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    quantity_after: Mapped[Decimal] = mapped_column(
        PreciseDecimal(38, 18),
        nullable=False,
    )
    average_price_before: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    average_price_after: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    realized_pnl: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    realized_return_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[TransactionSourceType] = mapped_column(
        _enum(TransactionSourceType, "position_transaction_source"),
        nullable=False,
    )
    status: Mapped[PositionTransactionStatus] = mapped_column(
        _enum(PositionTransactionStatus, "position_transaction_status"),
        nullable=False,
    )
    voided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    void_reason: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(String(4000))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )


class WatchEntityRecord(Base):
    __tablename__ = "watch_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_companies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    competitors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    customers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    industries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    @validates("symbol")
    def normalize_symbol(self, key: str, value: str) -> str:
        del key
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized


class SourceRecord(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_grade: Mapped[SourceGrade] = mapped_column(
        _enum(SourceGrade, "source_grade"),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    official: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    feed_url: Mapped[str | None] = mapped_column(String(1000))
    provider_type: Mapped[str | None] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="und")
    request_interval_seconds: Mapped[int] = mapped_column(nullable=False, default=60)
    timeout_seconds: Mapped[int] = mapped_column(nullable=False, default=10)
    max_items: Mapped[int] = mapped_column(nullable=False, default=50)
    original_source_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )


class RiskProfileRecord(Base):
    __tablename__ = "risk_profiles"
    __table_args__ = (
        CheckConstraint(
            "max_position_percent IS NULL OR "
            "(CAST(max_position_percent AS NUMERIC) >= 0 "
            "AND CAST(max_position_percent AS NUMERIC) <= 100)",
            name="ck_risk_max_position_range",
        ),
        CheckConstraint(
            "max_portfolio_loss_percent IS NULL OR "
            "(CAST(max_portfolio_loss_percent AS NUMERIC) >= 0 "
            "AND CAST(max_portfolio_loss_percent AS NUMERIC) <= 100)",
            name="ck_risk_max_portfolio_loss_range",
        ),
        CheckConstraint(
            "default_stop_loss_percent IS NULL OR "
            "(CAST(default_stop_loss_percent AS NUMERIC) >= 0 "
            "AND CAST(default_stop_loss_percent AS NUMERIC) <= 100)",
            name="ck_risk_default_stop_loss_range",
        ),
        CheckConstraint(
            "default_take_profit_percent IS NULL OR "
            "(CAST(default_take_profit_percent AS NUMERIC) >= 0 "
            "AND CAST(default_take_profit_percent AS NUMERIC) <= 100)",
            name="ck_risk_default_take_profit_range",
        ),
        CheckConstraint(
            "max_single_trade_amount IS NULL OR CAST(max_single_trade_amount AS NUMERIC) >= 0",
            name="ck_risk_max_single_trade_nonnegative",
        ),
        CheckConstraint(
            "cash_reserve_percent IS NULL OR "
            "(CAST(cash_reserve_percent AS NUMERIC) >= 0 "
            "AND CAST(cash_reserve_percent AS NUMERIC) <= 100)",
            name="ck_risk_cash_reserve_range",
        ),
        CheckConstraint(
            "max_single_position_percent IS NULL OR "
            "(CAST(max_single_position_percent AS NUMERIC) > 0 "
            "AND CAST(max_single_position_percent AS NUMERIC) <= 100)",
            name="ck_risk_single_position_review_range",
        ),
        CheckConstraint(
            "portfolio_loss_review_percent IS NULL OR "
            "(CAST(portfolio_loss_review_percent AS NUMERIC) > 0 "
            "AND CAST(portfolio_loss_review_percent AS NUMERIC) <= 100)",
            name="ck_risk_portfolio_review_range",
        ),
        CheckConstraint(
            "minimum_cash_percent IS NULL OR "
            "(CAST(minimum_cash_percent AS NUMERIC) >= 0 "
            "AND CAST(minimum_cash_percent AS NUMERIC) <= 100)",
            name="ck_risk_minimum_cash_range",
        ),
        CheckConstraint(
            "default_loss_review_percent IS NULL OR "
            "(CAST(default_loss_review_percent AS NUMERIC) > 0 "
            "AND CAST(default_loss_review_percent AS NUMERIC) <= 100)",
            name="ck_risk_default_loss_review_range",
        ),
        CheckConstraint(
            "default_profit_review_percent IS NULL OR "
            "(CAST(default_profit_review_percent AS NUMERIC) > 0 "
            "AND CAST(default_profit_review_percent AS NUMERIC) <= 100)",
            name="ck_risk_default_profit_review_range",
        ),
        CheckConstraint(
            "max_single_additional_buy_percent IS NULL OR "
            "(CAST(max_single_additional_buy_percent AS NUMERIC) >= 0 "
            "AND CAST(max_single_additional_buy_percent AS NUMERIC) <= 100)",
            name="ck_risk_additional_buy_range",
        ),
        CheckConstraint(
            "high_volatility_asset_limit_percent IS NULL OR "
            "(CAST(high_volatility_asset_limit_percent AS NUMERIC) >= 0 "
            "AND CAST(high_volatility_asset_limit_percent AS NUMERIC) <= 100)",
            name="ck_risk_high_volatility_range",
        ),
        CheckConstraint(
            "crypto_asset_limit_percent IS NULL OR "
            "(CAST(crypto_asset_limit_percent AS NUMERIC) >= 0 "
            "AND CAST(crypto_asset_limit_percent AS NUMERIC) <= 100)",
            name="ck_risk_crypto_limit_range",
        ),
        CheckConstraint(
            "max_averaging_down_count IS NULL OR max_averaging_down_count >= 0",
            name="ck_risk_averaging_count_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")
    max_position_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    max_portfolio_loss_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    default_stop_loss_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    default_take_profit_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    max_single_trade_amount: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    cash_reserve_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    allow_averaging_down: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    recommendation_mode: Mapped[RecommendationMode] = mapped_column(
        _enum(RecommendationMode, "recommendation_mode"),
        nullable=False,
        default=RecommendationMode.UNSET,
    )
    risk_style: Mapped[RiskStyle | None] = mapped_column(_enum(RiskStyle, "risk_style"))
    primary_goal: Mapped[PrimaryGoal | None] = mapped_column(_enum(PrimaryGoal, "primary_goal"))
    default_investment_horizon: Mapped[InvestmentHorizon | None] = mapped_column(
        _enum(InvestmentHorizon, "risk_default_investment_horizon")
    )
    max_single_position_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    portfolio_loss_review_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    default_loss_review_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    default_profit_review_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    minimum_cash_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    max_single_additional_buy_percent: Mapped[Decimal | None] = mapped_column(
        PreciseDecimal(7, 4)
    )
    averaging_down_policy: Mapped[AveragingDownPolicy | None] = mapped_column(
        _enum(AveragingDownPolicy, "averaging_down_policy")
    )
    max_averaging_down_count: Mapped[int | None] = mapped_column(Integer)
    require_official_evidence_for_averaging_down: Mapped[bool | None] = mapped_column(Boolean)
    high_volatility_asset_limit_percent: Mapped[Decimal | None] = mapped_column(
        PreciseDecimal(7, 4)
    )
    crypto_asset_limit_percent: Mapped[Decimal | None] = mapped_column(PreciseDecimal(7, 4))
    notes: Mapped[str | None] = mapped_column(String(4000))
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source: Mapped[RiskProfileSource] = mapped_column(
        _enum(RiskProfileSource, "risk_profile_source"),
        nullable=False,
        default=RiskProfileSource.CUSTOM,
    )
    portfolio_fingerprint: Mapped[str | None] = mapped_column(String(64))
    recommendation_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )
