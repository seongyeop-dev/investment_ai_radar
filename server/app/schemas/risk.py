from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.time import require_aware_utc, restore_utc
from app.models.database import (
    AveragingDownPolicy,
    InvestmentHorizon,
    PrimaryGoal,
    RecommendationMode,
    RiskProfileSource,
    RiskStyle,
)


class RiskProfileSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: (
            value.split("_")[0] + "".join(part.capitalize() for part in value.split("_")[1:])
        ),
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
    )


class RiskProfileInput(RiskProfileSchema):
    max_position_percent: Decimal | None = Field(default=None, ge=0, le=100)
    max_portfolio_loss_percent: Decimal | None = Field(default=None, ge=0, le=100)
    default_stop_loss_percent: Decimal | None = Field(default=None, ge=0, le=100)
    default_take_profit_percent: Decimal | None = Field(default=None, ge=0, le=100)
    max_single_trade_amount: Decimal | None = Field(default=None, ge=0)
    cash_reserve_percent: Decimal | None = Field(default=None, ge=0, le=100)
    allow_averaging_down: bool = False
    recommendation_mode: RecommendationMode = RecommendationMode.UNSET
    risk_style: RiskStyle | None = None
    primary_goal: PrimaryGoal | None = None
    default_investment_horizon: InvestmentHorizon | None = None
    max_single_position_percent: Decimal | None = Field(default=None, gt=0, le=100)
    portfolio_loss_review_percent: Decimal | None = Field(default=None, gt=0, le=100)
    default_loss_review_percent: Decimal | None = Field(default=None, gt=0, le=100)
    default_profit_review_percent: Decimal | None = Field(default=None, gt=0, le=100)
    minimum_cash_percent: Decimal | None = Field(default=None, ge=0, le=100)
    max_single_additional_buy_percent: Decimal | None = Field(default=None, ge=0, le=100)
    averaging_down_policy: AveragingDownPolicy | None = None
    max_averaging_down_count: int | None = Field(default=None, ge=0, le=100)
    require_official_evidence_for_averaging_down: bool | None = None
    high_volatility_asset_limit_percent: Decimal | None = Field(default=None, ge=0, le=100)
    crypto_asset_limit_percent: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=4000)
    acknowledged_at: datetime | None = None

    @field_validator("acknowledged_at")
    @classmethod
    def acknowledged_is_utc(cls, value: datetime | None) -> datetime | None:
        return require_aware_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_averaging_policy(self) -> RiskProfileInput:
        if self.averaging_down_policy is AveragingDownPolicy.CONDITIONAL:
            if not self.max_averaging_down_count:
                raise ValueError("조건부 추가매수는 1회 이상의 최대 횟수가 필요합니다.")
            if self.require_official_evidence_for_averaging_down is None:
                raise ValueError("조건부 추가매수의 공식 근거 확인 여부가 필요합니다.")
        return self

    @field_serializer(
        "max_position_percent",
        "max_portfolio_loss_percent",
        "default_stop_loss_percent",
        "default_take_profit_percent",
        "max_single_trade_amount",
        "cash_reserve_percent",
        "max_single_position_percent",
        "portfolio_loss_review_percent",
        "default_loss_review_percent",
        "default_profit_review_percent",
        "minimum_cash_percent",
        "max_single_additional_buy_percent",
        "high_volatility_asset_limit_percent",
        "crypto_asset_limit_percent",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None


class RiskProfileRead(RiskProfileInput):
    source: RiskProfileSource = RiskProfileSource.CUSTOM
    portfolio_fingerprint: str | None = None
    recommendation_version: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", "acknowledged_at")
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        return restore_utc(value) if value is not None else None


class RiskProfileResponse(RiskProfileSchema):
    configured: bool
    profile: RiskProfileRead | None


class RiskRecommendationConfidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfirmationAnswer(StrEnum):
    YES = "YES"
    NO = "NO"
    UNSURE = "UNSURE"


class AcceptableLossRange(StrEnum):
    UP_TO_10 = "UP_TO_10"
    FROM_10_TO_20 = "FROM_10_TO_20"
    OVER_20 = "OVER_20"
    UNSURE = "UNSURE"


class RiskRecommendationAnswers(RiskProfileSchema):
    funds_needed_within_one_year: ConfirmationAnswer | None = None
    acceptable_loss_range: AcceptableLossRange | None = None
    emergency_fund: ConfirmationAnswer | None = None
    averaging_down_preference: AveragingDownPolicy | None = None


class RiskRecommendationRequest(RiskProfileSchema):
    answers: RiskRecommendationAnswers = Field(default_factory=RiskRecommendationAnswers)


class RiskRecommendationDataCoverage(RiskProfileSchema):
    basis: Literal["PURCHASE_COST_BY_CURRENCY"]
    portfolio_count: int
    holding_count: int
    transaction_count: int
    additional_buy_count: int
    crypto_position_count: int
    structural_high_volatility_count: int
    currencies: list[str]
    cost_basis_by_currency: dict[str, str]
    max_cost_concentration_percent: Decimal | None
    max_crypto_cost_share_percent: Decimal | None
    total_realized_pnl_by_currency: dict[str, str]
    asset_type_counts: dict[str, int]
    investment_horizon_counts: dict[str, int]
    position_status_counts: dict[str, int]
    tracking_status_counts: dict[str, int]
    partial_sell_count: int
    full_sell_count: int
    market_price_provider_configured: bool = False
    partial_market_price_coverage: bool = False
    quoted_crypto_position_count: int = 0
    volatility_provider_configured: bool = False

    @field_serializer(
        "max_cost_concentration_percent",
        "max_crypto_cost_share_percent",
    )
    def serialize_coverage_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None


class RiskProfileRecommendation(RiskProfileSchema):
    suggested_risk_style: RiskStyle
    max_single_position_percent: Decimal
    portfolio_loss_review_percent: Decimal
    default_loss_review_percent: Decimal
    default_profit_review_percent: Decimal
    minimum_cash_percent: Decimal | None
    max_single_additional_buy_percent: Decimal
    averaging_down_policy: AveragingDownPolicy
    max_averaging_down_count: int
    require_official_evidence_for_averaging_down: bool
    high_volatility_asset_limit_percent: Decimal
    crypto_asset_limit_percent: Decimal
    confidence: RiskRecommendationConfidence
    data_coverage: RiskRecommendationDataCoverage
    reasons: list[str]
    missing_inputs: list[str]
    generated_at: datetime
    portfolio_fingerprint: str
    recommendation_version: str
    risk_profile_configured: bool
    profile_portfolio_fingerprint: str | None
    portfolio_changed: bool

    @field_serializer(
        "max_single_position_percent",
        "portfolio_loss_review_percent",
        "default_loss_review_percent",
        "default_profit_review_percent",
        "minimum_cash_percent",
        "max_single_additional_buy_percent",
        "high_volatility_asset_limit_percent",
        "crypto_asset_limit_percent",
    )
    def serialize_recommendation_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    @field_validator("generated_at")
    @classmethod
    def recommendation_time_is_utc(cls, value: datetime) -> datetime:
        return restore_utc(value)


class RiskRecommendationOption(RiskProfileSchema):
    value: str
    label: str
    description: str


class RiskRecommendationQuestion(RiskProfileSchema):
    id: str
    prompt: str
    options: list[RiskRecommendationOption]


class RiskRecommendationQuestions(RiskProfileSchema):
    items: list[RiskRecommendationQuestion]


class RiskRecommendationApply(RiskRecommendationRequest):
    expected_portfolio_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    recommendation_version: str = Field(min_length=1, max_length=50)
    mode: Literal["ALL", "CHANGED_ONLY"]


class RiskRecommendationApplyResponse(RiskProfileSchema):
    recommendation: RiskProfileRecommendation
    profile: RiskProfileRead
