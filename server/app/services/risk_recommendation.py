from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    risk_profile_validation,
    risk_recommendation_stale,
)
from app.core.time import Clock, SystemClock, require_aware_utc
from app.models.database import (
    AssetType,
    AveragingDownPolicy,
    PortfolioItemRecord,
    PositionStatus,
    PositionTransactionRecord,
    PositionTransactionStatus,
    RiskProfileSource,
    RiskStyle,
    TransactionSide,
)
from app.repositories.risk_profile import RiskProfileRepository
from app.schemas.risk import (
    AcceptableLossRange,
    ConfirmationAnswer,
    RiskProfileRecommendation,
    RiskRecommendationAnswers,
    RiskRecommendationApply,
    RiskRecommendationApplyResponse,
    RiskRecommendationConfidence,
    RiskRecommendationDataCoverage,
    RiskRecommendationOption,
    RiskRecommendationQuestion,
    RiskRecommendationQuestions,
)

RECOMMENDATION_VERSION = "risk-cost-basis-v1"
PERCENT_QUANTUM = Decimal("0.0001")


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal(0)
    with localcontext() as context:
        context.prec = 80
        return (numerator / denominator * Decimal(100)).quantize(
            PERCENT_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


class RiskRecommendationService:
    def __init__(
        self,
        session: Session,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._profiles = RiskProfileRepository(session)
        self._clock = clock or SystemClock()

    def recommend(
        self,
        answers: RiskRecommendationAnswers | None = None,
    ) -> RiskProfileRecommendation:
        resolved_answers = answers or RiskRecommendationAnswers()
        portfolios = list(
            self._session.scalars(select(PortfolioItemRecord).order_by(PortfolioItemRecord.id))
        )
        transactions = list(
            self._session.scalars(
                select(PositionTransactionRecord).order_by(
                    PositionTransactionRecord.portfolio_item_id,
                    PositionTransactionRecord.traded_at,
                    PositionTransactionRecord.created_at,
                    PositionTransactionRecord.id,
                )
            )
        )
        active_portfolios = [item for item in portfolios if item.archived_at is None]
        holding = [
            item
            for item in active_portfolios
            if item.position_status is PositionStatus.HOLDING
            and item.quantity > 0
            and item.average_price is not None
            and item.average_price > 0
        ]
        active_ids = {item.id for item in active_portfolios}
        active_transactions = [
            record
            for record in transactions
            if record.portfolio_item_id in active_ids
            and record.status is PositionTransactionStatus.ACTIVE
        ]
        asset_type_counts: dict[str, int] = defaultdict(int)
        investment_horizon_counts: dict[str, int] = defaultdict(int)
        position_status_counts: dict[str, int] = defaultdict(int)
        tracking_status_counts: dict[str, int] = defaultdict(int)
        for item in active_portfolios:
            asset_type_counts[item.asset_type.value] += 1
            investment_horizon_counts[item.investment_horizon.value] += 1
            position_status_counts[item.position_status.value] += 1
            tracking_status_counts[item.tracking_status.value] += 1

        costs_by_currency: dict[str, Decimal] = defaultdict(Decimal)
        position_costs: list[tuple[str, Decimal, bool]] = []
        for item in holding:
            cost = item.quantity * (item.average_price or Decimal(0))
            currency = item.currency.value
            costs_by_currency[currency] += cost
            position_costs.append((currency, cost, item.asset_type is AssetType.CRYPTO))

        concentration = Decimal(0)
        crypto_share = Decimal(0)
        for currency, total in costs_by_currency.items():
            currency_positions = [
                cost
                for item_currency, cost, _is_crypto in position_costs
                if item_currency == currency
            ]
            currency_crypto = sum(
                (
                    cost
                    for item_currency, cost, is_crypto in position_costs
                    if item_currency == currency and is_crypto
                ),
                Decimal(0),
            )
            if currency_positions:
                concentration = max(
                    concentration,
                    _percent(max(currency_positions), total),
                )
            crypto_share = max(
                crypto_share,
                _percent(currency_crypto, total),
            )

        buys_by_portfolio: dict[str, int] = defaultdict(int)
        realized_by_currency: dict[str, Decimal] = defaultdict(Decimal)
        partial_sell_count = 0
        full_sell_count = 0
        for record in active_transactions:
            if record.transaction_side is TransactionSide.BUY:
                buys_by_portfolio[record.portfolio_item_id] += 1
            elif record.realized_pnl is not None:
                realized_by_currency[record.currency.value] += record.realized_pnl
                if record.quantity_after > 0:
                    partial_sell_count += 1
                else:
                    full_sell_count += 1
        additional_buy_count = sum(max(count - 1, 0) for count in buys_by_portfolio.values())
        missing_inputs = self._missing_inputs(resolved_answers)
        missing_inputs.extend(
            [
                "MARKET_PRICE_PROVIDER",
                "MARKET_VOLATILITY_PROVIDER",
                "FX_RATES_FOR_CROSS_CURRENCY_WEIGHT",
                "CURRENT_CASH_BALANCE",
            ]
        )
        if not holding:
            missing_inputs.append("POSITIVE_POSITION_COST_BASIS")
        missing_inputs = list(dict.fromkeys(missing_inputs))

        style = self._style(resolved_answers)
        settings = self._style_settings(style)
        if concentration >= Decimal(50):
            settings["max_single_position_percent"] = min(
                settings["max_single_position_percent"],
                Decimal(15),
            )
        elif concentration >= Decimal(35):
            settings["max_single_position_percent"] = min(
                settings["max_single_position_percent"],
                Decimal(20),
            )
        if crypto_share >= Decimal(25):
            settings["crypto_asset_limit_percent"] = min(
                settings["crypto_asset_limit_percent"],
                Decimal(10),
            )
            settings["high_volatility_asset_limit_percent"] = min(
                settings["high_volatility_asset_limit_percent"],
                Decimal(15),
            )

        emergency = resolved_answers.emergency_fund
        minimum_cash: Decimal | None = None
        if emergency is ConfirmationAnswer.NO:
            minimum_cash = Decimal(30)
        elif emergency is ConfirmationAnswer.YES:
            minimum_cash = settings["minimum_cash_percent"]

        averaging_policy = (
            resolved_answers.averaging_down_preference or AveragingDownPolicy.CONDITIONAL
        )
        max_averaging_count = (
            0
            if averaging_policy is AveragingDownPolicy.DISABLED
            else 3
            if averaging_policy is AveragingDownPolicy.ALLOWED
            else 2
        )

        answered = 4 - len(self._missing_inputs(resolved_answers))
        confidence = (
            RiskRecommendationConfidence.MEDIUM
            if holding and answered >= 3
            else RiskRecommendationConfidence.LOW
        )
        profile = self._profiles.get()
        fingerprint = self._fingerprint(
            active_portfolios,
            active_transactions,
        )
        reasons = [
            (
                "현재가·환율 Provider가 없어 시가평가가 아닌 통화별 매수 원가 "
                "기준으로 분석했습니다."
            ),
            (
                f"활성 {len(active_portfolios)}개 종목 중 매수 원가를 계산할 수 "
                f"있는 보유 종목은 {len(holding)}개입니다."
            ),
            (
                f"통화별 최대 종목 집중도는 {format(concentration, 'f')}%입니다."
                if holding
                else (
                    "양수 수량과 평균단가가 있는 보유 종목이 없어 집중도를 계산하지 못했습니다."
                )
            ),
            (
                "암호자산 보유 "
                f"{sum(1 for item in holding if item.asset_type is AssetType.CRYPTO)}개를 "
                "구조적 고변동 자산 proxy로만 반영했습니다. "
                "실제 변동성 수치는 생성하지 않았습니다."
            ),
            (
                f"활성 거래 {len(active_transactions)}건과 추가매수 "
                f"{additional_buy_count}회를 확인했습니다."
            ),
            (
                f"부분매도 {partial_sell_count}건과 전량매도 "
                f"{full_sell_count}건의 활성 원장을 반영했습니다."
            ),
            (
                "투자 기간·보유 상태·추적 상태는 실제 Portfolio 분포만 "
                "집계했으며 소득·부채·현금 정보는 추정하지 않았습니다."
            ),
            "이 결과는 위험 검토 기준 제안이며 매수·매도·보유 추천이 아닙니다.",
        ]

        return RiskProfileRecommendation(
            suggested_risk_style=style,
            max_single_position_percent=settings["max_single_position_percent"],
            portfolio_loss_review_percent=settings["portfolio_loss_review_percent"],
            default_loss_review_percent=settings["default_loss_review_percent"],
            default_profit_review_percent=settings["default_profit_review_percent"],
            minimum_cash_percent=minimum_cash,
            max_single_additional_buy_percent=settings["max_single_additional_buy_percent"],
            averaging_down_policy=averaging_policy,
            max_averaging_down_count=max_averaging_count,
            require_official_evidence_for_averaging_down=True,
            high_volatility_asset_limit_percent=settings["high_volatility_asset_limit_percent"],
            crypto_asset_limit_percent=settings["crypto_asset_limit_percent"],
            confidence=confidence,
            data_coverage=RiskRecommendationDataCoverage(
                basis="PURCHASE_COST_BY_CURRENCY",
                portfolio_count=len(active_portfolios),
                holding_count=len(holding),
                transaction_count=len(active_transactions),
                additional_buy_count=additional_buy_count,
                crypto_position_count=sum(
                    1 for item in holding if item.asset_type is AssetType.CRYPTO
                ),
                structural_high_volatility_count=sum(
                    1 for item in holding if item.asset_type is AssetType.CRYPTO
                ),
                currencies=sorted(costs_by_currency),
                cost_basis_by_currency={
                    key: format(value, "f") for key, value in sorted(costs_by_currency.items())
                },
                max_cost_concentration_percent=(concentration if holding else None),
                max_crypto_cost_share_percent=(crypto_share if holding else None),
                total_realized_pnl_by_currency={
                    key: format(value, "f")
                    for key, value in sorted(realized_by_currency.items())
                },
                asset_type_counts=dict(sorted(asset_type_counts.items())),
                investment_horizon_counts=dict(sorted(investment_horizon_counts.items())),
                position_status_counts=dict(sorted(position_status_counts.items())),
                tracking_status_counts=dict(sorted(tracking_status_counts.items())),
                partial_sell_count=partial_sell_count,
                full_sell_count=full_sell_count,
                market_price_provider_configured=False,
                partial_market_price_coverage=False,
                quoted_crypto_position_count=0,
            ),
            reasons=reasons,
            missing_inputs=missing_inputs,
            generated_at=require_aware_utc(self._clock.now()),
            portfolio_fingerprint=fingerprint,
            recommendation_version=RECOMMENDATION_VERSION,
            risk_profile_configured=profile is not None,
            profile_portfolio_fingerprint=(
                profile.portfolio_fingerprint if profile is not None else None
            ),
            portfolio_changed=bool(
                profile is not None
                and profile.portfolio_fingerprint is not None
                and profile.portfolio_fingerprint != fingerprint
            ),
        )

    def apply(
        self,
        payload: RiskRecommendationApply,
    ) -> RiskRecommendationApplyResponse:
        if payload.recommendation_version != RECOMMENDATION_VERSION:
            raise risk_recommendation_stale()
        recommendation = self.recommend(payload.answers)
        if payload.expected_portfolio_fingerprint != recommendation.portfolio_fingerprint:
            raise risk_recommendation_stale()

        values: dict[str, object] = {
            "risk_style": recommendation.suggested_risk_style,
            "max_single_position_percent": (recommendation.max_single_position_percent),
            "portfolio_loss_review_percent": (recommendation.portfolio_loss_review_percent),
            "default_loss_review_percent": (recommendation.default_loss_review_percent),
            "default_profit_review_percent": (recommendation.default_profit_review_percent),
            "max_single_additional_buy_percent": (
                recommendation.max_single_additional_buy_percent
            ),
            "averaging_down_policy": (recommendation.averaging_down_policy),
            "max_averaging_down_count": (recommendation.max_averaging_down_count),
            "require_official_evidence_for_averaging_down": (
                recommendation.require_official_evidence_for_averaging_down
            ),
            "high_volatility_asset_limit_percent": (
                recommendation.high_volatility_asset_limit_percent
            ),
            "crypto_asset_limit_percent": (recommendation.crypto_asset_limit_percent),
            "source": RiskProfileSource.DATA_ASSISTED,
            "acknowledged_at": require_aware_utc(self._clock.now()),
            "portfolio_fingerprint": recommendation.portfolio_fingerprint,
            "recommendation_version": RECOMMENDATION_VERSION,
        }
        if recommendation.minimum_cash_percent is not None:
            values["minimum_cash_percent"] = recommendation.minimum_cash_percent
            values["cash_reserve_percent"] = recommendation.minimum_cash_percent
        values.update(
            {
                "max_position_percent": (recommendation.max_single_position_percent),
                "max_portfolio_loss_percent": (recommendation.portfolio_loss_review_percent),
                "default_stop_loss_percent": (recommendation.default_loss_review_percent),
                "default_take_profit_percent": (recommendation.default_profit_review_percent),
                "allow_averaging_down": (
                    recommendation.averaging_down_policy is not AveragingDownPolicy.DISABLED
                ),
            }
        )
        current = self._profiles.get()
        if payload.mode == "CHANGED_ONLY" and current is not None:
            values = {
                key: value for key, value in values.items() if getattr(current, key) != value
            }
        try:
            profile = self._profiles.upsert(values)
        except IntegrityError as exc:
            raise risk_profile_validation("위험 설정 제안값을 저장할 수 없습니다.") from exc
        return RiskRecommendationApplyResponse(
            recommendation=self.recommend(payload.answers),
            profile=profile,
        )

    @staticmethod
    def questions() -> RiskRecommendationQuestions:
        yes_no_unsure = [
            RiskRecommendationOption(
                value="YES",
                label="예",
                description="해당 조건이 현재 상황에 적용됩니다.",
            ),
            RiskRecommendationOption(
                value="NO",
                label="아니요",
                description="해당 조건이 현재 상황에 적용되지 않습니다.",
            ),
            RiskRecommendationOption(
                value="UNSURE",
                label="잘 모르겠음",
                description="미확인 정보로 남기고 신뢰도를 낮춥니다.",
            ),
        ]
        return RiskRecommendationQuestions(
            items=[
                RiskRecommendationQuestion(
                    id="fundsNeededWithinOneYear",
                    prompt="1년 안에 사용할 예정인 투자금이 있나요?",
                    options=yes_no_unsure,
                ),
                RiskRecommendationQuestion(
                    id="acceptableLossRange",
                    prompt="감당 가능한 전체 손실 범위는 어느 정도인가요?",
                    options=[
                        RiskRecommendationOption(
                            value="UP_TO_10",
                            label="10% 이하",
                            description="손실 제한을 우선하는 기준입니다.",
                        ),
                        RiskRecommendationOption(
                            value="FROM_10_TO_20",
                            label="10~20%",
                            description="중간 수준의 손실 범위입니다.",
                        ),
                        RiskRecommendationOption(
                            value="OVER_20",
                            label="20% 초과",
                            description="높은 손실 변동을 감수하는 범위입니다.",
                        ),
                        RiskRecommendationOption(
                            value="UNSURE",
                            label="잘 모르겠음",
                            description="미확인 정보로 남깁니다.",
                        ),
                    ],
                ),
                RiskRecommendationQuestion(
                    id="emergencyFund",
                    prompt="투자금과 별도의 비상자금이 있나요?",
                    options=yes_no_unsure,
                ),
                RiskRecommendationQuestion(
                    id="averagingDownPreference",
                    prompt="추가매수는 어떤 정책으로 관리할까요?",
                    options=[
                        RiskRecommendationOption(
                            value="DISABLED",
                            label="사용 안 함",
                            description="추가매수를 기본적으로 하지 않습니다.",
                        ),
                        RiskRecommendationOption(
                            value="CONDITIONAL",
                            label="조건부",
                            description="공식 근거와 횟수 한도 안에서만 검토합니다.",
                        ),
                        RiskRecommendationOption(
                            value="ALLOWED",
                            label="허용",
                            description="한도 안에서 사용자가 직접 판단합니다.",
                        ),
                    ],
                ),
            ]
        )

    @staticmethod
    def _missing_inputs(
        answers: RiskRecommendationAnswers,
    ) -> list[str]:
        missing: list[str] = []
        if answers.funds_needed_within_one_year in {
            None,
            ConfirmationAnswer.UNSURE,
        }:
            missing.append("FUNDS_NEEDED_WITHIN_ONE_YEAR")
        if answers.acceptable_loss_range in {
            None,
            AcceptableLossRange.UNSURE,
        }:
            missing.append("ACCEPTABLE_TOTAL_LOSS")
        if answers.emergency_fund in {
            None,
            ConfirmationAnswer.UNSURE,
        }:
            missing.append("EMERGENCY_FUND")
        if answers.averaging_down_preference is None:
            missing.append("AVERAGING_DOWN_POLICY")
        return missing

    @staticmethod
    def _style(answers: RiskRecommendationAnswers) -> RiskStyle:
        if (
            answers.funds_needed_within_one_year is ConfirmationAnswer.YES
            or answers.emergency_fund is ConfirmationAnswer.NO
            or answers.acceptable_loss_range is AcceptableLossRange.UP_TO_10
        ):
            return RiskStyle.CONSERVATIVE
        if (
            answers.funds_needed_within_one_year is ConfirmationAnswer.NO
            and answers.emergency_fund is ConfirmationAnswer.YES
            and answers.acceptable_loss_range is AcceptableLossRange.OVER_20
        ):
            return RiskStyle.AGGRESSIVE
        return RiskStyle.BALANCED

    @staticmethod
    def _style_settings(style: RiskStyle) -> dict[str, Decimal]:
        if style is RiskStyle.CONSERVATIVE:
            return {
                "max_single_position_percent": Decimal(15),
                "portfolio_loss_review_percent": Decimal(10),
                "default_loss_review_percent": Decimal(8),
                "default_profit_review_percent": Decimal(15),
                "minimum_cash_percent": Decimal(20),
                "max_single_additional_buy_percent": Decimal(5),
                "high_volatility_asset_limit_percent": Decimal(10),
                "crypto_asset_limit_percent": Decimal(5),
            }
        if style is RiskStyle.AGGRESSIVE:
            return {
                "max_single_position_percent": Decimal(30),
                "portfolio_loss_review_percent": Decimal(25),
                "default_loss_review_percent": Decimal(15),
                "default_profit_review_percent": Decimal(30),
                "minimum_cash_percent": Decimal(5),
                "max_single_additional_buy_percent": Decimal(15),
                "high_volatility_asset_limit_percent": Decimal(25),
                "crypto_asset_limit_percent": Decimal(20),
            }
        return {
            "max_single_position_percent": Decimal(20),
            "portfolio_loss_review_percent": Decimal(15),
            "default_loss_review_percent": Decimal(10),
            "default_profit_review_percent": Decimal(20),
            "minimum_cash_percent": Decimal(10),
            "max_single_additional_buy_percent": Decimal(10),
            "high_volatility_asset_limit_percent": Decimal(15),
            "crypto_asset_limit_percent": Decimal(10),
        }

    @staticmethod
    def _fingerprint(
        portfolios: list[PortfolioItemRecord],
        transactions: list[PositionTransactionRecord],
    ) -> str:
        content = {
            "portfolios": [
                {
                    "id": item.id,
                    "assetType": item.asset_type.value,
                    "market": item.market,
                    "symbol": item.symbol,
                    "currency": item.currency.value,
                    "quantity": _decimal_text(item.quantity),
                    "averagePrice": _decimal_text(item.average_price),
                    "investmentHorizon": item.investment_horizon.value,
                    "positionStatus": item.position_status.value,
                    "trackingStatus": item.tracking_status.value,
                    "archivedAt": (
                        item.archived_at.isoformat() if item.archived_at is not None else None
                    ),
                }
                for item in portfolios
            ],
            "transactions": [
                {
                    "id": record.id,
                    "portfolioItemId": record.portfolio_item_id,
                    "side": record.transaction_side.value,
                    "tradedAt": record.traded_at.isoformat(),
                    "quantity": _decimal_text(record.quantity),
                    "unitPrice": _decimal_text(record.unit_price),
                    "feeAmount": _decimal_text(record.fee_amount),
                    "taxAmount": _decimal_text(record.tax_amount),
                    "status": record.status.value,
                }
                for record in transactions
            ],
        }
        encoded = json.dumps(
            content,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
