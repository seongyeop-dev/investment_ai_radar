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
)

from app.core.time import require_aware_utc, restore_utc
from app.models.database import (
    Currency,
    PositionStatus,
    PositionTransactionStatus,
    PositionTransactionType,
    TrackingStatus,
    TransactionSide,
    TransactionSourceType,
)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class TransactionSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class TransactionCreate(TransactionSchema):
    traded_at: datetime
    quantity: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    unit_price: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    fee_amount: Decimal = Field(
        default=Decimal(0),
        ge=0,
        max_digits=38,
        decimal_places=18,
    )
    tax_amount: Decimal = Field(
        default=Decimal(0),
        ge=0,
        max_digits=38,
        decimal_places=18,
    )
    notes: str | None = Field(default=None, max_length=4000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("traded_at")
    @classmethod
    def aware_traded_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class BuyCreate(TransactionCreate):
    pass


class SellCreate(TransactionCreate):
    pass


class TransactionUpdate(TransactionSchema):
    traded_at: datetime | None = None
    unit_price: Decimal | None = Field(
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

    @field_validator("traded_at")
    @classmethod
    def aware_optional_traded_at(cls, value: datetime | None) -> datetime | None:
        return require_aware_utc(value) if value is not None else None


class TransactionVoid(TransactionSchema):
    reason: str = Field(min_length=1, max_length=1000)


class HistoricalTransactionEntry(TransactionCreate):
    transaction_side: TransactionSide


class HistoricalTransactionImport(TransactionSchema):
    items: list[HistoricalTransactionEntry] = Field(min_length=1, max_length=500)


class PositionTransactionRead(TransactionSchema):
    id: UUID
    portfolio_item_id: UUID
    transaction_side: TransactionSide
    transaction_type: PositionTransactionType
    traded_at: datetime
    quantity: Decimal
    unit_price: Decimal
    currency: Currency
    fee_amount: Decimal
    tax_amount: Decimal
    gross_amount: Decimal
    quantity_before: Decimal
    quantity_after: Decimal
    average_price_before: Decimal | None
    average_price_after: Decimal | None
    realized_pnl: Decimal | None
    realized_return_percent: Decimal | None
    sequence_number: int
    source_type: TransactionSourceType
    status: PositionTransactionStatus
    voided_at: datetime | None
    void_reason: str | None
    notes: str | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "quantity",
        "unit_price",
        "fee_amount",
        "tax_amount",
        "gross_amount",
        "quantity_before",
        "quantity_after",
        "average_price_before",
        "average_price_after",
        "realized_pnl",
        "realized_return_percent",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    @field_validator("traded_at", "voided_at", "created_at", "updated_at")
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        return restore_utc(value) if value is not None else None


class PositionTransactionList(TransactionSchema):
    items: list[PositionTransactionRead]
    total: int


class PositionSummary(TransactionSchema):
    portfolio_item_id: UUID
    position_status: PositionStatus
    tracking_status: TrackingStatus
    current_quantity: Decimal
    current_average_price: Decimal | None
    total_bought_quantity: Decimal
    total_sold_quantity: Decimal
    weighted_average_sale_price: Decimal | None
    total_realized_pnl: Decimal
    total_realized_return_percent: Decimal | None
    active_transaction_count: int
    buy_count: int
    sell_count: int
    first_traded_at: datetime | None
    last_traded_at: datetime | None

    @field_serializer(
        "current_quantity",
        "current_average_price",
        "total_bought_quantity",
        "total_sold_quantity",
        "weighted_average_sale_price",
        "total_realized_pnl",
        "total_realized_return_percent",
        when_used="json",
    )
    def serialize_summary_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    @field_validator("first_traded_at", "last_traded_at")
    @classmethod
    def ensure_summary_utc(cls, value: datetime | None) -> datetime | None:
        return restore_utc(value) if value is not None else None
