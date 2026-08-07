from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import restore_utc
from app.models.database import Currency
from app.models.disclosures import (
    AssetType,
    InstrumentVerificationStatus,
    ProviderName,
)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class InstrumentSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class InstrumentRead(InstrumentSchema):
    id: UUID
    canonical_symbol: str
    display_name: str
    local_name: str | None
    exchange: str | None
    market: str
    country: str
    currency: Currency
    asset_type: AssetType
    active: bool
    verification_status: InstrumentVerificationStatus
    verification_source: str | None
    verified_at: datetime | None
    delisted_at: datetime | None
    available_providers: list[ProviderName] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("verified_at", "delisted_at", "created_at", "updated_at")
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        return restore_utc(value) if value is not None else None


class InstrumentSearchResponse(InstrumentSchema):
    items: list[InstrumentRead]
    total: int
    limit: int


class InstrumentMappingInput(InstrumentSchema):
    instrument_id: UUID


class InstrumentSummary(InstrumentSchema):
    id: UUID
    canonical_symbol: str
    display_name: str
    market: str
