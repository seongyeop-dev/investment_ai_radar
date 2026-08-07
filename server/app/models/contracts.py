from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class Contract(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class HoldingStatus(StrEnum):
    HELD = "HELD"
    WATCHING = "WATCHING"
    EXITED = "EXITED"


class SourceGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class VerificationStatus(StrEnum):
    OFFICIAL_CONFIRMED = "OFFICIAL_CONFIRMED"
    MULTI_SOURCE_CONFIRMED = "MULTI_SOURCE_CONFIRMED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    OFFICIALLY_DENIED = "OFFICIALLY_DENIED"
    CORRECTED = "CORRECTED"
    STALE_REUSED = "STALE_REUSED"


class RecommendationType(StrEnum):
    BUY_REVIEW = "BUY_REVIEW"
    HOLD = "HOLD"
    WAIT = "WAIT"
    REDUCE_REVIEW = "REDUCE_REVIEW"
    SELL_REVIEW = "SELL_REVIEW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class PortfolioItem(Contract):
    id: UUID
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    market: str = Field(min_length=1, max_length=50)
    currency: str = Field(min_length=3, max_length=3)
    holding_status: HoldingStatus
    quantity: Decimal = Field(ge=0)
    average_price: Decimal | None = Field(default=None, ge=0)
    investment_horizon: str
    strategy: str
    target_allocation: Decimal | None = Field(default=None, ge=0, le=100)
    max_loss_percent: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class WatchEntity(Contract):
    id: UUID
    symbol: str
    aliases: list[str] = Field(default_factory=list)
    related_companies: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    customers: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class Source(Contract):
    id: UUID
    name: str
    source_type: str
    source_grade: SourceGrade
    domain: str
    official: bool
    enabled: bool


class InformationItem(Contract):
    id: UUID
    title: str
    canonical_url: str
    source_id: UUID
    published_at: datetime | None = None
    source_updated_at: datetime | None = None
    first_seen_at: datetime
    fetched_at: datetime
    content_hash: str
    language: str
    raw_summary: str | None = None
    status: VerificationStatus


class Claim(Contract):
    id: UUID
    information_item_id: UUID
    subject: str
    predicate: str
    object: str
    certainty: Decimal = Field(ge=0, le=1)
    amount: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    effective_date: datetime | None = None


class Verification(Contract):
    id: UUID
    information_item_id: UUID
    verification_status: VerificationStatus
    trust_score: Decimal = Field(ge=0, le=100)
    official_match: bool
    independent_source_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    contradiction_count: int = Field(ge=0)
    verified_at: datetime | None = None
    reasons: list[str] = Field(default_factory=list)


class PortfolioImpact(Contract):
    id: UUID
    information_item_id: UUID
    portfolio_item_id: UUID
    direction: Literal["POSITIVE", "NEUTRAL", "NEGATIVE", "UNKNOWN"]
    magnitude: Decimal | None = Field(default=None, ge=0)
    horizon: str
    relevance_score: Decimal = Field(ge=0, le=100)
    explanation: str


class MacroSnapshot(Contract):
    id: UUID
    observed_at: datetime
    bitcoin: Decimal | None = Field(default=None, gt=0)
    gold: Decimal | None = Field(default=None, gt=0)
    wti: Decimal | None = Field(default=None, gt=0)
    brent: Decimal | None = Field(default=None, gt=0)
    usd_krw: Decimal | None = Field(default=None, gt=0)
    dollar_index: Decimal | None = Field(default=None, gt=0)
    us2_year: Decimal | None = None
    us10_year: Decimal | None = None
    vix: Decimal | None = Field(default=None, ge=0)
    kospi: Decimal | None = Field(default=None, gt=0)
    kosdaq: Decimal | None = Field(default=None, gt=0)
    nasdaq: Decimal | None = Field(default=None, gt=0)
    sp500: Decimal | None = Field(default=None, gt=0)
    sox: Decimal | None = Field(default=None, gt=0)
    data_quality: VerificationStatus


class Recommendation(Contract):
    id: UUID
    portfolio_item_id: UUID
    recommendation_type: RecommendationType
    generated_at: datetime
    valid_until: datetime
    portfolio_context: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    confidence: Decimal = Field(ge=0, le=100)
    trust_score: Decimal = Field(ge=0, le=100)
    data_completeness: Decimal = Field(ge=0, le=100)
    bullish_evidence: list[str] = Field(default_factory=list)
    bearish_evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    human_decision_required: Literal[True] = True


class Briefing(Contract):
    id: UUID
    briefing_type: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    important_items: list[UUID] = Field(default_factory=list)
    macro_summary: str | None = None
    portfolio_summary: str | None = None
    recommendation_summary: str | None = None
    corrections: list[str] = Field(default_factory=list)
    delivery_status: str
