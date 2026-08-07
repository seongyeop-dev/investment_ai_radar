from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from app.core.time import require_aware_utc
from app.models.analysis import (
    Confidence,
    DecisionDirection,
    GeneratedBy,
    ImpactDirection,
    ImpactHorizon,
    ImpactRelevance,
    Strength,
    ThesisEffect,
    ThesisStatus,
    UserConviction,
)
from app.models.contracts import VerificationStatus


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class AnalysisSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class SourceLink(AnalysisSchema):
    title: str = Field(max_length=500)
    url: str = Field(max_length=1000)
    official: bool = False


class InvestmentThesisInput(AnalysisSchema):
    thesis_summary: str = Field(default="", max_length=4000)
    investment_purpose: str = Field(default="", max_length=1000)
    investment_horizon: str = Field(default="UNSET", max_length=30)
    original_reasons: list[str] = Field(default_factory=list)
    expected_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    conditions_to_add: list[str] = Field(default_factory=list)
    conditions_to_hold: list[str] = Field(default_factory=list)
    conditions_to_reduce: list[str] = Field(default_factory=list)
    conditions_to_exit: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    questions_to_verify: list[str] = Field(default_factory=list)
    user_conviction: UserConviction = UserConviction.NOT_SET
    thesis_status: ThesisStatus = ThesisStatus.NOT_SET


class InvestmentThesisRead(InvestmentThesisInput):
    id: UUID | None
    portfolio_item_id: UUID
    created_at: datetime | None
    updated_at: datetime | None
    last_reviewed_at: datetime | None


class PortfolioImpactRead(AnalysisSchema):
    id: UUID
    event_id: UUID
    portfolio_item_id: UUID
    thesis_id: UUID | None
    relevance: ImpactRelevance
    impact_direction: ImpactDirection
    impact_strength: Strength
    impact_horizon: ImpactHorizon
    thesis_effect: ThesisEffect
    confidence: Confidence
    evidence_strength: Strength
    one_line_summary: str
    impact_path: list[str]
    supporting_factors: list[str]
    opposing_factors: list[str]
    conditions_to_watch: list[str]
    invalidation_conditions: list[str]
    missing_information: list[str]
    source_links: list[SourceLink]
    verification_status: VerificationStatus
    generated_by: GeneratedBy
    generated_at: datetime
    valid_until: datetime | None
    human_decision_required: bool


class PortfolioImpactList(AnalysisSchema):
    items: list[PortfolioImpactRead]
    total: int


class DecisionReviewRead(AnalysisSchema):
    id: UUID | None
    portfolio_item_id: UUID
    thesis_id: UUID | None
    direction: DecisionDirection
    thesis_status: ThesisStatus
    confidence: Confidence
    evidence_strength: Strength
    why_now: str
    supporting_evidence: list[str]
    contrary_evidence: list[str]
    positive_factors: list[str]
    negative_factors: list[str]
    conditions_to_add: list[str]
    conditions_to_hold: list[str]
    conditions_to_reduce: list[str]
    conditions_to_exit: list[str]
    invalidation_conditions: list[str]
    missing_information: list[str]
    manual_reference_price: Decimal | None
    average_cost_snapshot: Decimal | None
    quantity_snapshot: Decimal
    risk_profile_snapshot: dict[str, object]
    based_on_event_ids: list[UUID]
    generated_by: GeneratedBy
    generated_at: datetime
    valid_until: datetime | None
    acknowledged_at: datetime | None
    user_decision: str | None
    human_decision_required: bool

    @field_serializer(
        "manual_reference_price",
        "average_cost_snapshot",
        "quantity_snapshot",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None


class DecisionReviewList(AnalysisSchema):
    items: list[DecisionReviewRead]
    total: int


class DecisionReviewRefresh(AnalysisSchema):
    manual_reference_price: Decimal | None = Field(default=None, gt=0)


class DecisionReviewAcknowledge(AnalysisSchema):
    user_decision: str = Field(min_length=1, max_length=1000)


class AnalysisPacket(AnalysisSchema):
    portfolio_item_id: UUID
    name: str
    symbol: str
    market: str
    asset_type: str
    position_status: str
    tracking_status: str
    quantity: Decimal
    average_cost: Decimal | None
    investment_horizon: str
    thesis: InvestmentThesisRead
    recent_impacts: list[PortfolioImpactRead]
    decision_review: DecisionReviewRead
    official_source_links: list[SourceLink]
    missing_information: list[str]
    questions_for_chatgpt: list[str]
    copy_text: str
    article_full_text_included: bool = False
    human_decision_required: bool = True

    @field_serializer("quantity", "average_cost", when_used="json")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None


class EconomicEventRead(AnalysisSchema):
    id: UUID
    event_type: str
    title: str
    scheduled_at: datetime
    official_source_name: str
    official_source_url: str
    related_portfolio_item_ids: list[UUID]
    expected_impact_path: list[str]
    pre_release_checks: list[str]
    actual_result: str | None
    changed: bool
    created_at: datetime
    updated_at: datetime


class EconomicEventList(AnalysisSchema):
    items: list[EconomicEventRead]
    total: int


class EconomicEventImportRequest(AnalysisSchema):
    event_type: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    scheduled_at: datetime
    official_source_name: str = Field(min_length=1, max_length=300)
    official_source_url: str = Field(min_length=1, max_length=1000)
    portfolio_item_ids: list[UUID] = Field(min_length=1, max_length=20)
    expected_impact_path: list[str] = Field(min_length=1, max_length=10)
    pre_release_checks: list[str] = Field(default_factory=list, max_length=10)
    official_source_confirmed: bool = False
    confirm: bool = False

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime) -> datetime:
        del cls
        return require_aware_utc(value)

    @field_validator("official_source_url")
    @classmethod
    def validate_official_source_url(cls, value: str) -> str:
        del cls
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("공식 일정 원문은 HTTPS 절대주소여야 합니다.")
        return normalized

    @field_validator(
        "event_type",
        "title",
        "official_source_name",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        del cls
        normalized = value.strip()
        if not normalized:
            raise ValueError("필수 입력값은 비어 있을 수 없습니다.")
        return normalized

    @field_validator("portfolio_item_ids")
    @classmethod
    def unique_portfolio_item_ids(cls, value: list[UUID]) -> list[UUID]:
        del cls
        return list(dict.fromkeys(value))

    @field_validator("expected_impact_path")
    @classmethod
    def normalize_expected_impact_path(cls, value: list[str]) -> list[str]:
        del cls
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not normalized:
            raise ValueError("예상 영향 경로를 하나 이상 입력해야 합니다.")
        if any(len(item) > 500 for item in normalized):
            raise ValueError("예상 영향 경로 항목은 500자 이하여야 합니다.")
        return normalized

    @field_validator("pre_release_checks")
    @classmethod
    def normalize_pre_release_checks(cls, value: list[str]) -> list[str]:
        del cls
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if any(len(item) > 500 for item in normalized):
            raise ValueError("사전 확인 항목은 500자 이하여야 합니다.")
        return normalized


class EconomicEventImportPortfolioItem(AnalysisSchema):
    id: UUID
    symbol: str
    name: str
    market: str


class EconomicEventImportDuplicate(AnalysisSchema):
    duplicate: bool
    existing_event_id: UUID | None


class EconomicEventImportPreview(AnalysisSchema):
    normalized_url: str
    source_domain: str
    scheduled_at: datetime
    portfolio_items: list[EconomicEventImportPortfolioItem]
    duplicate: EconomicEventImportDuplicate
    official_source_confirmed: bool
    validation_warnings: list[str] = Field(default_factory=list)
    would_create: bool
    can_confirm: bool
    confirmed: Literal[False] = False


class EconomicEventImportConfirmed(AnalysisSchema):
    event: EconomicEventRead
    portfolio_items: list[EconomicEventImportPortfolioItem]
    validation_warnings: list[str] = Field(default_factory=list)
    confirmed: Literal[True] = True
