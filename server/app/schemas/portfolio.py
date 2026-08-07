from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.time import restore_utc
from app.models.database import (
    AssetType,
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PositionStatus,
    TrackingStatus,
)
from app.models.disclosures import InstrumentVerificationStatus
from app.schemas.sales import SaleSummary
from app.schemas.transactions import BuyCreate, PositionSummary


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class PortfolioSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class PortfolioCreate(PortfolioSchema):
    asset_type: AssetType
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    market: str = Field(min_length=1, max_length=50)
    currency: Currency
    holding_status: HoldingStatus
    tracking_status: TrackingStatus | None = None
    quantity: Decimal = Field(ge=0, max_digits=38, decimal_places=18)
    average_price: Decimal | None = Field(default=None, ge=0, max_digits=38, decimal_places=18)
    investment_horizon: InvestmentHorizon = InvestmentHorizon.UNSET
    strategy: str = Field(default="", max_length=500)
    target_allocation: Decimal | None = Field(default=None, ge=0, le=100)
    max_loss_percent: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=4000)
    initial_buy: BuyCreate | None = None

    @field_validator("symbol", "market")
    @classmethod
    def normalize_uppercase(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_holding_quantity(self) -> PortfolioCreate:
        if self.asset_type not in {
            AssetType.EQUITY,
            AssetType.ETF,
            AssetType.ADR,
            AssetType.CRYPTO,
            AssetType.OTHER,
        }:
            raise ValueError("포트폴리오에서 지원하지 않는 자산 유형입니다.")
        if self.asset_type is AssetType.CRYPTO:
            fractional_digits = max(-self.quantity.as_tuple().exponent, 0)
            if fractional_digits > 8:
                raise ValueError("암호자산 수량은 소수점 이하 8자리까지 입력할 수 있습니다.")
        if self.holding_status is HoldingStatus.HOLDING and self.quantity <= 0:
            raise ValueError("HOLDING 상태의 수량은 0보다 커야 합니다.")
        if self.holding_status is HoldingStatus.HOLDING and (
            self.average_price is None or self.average_price <= 0
        ):
            raise ValueError("HOLDING 상태의 평균 매입가는 0보다 커야 합니다.")
        if self.initial_buy is not None and (
            self.holding_status is not HoldingStatus.HOLDING
            or self.initial_buy.quantity != self.quantity
            or self.initial_buy.unit_price != self.average_price
        ):
            raise ValueError("초기 매수의 수량·단가는 보유 수량·평균단가와 일치해야 합니다.")
        return self


class PortfolioUpdate(PortfolioSchema):
    asset_type: AssetType | None = None
    symbol: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    market: str | None = Field(default=None, min_length=1, max_length=50)
    currency: Currency | None = None
    holding_status: HoldingStatus | None = None
    tracking_status: TrackingStatus | None = None
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=38, decimal_places=18)
    average_price: Decimal | None = Field(default=None, ge=0, max_digits=38, decimal_places=18)
    investment_horizon: InvestmentHorizon | None = None
    strategy: str | None = Field(default=None, max_length=500)
    target_allocation: Decimal | None = Field(default=None, ge=0, le=100)
    max_loss_percent: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("symbol", "market")
    @classmethod
    def normalize_identifiers(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class PortfolioRead(PortfolioSchema):
    id: UUID
    instrument_id: UUID | None = None
    instrument_verification_status: InstrumentVerificationStatus = (
        InstrumentVerificationStatus.UNVERIFIED
    )
    official_disclosure_availability: str = "NOT_MAPPED"
    symbol: str
    name: str
    market: str
    currency: Currency
    asset_type: AssetType
    holding_status: HoldingStatus
    position_status: PositionStatus
    tracking_status: TrackingStatus
    quantity: Decimal
    average_price: Decimal | None
    investment_horizon: InvestmentHorizon
    strategy: str
    target_allocation: Decimal | None
    max_loss_percent: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    current_price_availability: str = "NOT_CONFIGURED"
    sale_summary: SaleSummary | None = None
    active_sale_count: int = 0
    total_sold_quantity: Decimal = Decimal(0)
    weighted_average_sale_price: Decimal | None = None
    total_realized_pnl: Decimal = Decimal(0)
    total_realized_return_percent: Decimal | None = None
    first_sold_at: datetime | None = None
    last_sold_at: datetime | None = None
    position_summary: PositionSummary | None = None
    total_bought_quantity: Decimal = Decimal(0)
    active_transaction_count: int = 0
    buy_transaction_count: int = 0
    sell_transaction_count: int = 0
    first_traded_at: datetime | None = None
    last_traded_at: datetime | None = None

    @field_serializer(
        "quantity",
        "average_price",
        "target_allocation",
        "max_loss_percent",
        "total_sold_quantity",
        "weighted_average_sale_price",
        "total_realized_pnl",
        "total_realized_return_percent",
        "total_bought_quantity",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    @field_validator(
        "created_at",
        "updated_at",
        "archived_at",
        "first_sold_at",
        "last_sold_at",
        "first_traded_at",
        "last_traded_at",
    )
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        return restore_utc(value) if value is not None else None


class PortfolioList(PortfolioSchema):
    items: list[PortfolioRead]
    total: int
    limit: int
    offset: int


class PortfolioContextUpdate(PortfolioSchema):
    position_status: PositionStatus | None = None
    tracking_status: TrackingStatus | None = None
    current_quantity: Decimal | None = Field(
        default=None, ge=0, max_digits=38, decimal_places=18
    )
    average_cost: Decimal | None = Field(default=None, ge=0, max_digits=38, decimal_places=18)
    currency: Currency | None = None
    investment_horizon: InvestmentHorizon | None = None
    memo: str | None = Field(default=None, max_length=4000)


class PortfolioSummary(PortfolioSchema):
    total: int
    holding: int
    watchlist: int
    reentry_watch: int
    closed: int
    needs_review: int
    thesis_not_set: int
