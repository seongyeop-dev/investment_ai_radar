from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ProviderSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, from_attributes=True
    )


class ProviderStatusRead(ProviderSchema):
    provider: str
    capability: str
    configured: bool
    status: str
    last_success_at: datetime | None = None
    last_error_code: str | None = None
    consecutive_failures: int = 0
    request_count: int = 0
    success_count: int = 0


class ProviderStatusList(ProviderSchema):
    items: list[ProviderStatusRead]
    verified_mapping_count: int
    unresolved_mapping_count: int
    conflicting_mapping_count: int
    stale_mapping_count: int
    recent_disclosure_count: int
    latest_quote_count: int


class InstrumentMappingRead(ProviderSchema):
    id: UUID
    instrument_id: UUID
    provider: str
    provider_instrument_id: str
    provider_symbol: str | None
    cik: str | None
    corp_code: str | None
    stock_code: str | None
    canonical_symbol: str
    exchange: str | None
    official_name: str | None
    mapping_status: str
    match_method: str
    confidence: int
    source_url: str
    source_updated_at: datetime | None
    verified_at: datetime | None
    last_checked_at: datetime | None
    conflict_reason: str | None


class QuoteRead(ProviderSchema):
    id: UUID
    instrument_id: UUID
    provider: str
    provider_symbol: str
    price: Decimal
    quote_currency: str
    provider_event_at: datetime
    fetched_at: datetime
    freshness_status: str
    source_status: str
    sequence: int


class QuoteList(ProviderSchema):
    items: list[QuoteRead]
    total: int


class PortfolioQuoteRead(ProviderSchema):
    portfolio_id: UUID
    quote_status: str
    provider_configured: bool
    quote: QuoteRead | None = None


class NextMarketSessionRead(ProviderSchema):
    market: str
    session_date: str
    market_timezone: str
    open_at: datetime | None
    close_at: datetime | None
    holiday: bool
    early_close: bool
    schedule_status: str
    source: str | None
    next_briefings: list[dict[str, object]]


class NextMarketSessionList(ProviderSchema):
    items: list[NextMarketSessionRead]
