from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.database import HoldingStatus, PortfolioItemRecord
from app.models.disclosures import (
    DisclosureRecord,
    InformationEventRecord,
    NewsReferenceRecord,
)
from app.models.operations import (
    BriefingRecord,
    BriefingType,
    NotificationPreferenceRecord,
)
from app.schemas.market_briefings import MarketBriefingPreviewRead
from app.services.market_calendar import (
    MarketCode,
    MarketScheduleService,
    ScheduleStatus,
    briefing_market,
)

KRX_MARKETS = {"KRX", "KOSPI", "KOSDAQ"}
US_MARKETS = {"NASDAQ", "NYSE", "AMEX"}


class MarketBriefingPreviewService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        schedules: MarketScheduleService,
    ) -> None:
        self.session = session
        self.settings = settings
        self.schedules = schedules

    def preview(
        self,
        briefing_type: BriefingType,
        *,
        session_date: date,
        now: datetime | None = None,
    ) -> MarketBriefingPreviewRead:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        preference = self.session.get(NotificationPreferenceRecord, "default")
        schedule = self.schedules.schedule(briefing_type, session_date, preference)
        market = briefing_market(briefing_type)
        previous = self.session.scalar(
            select(BriefingRecord.generated_at)
            .where(BriefingRecord.briefing_type == briefing_type)
            .order_by(BriefingRecord.generated_at.desc())
            .limit(1)
        )
        period_start = previous or current - timedelta(hours=24)
        portfolios = self._portfolios(market, preference)
        instrument_ids = {item.instrument_id for item in portfolios if item.instrument_id}
        events = (
            list(
                self.session.scalars(
                    select(InformationEventRecord).where(
                        InformationEventRecord.instrument_id.in_(instrument_ids),
                        InformationEventRecord.last_seen_at >= period_start,
                        InformationEventRecord.last_seen_at <= current,
                    )
                )
            )
            if instrument_ids
            else []
        )
        event_ids = [event.id for event in events]
        disclosures = (
            list(
                self.session.scalars(
                    select(DisclosureRecord)
                    .where(DisclosureRecord.event_id.in_(event_ids))
                    .order_by(DisclosureRecord.published_at.desc())
                    .limit(10)
                )
            )
            if event_ids
            else []
        )
        news = (
            list(
                self.session.scalars(
                    select(NewsReferenceRecord)
                    .where(NewsReferenceRecord.information_event_id.in_(event_ids))
                    .order_by(NewsReferenceRecord.published_at.desc())
                    .limit(10)
                )
            )
            if event_ids
            else []
        )
        provider_ready = self._provider_ready(market)
        calendar_ready = schedule.session.schedule_status is ScheduleStatus.CONFIRMED
        data_missing = not provider_ready or not calendar_ready
        if not calendar_ready:
            data_message = "시장 Calendar가 미설정되어 실제 일정을 확인할 수 없습니다."
        elif not provider_ready:
            data_message = (
                "일부 데이터 제공자가 미설정 또는 실패 상태여서 완전한 확인이 불가능합니다."
            )
        elif not events:
            data_message = "이번 조사 구간에 새롭게 확인된 중요 공시·정정·공식 부인은 없습니다."
        else:
            data_message = "확인된 자료만 포함했습니다."
        label = {
            BriefingType.KRX_PRE_OPEN: "국내장 개장 전",
            BriefingType.KRX_POST_CLOSE: "국내장 마감 후",
            BriefingType.NASDAQ_PRE_OPEN: "나스닥 개장 전",
            BriefingType.NASDAQ_POST_CLOSE: "나스닥 마감 후",
        }[briefing_type]
        links = [{"title": item.title, "url": item.official_url} for item in disclosures] + [
            {"title": item.title, "url": item.canonical_url} for item in news
        ]
        return MarketBriefingPreviewRead(
            briefing_type=briefing_type,
            market=market,
            session_date=session_date,
            schedule_status=schedule.session.schedule_status,
            investigation_start=period_start,
            investigation_end=current,
            related_instrument_count=len(portfolios),
            official_disclosure_count=len(disclosures),
            news_reference_count=len(news),
            material_change_count=sum(int(event.material_change) for event in events),
            data_missing=data_missing,
            data_status_message=data_message,
            email_subject=f"[Investment AI Radar] {label} 브리핑",
            body_sections=[
                {
                    "title": "대상과 조사 구간",
                    "content": (
                        f"{market.value} 관련 Portfolio {len(portfolios)}개, "
                        f"{period_start.isoformat()} ~ {current.isoformat()}"
                    ),
                },
                {
                    "title": "공식 공시와 뉴스 참조",
                    "content": (f"공식 공시 {len(disclosures)}건, 뉴스 참조 {len(news)}건"),
                },
                {"title": "데이터 상태", "content": data_message},
            ],
            source_links=links,
        )

    def _portfolios(
        self,
        market: MarketCode,
        preference: NotificationPreferenceRecord | None,
    ) -> list[PortfolioItemRecord]:
        markets = KRX_MARKETS if market is MarketCode.KRX else US_MARKETS
        statuses = [HoldingStatus.HOLDING]
        if preference is None or preference.include_watchlist:
            statuses.append(HoldingStatus.WATCHLIST)
        if preference and preference.include_reentry_watch:
            statuses.append(HoldingStatus.REENTRY_WATCH)
        if preference and preference.include_sold:
            statuses.append(HoldingStatus.SOLD)
        return list(
            self.session.scalars(
                select(PortfolioItemRecord).where(
                    PortfolioItemRecord.archived_at.is_(None),
                    PortfolioItemRecord.market.in_(markets),
                    PortfolioItemRecord.holding_status.in_(statuses),
                )
            )
        )

    def _provider_ready(self, market: MarketCode) -> bool:
        official = (
            self.settings.open_dart_configured
            if market is MarketCode.KRX
            else self.settings.sec_configured
        )
        return official and self.settings.news_configured


def sent_email_count(session: Session) -> int:
    from app.models.operations import DeliveryStatus, NotificationDeliveryRecord

    return int(
        session.scalar(
            select(func.count())
            .select_from(NotificationDeliveryRecord)
            .where(NotificationDeliveryRecord.status == DeliveryStatus.SENT)
        )
        or 0
    )
