from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import Clock, SystemClock
from app.models.analysis import (
    Confidence,
    DecisionDirection,
    DecisionReviewRecord,
    EconomicEventRecord,
    GeneratedBy,
    ImpactDirection,
    ImpactHorizon,
    ImpactRelevance,
    InvestmentThesisRecord,
    PortfolioImpactRecord,
    Strength,
    ThesisEffect,
    ThesisStatus,
)
from app.models.contracts import VerificationStatus
from app.models.database import PortfolioItemRecord, RiskProfileRecord
from app.models.disclosures import (
    DisclosureRecord,
    InformationEventRecord,
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    LifecycleStatus,
    MappingStatus,
    ProviderName,
)
from app.repositories.portfolio import PortfolioRepository
from app.schemas.analysis import (
    AnalysisPacket,
    DecisionReviewRead,
    EconomicEventImportRequest,
    InvestmentThesisInput,
    InvestmentThesisRead,
    PortfolioImpactRead,
    SourceLink,
)
from app.services.disclosures import canonical_official_url
from app.services.portfolio import PortfolioService


@dataclass(frozen=True, slots=True)
class EconomicEventImportPlan:
    canonical_url: str
    source_domain: str
    portfolio_items: tuple[PortfolioItemRecord, ...]
    duplicate: EconomicEventRecord | None
    official_source_confirmed: bool
    validation_warnings: tuple[str, ...]

    @property
    def would_create(self) -> bool:
        return self.duplicate is None

    @property
    def can_confirm(self) -> bool:
        return self.would_create and self.official_source_confirmed


class AnalysisService:
    def __init__(self, session: Session, *, clock: Clock | None = None) -> None:
        self.session = session
        self.clock = clock or SystemClock()
        self.portfolios = PortfolioService(PortfolioRepository(session))

    def thesis(self, portfolio_item_id: str) -> InvestmentThesisRead:
        item = self.portfolios.get(portfolio_item_id)
        record = self.session.scalar(
            select(InvestmentThesisRecord).where(
                InvestmentThesisRecord.portfolio_item_id == portfolio_item_id
            )
        )
        if record is not None:
            return InvestmentThesisRead.model_validate(record)
        return InvestmentThesisRead(
            id=None,
            portfolio_item_id=item.id,
            thesis_summary="",
            investment_purpose="",
            investment_horizon=item.investment_horizon.value,
            original_reasons=[],
            expected_catalysts=[],
            key_risks=[],
            conditions_to_add=[],
            conditions_to_hold=[],
            conditions_to_reduce=[],
            conditions_to_exit=[],
            invalidation_conditions=[],
            questions_to_verify=[],
            user_conviction="NOT_SET",
            thesis_status="NOT_SET",
            created_at=None,
            updated_at=None,
            last_reviewed_at=None,
        )

    def save_thesis(
        self, portfolio_item_id: str, payload: InvestmentThesisInput
    ) -> InvestmentThesisRecord:
        self.portfolios.get(portfolio_item_id)
        record = self.session.scalar(
            select(InvestmentThesisRecord).where(
                InvestmentThesisRecord.portfolio_item_id == portfolio_item_id
            )
        )
        values = payload.model_dump(mode="json")
        now = self.clock.now()
        if record is None:
            record = InvestmentThesisRecord(
                portfolio_item_id=portfolio_item_id,
                **values,
                created_at=now,
                updated_at=now,
                last_reviewed_at=now,
            )
            self.session.add(record)
        else:
            for key, value in values.items():
                setattr(record, key, value)
            record.updated_at = now
            record.last_reviewed_at = now
        self.session.flush()
        self.session.refresh(record)
        return record

    def impacts(
        self,
        *,
        portfolio_item_id: str | None = None,
        event_id: str | None = None,
    ) -> list[PortfolioImpactRecord]:
        filters = []
        if portfolio_item_id is not None:
            self.portfolios.get(portfolio_item_id)
            filters.append(PortfolioImpactRecord.portfolio_item_id == portfolio_item_id)
        if event_id is not None:
            filters.append(PortfolioImpactRecord.event_id == event_id)
        return list(
            self.session.scalars(
                select(PortfolioImpactRecord)
                .where(*filters)
                .order_by(
                    PortfolioImpactRecord.generated_at.desc(),
                    PortfolioImpactRecord.id.asc(),
                )
            )
        )

    def latest_review(self, portfolio_item_id: str) -> DecisionReviewRead:
        item = self.portfolios.get(portfolio_item_id)
        draft = self._draft(item, manual_reference_price=None)
        record = self.session.scalar(
            select(DecisionReviewRecord)
            .where(DecisionReviewRecord.portfolio_item_id == portfolio_item_id)
            .order_by(
                DecisionReviewRecord.generated_at.desc(),
                DecisionReviewRecord.id.desc(),
            )
            .limit(1)
        )
        if record is not None and self._same_analysis(record, draft):
            return DecisionReviewRead.model_validate(record)
        return draft

    def list_reviews(self) -> list[DecisionReviewRead]:
        items, _ = self.portfolios.list(include_archived=False, limit=100)
        return [self.latest_review(item.id) for item in items]

    def refresh_review(
        self,
        portfolio_item_id: str,
        *,
        manual_reference_price: Decimal | None,
    ) -> DecisionReviewRecord:
        item = self.portfolios.get(portfolio_item_id)
        draft = self._draft(item, manual_reference_price=manual_reference_price)
        existing = self.session.scalar(
            select(DecisionReviewRecord)
            .where(DecisionReviewRecord.portfolio_item_id == portfolio_item_id)
            .order_by(
                DecisionReviewRecord.generated_at.desc(),
                DecisionReviewRecord.id.desc(),
            )
            .limit(1)
        )
        if existing is not None and self._same_analysis(existing, draft):
            return existing
        values = draft.model_dump(exclude={"id"}, mode="python")
        values["portfolio_item_id"] = str(values["portfolio_item_id"])
        values["thesis_id"] = (
            str(values["thesis_id"]) if values["thesis_id"] is not None else None
        )
        values["based_on_event_ids"] = [
            str(event_id) for event_id in values["based_on_event_ids"]
        ]
        values["generated_by"] = values["generated_by"].value
        values["direction"] = values["direction"].value
        values["thesis_status"] = values["thesis_status"].value
        values["confidence"] = values["confidence"].value
        values["evidence_strength"] = values["evidence_strength"].value
        record = DecisionReviewRecord(**values)
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return record

    def acknowledge(
        self, portfolio_item_id: str, *, user_decision: str
    ) -> DecisionReviewRecord:
        item = self.portfolios.get(portfolio_item_id)
        draft = self._draft(item, manual_reference_price=None)
        record = self.session.scalar(
            select(DecisionReviewRecord)
            .where(DecisionReviewRecord.portfolio_item_id == portfolio_item_id)
            .order_by(
                DecisionReviewRecord.generated_at.desc(),
                DecisionReviewRecord.id.desc(),
            )
            .limit(1)
        )
        if record is None or not self._same_analysis(record, draft):
            record = self.refresh_review(portfolio_item_id, manual_reference_price=None)
        record.acknowledged_at = self.clock.now()
        record.user_decision = user_decision
        self.session.flush()
        self.session.refresh(record)
        return record

    def analysis_packet(self, portfolio_item_id: str) -> AnalysisPacket:
        item = self.portfolios.get(portfolio_item_id)
        thesis = self.thesis(portfolio_item_id)
        impacts = [
            PortfolioImpactRead.model_validate(record)
            for record in self.impacts(portfolio_item_id=portfolio_item_id)
        ][:20]
        review = self.latest_review(portfolio_item_id)
        links: list[SourceLink] = []
        seen_urls: set[str] = set()
        for impact in impacts:
            for link in impact.source_links:
                canonical_url = canonical_official_url(link.url)
                if canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)
                links.append(link.model_copy(update={"url": canonical_url}))
        questions = list(
            dict.fromkeys(
                [
                    *review.missing_information,
                    "반대 근거와 판단 무효화 조건을 함께 검토해 주세요.",
                ]
            )
        )
        copy_text = self._copy_text(item, thesis, impacts, review, links, questions)
        return AnalysisPacket(
            portfolio_item_id=item.id,
            name=item.name,
            symbol=item.symbol,
            market=item.market,
            asset_type=item.asset_type.value,
            position_status=item.position_status.value,
            tracking_status=item.tracking_status.value,
            quantity=item.quantity,
            average_cost=item.average_price,
            investment_horizon=item.investment_horizon.value,
            thesis=thesis,
            recent_impacts=impacts,
            decision_review=review,
            official_source_links=links,
            missing_information=review.missing_information,
            questions_for_chatgpt=questions,
            copy_text=copy_text,
            article_full_text_included=False,
            human_decision_required=True,
        )

    def economic_events(self, *, upcoming_only: bool = False) -> list[EconomicEventRecord]:
        filters = []
        if upcoming_only:
            filters.append(EconomicEventRecord.scheduled_at >= self.clock.now())
        return list(
            self.session.scalars(
                select(EconomicEventRecord)
                .where(*filters)
                .order_by(EconomicEventRecord.scheduled_at.asc())
            )
        )

    def plan_economic_event_import(
        self,
        payload: EconomicEventImportRequest,
    ) -> EconomicEventImportPlan:
        portfolio_items = tuple(
            self.portfolios.get(str(item_id)) for item_id in payload.portfolio_item_ids
        )
        canonical_url = canonical_official_url(payload.official_source_url)
        source_domain = (urlsplit(canonical_url).hostname or "").lower()

        duplicate = self.session.scalar(
            select(EconomicEventRecord)
            .where(EconomicEventRecord.official_source_url == canonical_url)
            .order_by(EconomicEventRecord.created_at.asc())
            .limit(1)
        )
        if duplicate is None:
            duplicate = self.session.scalar(
                select(EconomicEventRecord)
                .where(
                    EconomicEventRecord.title == payload.title,
                    EconomicEventRecord.scheduled_at == payload.scheduled_at,
                )
                .order_by(EconomicEventRecord.created_at.asc())
                .limit(1)
            )

        warnings: list[str] = []
        if payload.scheduled_at < self.clock.now():
            warnings.append("예정 시각이 이미 지났습니다. 과거 일정 기록으로 등록됩니다.")
        if not payload.official_source_confirmed:
            warnings.append("최종 등록 전 공식 원문과 발표 예정 시각을 직접 확인해야 합니다.")
        if duplicate is not None:
            warnings.append("동일한 공식 주소 또는 같은 시각의 일정이 이미 등록되어 있습니다.")

        return EconomicEventImportPlan(
            canonical_url=canonical_url,
            source_domain=source_domain,
            portfolio_items=portfolio_items,
            duplicate=duplicate,
            official_source_confirmed=payload.official_source_confirmed,
            validation_warnings=tuple(warnings),
        )

    def create_economic_event(
        self,
        payload: EconomicEventImportRequest,
        plan: EconomicEventImportPlan,
    ) -> EconomicEventRecord:
        if not plan.official_source_confirmed:
            raise ValueError("공식 원문과 발표 예정 시각 확인이 필요합니다.")
        if plan.duplicate is not None:
            raise ValueError("이미 등록된 경제·기업 일정입니다.")

        now = self.clock.now()
        record = EconomicEventRecord(
            event_type=payload.event_type.upper(),
            title=payload.title,
            scheduled_at=payload.scheduled_at,
            official_source_name=payload.official_source_name,
            official_source_url=plan.canonical_url,
            related_portfolio_item_ids=[item.id for item in plan.portfolio_items],
            expected_impact_path=payload.expected_impact_path,
            pre_release_checks=payload.pre_release_checks,
            actual_result=None,
            changed=False,
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return record

    def sync_direct_impacts(self) -> int:
        """Structure only verified event metadata; never infer a trading direction."""
        portfolios = list(
            self.session.scalars(
                select(PortfolioItemRecord).where(
                    PortfolioItemRecord.archived_at.is_(None),
                )
            )
        )
        created = 0
        for item in portfolios:
            instrument_ids = set()
            if item.instrument_id is not None:
                instrument_ids.add(item.instrument_id)
            instrument_ids.update(
                self.session.scalars(
                    select(InstrumentRecord.id)
                    .join(
                        InstrumentProviderMappingRecord,
                        InstrumentProviderMappingRecord.instrument_id == InstrumentRecord.id,
                    )
                    .where(
                        InstrumentRecord.active.is_(True),
                        InstrumentRecord.market == item.market,
                        InstrumentRecord.canonical_symbol == item.symbol,
                        InstrumentProviderMappingRecord.active.is_(True),
                        InstrumentProviderMappingRecord.mapping_status
                        == MappingStatus.VERIFIED,
                        InstrumentProviderMappingRecord.provider.in_(
                            [ProviderName.OPENDART, ProviderName.SEC_EDGAR]
                        ),
                    )
                )
            )
            if not instrument_ids:
                continue
            events = list(
                self.session.scalars(
                    select(InformationEventRecord).where(
                        InformationEventRecord.instrument_id.in_(instrument_ids)
                    )
                )
            )
            thesis = self.session.scalar(
                select(InvestmentThesisRecord).where(
                    InvestmentThesisRecord.portfolio_item_id == item.id
                )
            )
            for event in events:
                existing = self.session.scalar(
                    select(PortfolioImpactRecord).where(
                        PortfolioImpactRecord.event_id == event.id,
                        PortfolioImpactRecord.portfolio_item_id == item.id,
                    )
                )
                if (
                    event.lifecycle_status
                    in {
                        LifecycleStatus.STALE,
                        LifecycleStatus.ARCHIVED,
                    }
                    or event.verification_status is VerificationStatus.STALE_REUSED
                ):
                    if existing is not None:
                        existing.verification_status = VerificationStatus.STALE_REUSED.value
                    continue
                disclosures = list(
                    self.session.scalars(
                        select(DisclosureRecord).where(DisclosureRecord.event_id == event.id)
                    )
                )
                if not disclosures:
                    continue
                links = []
                seen_urls: set[str] = set()
                for record in disclosures:
                    canonical_url = canonical_official_url(record.official_url)
                    if canonical_url in seen_urls:
                        continue
                    seen_urls.add(canonical_url)
                    links.append(
                        {
                            "title": record.title,
                            "url": canonical_url,
                            "official": True,
                        }
                    )
                summary = event.current_summary or event.normalized_claim[:1000]
                special_review = event.verification_status in {
                    VerificationStatus.CORRECTED,
                    VerificationStatus.OFFICIALLY_DENIED,
                    VerificationStatus.CONFLICTING,
                }
                strength = Strength.MEDIUM.value if special_review else Strength.LOW.value
                conditions = (
                    ["정정·공식 부인 또는 상충 자료의 후속 공시 확인"]
                    if special_review
                    else ["공식 공시의 세부 내용과 후속 변경 여부 확인"]
                )
                if existing is not None:
                    changed = any(
                        (
                            existing.one_line_summary != summary,
                            existing.source_links != links,
                            existing.verification_status != event.verification_status.value,
                            existing.impact_strength != strength,
                        )
                    )
                    if changed:
                        existing.one_line_summary = summary
                        existing.source_links = links
                        existing.verification_status = event.verification_status.value
                        existing.impact_strength = strength
                        existing.conditions_to_watch = conditions
                        existing.generated_at = self.clock.now()
                    continue
                if not event.material_change:
                    continue
                self.session.add(
                    PortfolioImpactRecord(
                        event_id=event.id,
                        portfolio_item_id=item.id,
                        thesis_id=thesis.id if thesis else None,
                        relevance=ImpactRelevance.DIRECT.value,
                        impact_direction=ImpactDirection.UNCLEAR.value,
                        impact_strength=strength,
                        impact_horizon=ImpactHorizon.UNKNOWN.value,
                        thesis_effect=ThesisEffect.UNKNOWN.value,
                        confidence=Confidence.LOW.value,
                        evidence_strength=(
                            Strength.MEDIUM.value
                            if event.official_source_count > 0
                            else Strength.LOW.value
                        ),
                        one_line_summary=summary,
                        impact_path=["등록 종목에 직접 연결된 정보 사건"],
                        supporting_factors=[],
                        opposing_factors=[],
                        conditions_to_watch=conditions,
                        invalidation_conditions=[],
                        missing_information=["투자근거에 미치는 방향은 사용자 검토 필요"],
                        source_links=links,
                        verification_status=event.verification_status.value,
                        generated_by=GeneratedBy.RULE_BASED.value,
                        generated_at=self.clock.now(),
                        valid_until=None,
                        human_decision_required=True,
                    )
                )
                created += 1
        if created:
            self.session.flush()
        return created

    def _draft(
        self,
        item: PortfolioItemRecord,
        *,
        manual_reference_price: Decimal | None,
    ) -> DecisionReviewRead:
        thesis_record = self.session.scalar(
            select(InvestmentThesisRecord).where(
                InvestmentThesisRecord.portfolio_item_id == item.id
            )
        )
        impacts = self.impacts(portfolio_item_id=item.id)
        verified_statuses = {
            VerificationStatus.OFFICIAL_CONFIRMED.value,
            VerificationStatus.MULTI_SOURCE_CONFIRMED.value,
            VerificationStatus.CORRECTED.value,
            VerificationStatus.OFFICIALLY_DENIED.value,
            VerificationStatus.CONFLICTING.value,
        }
        material_event_ids = set(
            self.session.scalars(
                select(InformationEventRecord.id).where(
                    InformationEventRecord.material_change.is_(True)
                )
            )
        )
        verified_impacts = [
            impact
            for impact in impacts
            if impact.verification_status in verified_statuses
            and impact.verification_status != VerificationStatus.STALE_REUSED.value
            and impact.event_id in material_event_ids
        ]
        thesis_status = ThesisStatus.NOT_SET
        direction = DecisionDirection.INSUFFICIENT_DATA
        why_now = "연결된 공식 공시와 검증 정보가 부족합니다."
        confidence = Confidence.LOW
        evidence_strength = Strength.LOW
        positive_impacts = [
            impact
            for impact in verified_impacts
            if impact.impact_direction == ImpactDirection.POSITIVE.value
        ]
        negative_impacts = [
            impact
            for impact in verified_impacts
            if impact.impact_direction == ImpactDirection.NEGATIVE.value
        ]
        mixed_impacts = [
            impact
            for impact in verified_impacts
            if impact.impact_direction == ImpactDirection.MIXED.value
            or impact.verification_status == VerificationStatus.CONFLICTING.value
        ]
        special_review_impacts = [
            impact
            for impact in verified_impacts
            if impact.verification_status
            in {
                VerificationStatus.CORRECTED.value,
                VerificationStatus.OFFICIALLY_DENIED.value,
                VerificationStatus.CONFLICTING.value,
            }
        ]
        break_impacts = [
            impact
            for impact in verified_impacts
            if impact.thesis_effect == ThesisEffect.BREAKS.value
        ]
        weakening_impacts = [
            impact
            for impact in verified_impacts
            if impact.thesis_effect
            in {
                ThesisEffect.SLIGHTLY_WEAKENS.value,
                ThesisEffect.WEAKENS.value,
            }
        ]
        strengthening_count = sum(
            1
            for impact in verified_impacts
            if impact.thesis_effect
            in {
                ThesisEffect.STRENGTHENS.value,
                ThesisEffect.SLIGHTLY_STRENGTHENS.value,
            }
        )

        if verified_impacts:
            confidence = Confidence.MEDIUM
            evidence_strength = (
                Strength.HIGH
                if any(
                    impact.evidence_strength == Strength.HIGH.value
                    for impact in verified_impacts
                )
                else Strength.MEDIUM
            )

        if break_impacts:
            thesis_status = ThesisStatus.BROKEN
            direction = DecisionDirection.EXIT_REVIEW
            why_now = (
                "공식·검증 정보에서 핵심 근거 훼손 신호가 확인되어 청산 여부 검토가 필요합니다."
            )
        elif mixed_impacts or (positive_impacts and negative_impacts):
            thesis_status = ThesisStatus.REVIEW_REQUIRED
            direction = DecisionDirection.WAIT
            why_now = (
                "긍정·부정 또는 상충하는 검증 자료가 함께 있어 추가 공식 확인이 필요합니다."
            )
        elif special_review_impacts:
            thesis_status = ThesisStatus.REVIEW_REQUIRED
            direction = DecisionDirection.WAIT
            why_now = "정정·공식 부인 정보가 확인되어 기존 판단을 다시 검토해야 합니다."
        elif weakening_impacts or negative_impacts:
            thesis_status = (
                ThesisStatus.WEAKENED
                if any(
                    impact.thesis_effect == ThesisEffect.WEAKENS.value
                    for impact in weakening_impacts
                )
                or negative_impacts
                else ThesisStatus.PARTIALLY_BROKEN
            )
            direction = DecisionDirection.REDUCE_REVIEW
            why_now = "공식·검증 정보에서 부정적 영향 또는 근거 약화 신호가 확인되었습니다."
        elif strengthening_count >= 2 and positive_impacts:
            thesis_status = ThesisStatus.STRENGTHENED
            direction = DecisionDirection.ADD_REVIEW
            why_now = (
                "복수의 공식·검증 정보가 기존 투자근거를 강화했습니다. "
                "위험 한도와 가격 조건은 사용자가 별도로 확인해야 합니다."
            )
        elif positive_impacts:
            thesis_status = ThesisStatus.ACTIVE
            direction = DecisionDirection.HOLD
            why_now = (
                "공식·검증 정보가 긍정적이지만 현재 자료만으로 포지션 변경을 단정하지 않습니다."
            )
        elif verified_impacts:
            thesis_status = ThesisStatus.REVIEW_REQUIRED
            direction = DecisionDirection.WAIT
            why_now = (
                "공식 공시는 확인됐지만 종목에 미치는 긍정·부정 방향은 추가 검토가 필요합니다."
            )

        missing = []
        if not verified_impacts:
            missing.append("VERIFIED_PORTFOLIO_IMPACT")
        if manual_reference_price is None:
            missing.append("OPTIONAL_MANUAL_PRICE_CONTEXT")
        profile = self.session.get(RiskProfileRecord, "default")
        risk_snapshot: dict[str, object] = {
            "configured": profile is not None,
            "automaticChangeAllowed": False,
        }
        now = self.clock.now()
        return DecisionReviewRead(
            id=None,
            portfolio_item_id=item.id,
            thesis_id=thesis_record.id if thesis_record else None,
            direction=direction,
            thesis_status=thesis_status,
            confidence=confidence,
            evidence_strength=evidence_strength,
            why_now=why_now,
            supporting_evidence=self._unique(
                [
                    value
                    for impact in positive_impacts
                    for value in [impact.one_line_summary, *impact.supporting_factors]
                ]
            )[:3],
            contrary_evidence=self._unique(
                [
                    value
                    for impact in [*negative_impacts, *mixed_impacts]
                    for value in [impact.one_line_summary, *impact.opposing_factors]
                ]
            )[:3],
            positive_factors=self._unique(
                [impact.one_line_summary for impact in positive_impacts]
            )[:3],
            negative_factors=self._unique(
                [impact.one_line_summary for impact in [*negative_impacts, *mixed_impacts]]
            )[:3],
            conditions_to_add=[],
            conditions_to_hold=[],
            conditions_to_reduce=self._unique(
                [
                    condition
                    for impact in [*negative_impacts, *mixed_impacts]
                    for condition in impact.conditions_to_watch
                ]
            ),
            conditions_to_exit=self._unique(
                [
                    condition
                    for impact in break_impacts
                    for condition in impact.invalidation_conditions
                ]
            ),
            invalidation_conditions=self._unique(
                [
                    condition
                    for impact in verified_impacts
                    for condition in impact.invalidation_conditions
                ]
            ),
            missing_information=missing,
            manual_reference_price=manual_reference_price,
            average_cost_snapshot=item.average_price,
            quantity_snapshot=item.quantity,
            risk_profile_snapshot=risk_snapshot,
            based_on_event_ids=[impact.event_id for impact in verified_impacts],
            generated_by=GeneratedBy.RULE_BASED,
            generated_at=now,
            valid_until=now + timedelta(days=7),
            acknowledged_at=None,
            user_decision=None,
            human_decision_required=True,
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value.strip()))

    @staticmethod
    def _same_analysis(record: DecisionReviewRecord, draft: DecisionReviewRead) -> bool:
        current = DecisionReviewRead.model_validate(record)
        excluded = {
            "id",
            "generated_at",
            "valid_until",
            "acknowledged_at",
            "user_decision",
        }
        return current.model_dump(exclude=excluded, mode="python") == draft.model_dump(
            exclude=excluded,
            mode="python",
        )

    @staticmethod
    def _copy_text(
        item: PortfolioItemRecord,
        _thesis: InvestmentThesisRead,
        impacts: list[PortfolioImpactRead],
        review: DecisionReviewRead,
        links: list[SourceLink],
        questions: list[str],
    ) -> str:
        def bullets(values: list[str]) -> str:
            return "\n".join(f"- {value}" for value in values) or "- 없음"

        impact_lines = [
            f"- [{impact.verification_status}] {impact.one_line_summary}" for impact in impacts
        ]
        link_lines = [f"- {link.title}: {link.url}" for link in links]
        return "\n".join(
            [
                "다음 종목의 투자근거와 최근 검증 정보를 분석해 주세요.",
                "추가매수 검토·유지·관망·비중축소 검토·손절·청산 검토 중",
                "어느 방향이 적절한지 설명하고 반대 근거와 판단 무효화 조건도 포함해 주세요.",
                "현재가와 주문은 제가 별도 금융 앱에서 확인합니다.",
                "",
                f"종목: {item.name} ({item.symbol}, {item.market})",
                f"상태: {item.position_status.value} / {item.tracking_status.value}",
                f"보유수량: {item.quantity}",
                f"평균단가: {item.average_price or '미입력'} {item.currency.value}",
                f"투자기간: {item.investment_horizon.value}",
                "",
                f"자동 분석 상태: {review.thesis_status.value}",
                "긍정 근거:",
                bullets(review.positive_factors),
                "부정 근거:",
                bullets(review.negative_factors),
                "",
                "최근 구조화 정보:",
                "\n".join(impact_lines) or "- 없음",
                f"현재 규칙 기반 방향: {review.direction.value}",
                f"한 줄 이유: {review.why_now}",
                "",
                "확인 질문:",
                bullets(questions),
                "",
                "공식·원문 링크:",
                "\n".join(link_lines) or "- 없음",
                "",
                "※ 기사·공시 전문은 포함하지 않았고, 최종 판단과 주문은 사용자 책임입니다.",
            ]
        )
