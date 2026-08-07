from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.core.time import require_aware_utc, restore_utc
from app.models.database import (
    AssetType,
    Currency,
    InvestmentHorizon,
    SaleTransactionStatus,
    SaleTransactionType,
)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class SaleSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class SaleCreate(SaleSchema):
    sold_at: datetime
    quantity: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    sale_price: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    fee_amount: Decimal = Field(default=Decimal(0), ge=0, max_digits=38, decimal_places=18)
    tax_amount: Decimal = Field(default=Decimal(0), ge=0, max_digits=38, decimal_places=18)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("sold_at")
    @classmethod
    def aware_sold_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class SaleUpdate(SaleSchema):
    sold_at: datetime | None = None
    sale_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=38,
        decimal_places=18,
    )
    fee_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=38,
        decimal_places=18,
    )
    tax_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=38,
        decimal_places=18,
    )
    notes: str | None = Field(default=None, max_length=4000)
    quantity: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=38,
        decimal_places=18,
    )

    @field_validator("sold_at")
    @classmethod
    def aware_optional_sold_at(cls, value: datetime | None) -> datetime | None:
        return require_aware_utc(value) if value is not None else None


class SaleVoid(SaleSchema):
    reason: str = Field(min_length=1, max_length=1000)


class HistoricalSaleEntry(SaleCreate):
    pass


class HistoricalPortfolioCreate(SaleSchema):
    asset_type: AssetType
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    market: str = Field(min_length=1, max_length=50)
    currency: Currency
    average_price: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    total_sold_quantity: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    investment_horizon: InvestmentHorizon = InvestmentHorizon.UNSET
    strategy: str = Field(default="", max_length=500)
    target_allocation: Decimal | None = Field(default=None, ge=0, le=100)
    max_loss_percent: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=4000)
    sales: list[HistoricalSaleEntry] = Field(min_length=1)

    @field_validator("symbol", "market")
    @classmethod
    def normalize_identifiers(cls, value: str) -> str:
        return value.strip().upper()


class SaleRead(SaleSchema):
    id: UUID
    portfolio_item_id: UUID
    transaction_type: SaleTransactionType
    sold_at: datetime
    quantity: Decimal
    sale_price: Decimal
    purchase_average_price_snapshot: Decimal
    currency: Currency
    fee_amount: Decimal
    tax_amount: Decimal
    gross_proceeds: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal
    realized_return_percent: Decimal | None
    quantity_before: Decimal
    quantity_after: Decimal
    historical_import: bool
    notes: str | None
    status: SaleTransactionStatus
    voided_at: datetime | None
    void_reason: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "quantity",
        "sale_price",
        "purchase_average_price_snapshot",
        "fee_amount",
        "tax_amount",
        "gross_proceeds",
        "cost_basis",
        "realized_pnl",
        "realized_return_percent",
        "quantity_before",
        "quantity_after",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    @field_validator(
        "sold_at",
        "voided_at",
        "created_at",
        "updated_at",
    )
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        return restore_utc(value) if value is not None else None


class SaleList(SaleSchema):
    items: list[SaleRead]
    total: int


class SaleSummary(SaleSchema):
    active_sale_count: int
    total_sold_quantity: Decimal
    total_gross_proceeds: Decimal
    total_fee_amount: Decimal
    total_tax_amount: Decimal
    total_cost_basis: Decimal
    total_realized_pnl: Decimal
    total_realized_return_percent: Decimal | None
    weighted_average_sale_price: Decimal | None
    first_sold_at: datetime | None
    last_sold_at: datetime | None

    @field_serializer(
        "total_sold_quantity",
        "total_gross_proceeds",
        "total_fee_amount",
        "total_tax_amount",
        "total_cost_basis",
        "total_realized_pnl",
        "total_realized_return_percent",
        "weighted_average_sale_price",
        when_used="json",
    )
    def serialize_summary_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    @field_validator("first_sold_at", "last_sold_at")
    @classmethod
    def ensure_summary_utc(cls, value: datetime | None) -> datetime | None:
        return restore_utc(value) if value is not None else None


class HistoricalPortfolioRead(SaleSchema):
    portfolio_id: UUID
    sales: list[SaleRead]
    sale_summary: SaleSummary
