from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import SystemClock
from app.database import Base
from app.models.database import PreciseDecimal, UTCDateTime


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return SystemClock().now()


class ThesisStatus(StrEnum):
    NOT_SET = "NOT_SET"
    ACTIVE = "ACTIVE"
    STRENGTHENED = "STRENGTHENED"
    WEAKENED = "WEAKENED"
    PARTIALLY_BROKEN = "PARTIALLY_BROKEN"
    BROKEN = "BROKEN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class UserConviction(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NOT_SET = "NOT_SET"


class ImpactRelevance(StrEnum):
    DIRECT = "DIRECT"
    INDUSTRY = "INDUSTRY"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    CUSTOMER = "CUSTOMER"
    COMPETITOR = "COMPETITOR"
    MACRO = "MACRO"
    LOW = "LOW"


class ImpactDirection(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"
    UNCLEAR = "UNCLEAR"


class Strength(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImpactHorizon(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_TERM = "LONG_TERM"
    UNKNOWN = "UNKNOWN"


class ThesisEffect(StrEnum):
    STRENGTHENS = "STRENGTHENS"
    SLIGHTLY_STRENGTHENS = "SLIGHTLY_STRENGTHENS"
    NO_CHANGE = "NO_CHANGE"
    SLIGHTLY_WEAKENS = "SLIGHTLY_WEAKENS"
    WEAKENS = "WEAKENS"
    BREAKS = "BREAKS"
    UNKNOWN = "UNKNOWN"


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GeneratedBy(StrEnum):
    RULE_BASED = "RULE_BASED"
    USER = "USER"
    AI_ASSISTED = "AI_ASSISTED"


class DecisionDirection(StrEnum):
    ADD_REVIEW = "ADD_REVIEW"
    HOLD = "HOLD"
    WAIT = "WAIT"
    REDUCE_REVIEW = "REDUCE_REVIEW"
    EXIT_REVIEW = "EXIT_REVIEW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class InvestmentThesisRecord(Base):
    __tablename__ = "investment_theses"
    __table_args__ = (
        UniqueConstraint("portfolio_item_id", name="uq_investment_thesis_portfolio"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    portfolio_item_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_items.id", ondelete="RESTRICT"), nullable=False
    )
    thesis_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    investment_purpose: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    investment_horizon: Mapped[str] = mapped_column(String(30), nullable=False, default="UNSET")
    original_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expected_catalysts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    key_risks: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_add: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_hold: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_reduce: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_exit: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    invalidation_conditions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    questions_to_verify: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    user_conviction: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_SET")
    thesis_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_SET")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_now, onupdate=_now
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PortfolioImpactRecord(Base):
    __tablename__ = "portfolio_impacts"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "portfolio_item_id", name="uq_portfolio_impact_event_portfolio"
        ),
        Index("ix_portfolio_impacts_portfolio_generated", "portfolio_item_id", "generated_at"),
        Index("ix_portfolio_impacts_event", "event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("information_events.id", ondelete="RESTRICT"), nullable=False
    )
    portfolio_item_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_items.id", ondelete="RESTRICT"), nullable=False
    )
    thesis_id: Mapped[str | None] = mapped_column(
        ForeignKey("investment_theses.id", ondelete="SET NULL")
    )
    relevance: Mapped[str] = mapped_column(String(30), nullable=False)
    impact_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    impact_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    impact_horizon: Mapped[str] = mapped_column(String(30), nullable=False)
    thesis_effect: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    one_line_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    impact_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supporting_factors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    opposing_factors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_watch: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    invalidation_conditions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    missing_information: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_links: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    generated_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GeneratedBy.RULE_BASED.value
    )
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_now)
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    human_decision_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DecisionReviewRecord(Base):
    __tablename__ = "decision_reviews"
    __table_args__ = (
        Index("ix_decision_reviews_portfolio_generated", "portfolio_item_id", "generated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    portfolio_item_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_items.id", ondelete="RESTRICT"), nullable=False
    )
    thesis_id: Mapped[str | None] = mapped_column(
        ForeignKey("investment_theses.id", ondelete="SET NULL")
    )
    direction: Mapped[str] = mapped_column(String(30), nullable=False)
    thesis_status: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    why_now: Mapped[str] = mapped_column(String(2000), nullable=False)
    supporting_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    contrary_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    positive_factors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    negative_factors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_add: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_hold: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_reduce: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conditions_to_exit: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    invalidation_conditions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    missing_information: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    manual_reference_price: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    average_cost_snapshot: Mapped[Decimal | None] = mapped_column(PreciseDecimal(38, 18))
    quantity_snapshot: Mapped[Decimal] = mapped_column(PreciseDecimal(38, 18), nullable=False)
    risk_profile_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    based_on_event_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generated_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GeneratedBy.RULE_BASED.value
    )
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_now)
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    user_decision: Mapped[str | None] = mapped_column(String(1000))
    human_decision_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EconomicEventRecord(Base):
    __tablename__ = "economic_events"
    __table_args__ = (Index("ix_economic_events_scheduled", "scheduled_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    official_source_name: Mapped[str] = mapped_column(String(300), nullable=False)
    official_source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    related_portfolio_item_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    expected_impact_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    pre_release_checks: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    actual_result: Mapped[str | None] = mapped_column(String(2000))
    changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_now, onupdate=_now
    )
