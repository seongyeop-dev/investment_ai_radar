from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.core.config import Settings
from app.models.operations import (
    BriefingRecord,
    BriefingType,
    NotificationPreferenceRecord,
)
from app.schemas.market_briefings import (
    MarketBriefingPreviewRead,
    MarketBriefingStatusRead,
    MarketSessionList,
    MarketSessionRead,
    NextMarketBriefingList,
    NextMarketBriefingRead,
)
from app.services.market_briefings import (
    MarketBriefingPreviewService,
    sent_email_count,
)
from app.services.market_calendar import (
    MARKET_BRIEFING_TYPES,
    MarketCode,
    MarketScheduleService,
    default_market_calendar,
)

router = APIRouter(prefix="/api/v1", tags=["market-briefings"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _schedule_service(settings: Settings) -> MarketScheduleService:
    return MarketScheduleService(
        default_market_calendar(enabled=settings.market_calendar_enabled)
    )


def _next_read(schedule: object) -> NextMarketBriefingRead:
    from app.services.market_calendar import BriefingSchedule

    assert isinstance(schedule, BriefingSchedule)
    return NextMarketBriefingRead(
        briefing_type=schedule.briefing_type,
        market=schedule.market,
        session_date=schedule.session.session_date,
        market_timezone=schedule.session.market_timezone,
        schedule_status=schedule.session.schedule_status,
        scheduled_at=schedule.scheduled_at,
        scheduled_at_kst=schedule.scheduled_at_kst,
        offset_minutes=schedule.offset_minutes,
        enabled=schedule.enabled,
        holiday=schedule.session.holiday,
        early_close=schedule.session.early_close,
        source=schedule.session.source,
    )


@router.get("/market-sessions", response_model=MarketSessionList)
def market_sessions(
    request: Request,
    session: SessionDependency,
    session_date: Annotated[date | None, Query(alias="sessionDate")] = None,
) -> MarketSessionList:
    target = session_date or datetime.now(ZoneInfo("Asia/Seoul")).date()
    preference = session.get(NotificationPreferenceRecord, "default")
    service = _schedule_service(request.app.state.settings)
    items: list[MarketSessionRead] = []
    for market, pre_type, post_type in (
        (MarketCode.KRX, BriefingType.KRX_PRE_OPEN, BriefingType.KRX_POST_CLOSE),
        (
            MarketCode.NASDAQ,
            BriefingType.NASDAQ_PRE_OPEN,
            BriefingType.NASDAQ_POST_CLOSE,
        ),
    ):
        pre = service.schedule(pre_type, target, preference)
        post = service.schedule(post_type, target, preference)
        market_session = pre.session
        items.append(
            MarketSessionRead(
                market=market,
                session_date=target,
                market_timezone=market_session.market_timezone,
                open_at=market_session.open_at,
                close_at=market_session.close_at,
                pre_open_briefing_at=pre.scheduled_at,
                post_close_briefing_at=post.scheduled_at,
                holiday=market_session.holiday,
                early_close=market_session.early_close,
                schedule_status=market_session.schedule_status,
                source=market_session.source,
                fetched_at=market_session.fetched_at,
                verified_at=market_session.verified_at,
            )
        )
    return MarketSessionList(items=items, calendar_configured=service.adapter.configured)


@router.get("/market-sessions/next", response_model=NextMarketBriefingList)
def next_market_sessions(
    request: Request, session: SessionDependency
) -> NextMarketBriefingList:
    preference = session.get(NotificationPreferenceRecord, "default")
    service = _schedule_service(request.app.state.settings)
    now = datetime.now(UTC)
    return NextMarketBriefingList(
        items=[
            _next_read(service.next_schedule(briefing_type, now=now, preference=preference))
            for briefing_type in MARKET_BRIEFING_TYPES
        ],
        calendar_configured=service.adapter.configured,
    )


@router.get(
    "/briefings/market-preview",
    response_model=MarketBriefingPreviewRead,
)
def market_preview(
    briefing_type: Annotated[BriefingType, Query(alias="briefingType")],
    request: Request,
    session: SessionDependency,
    session_date: Annotated[date | None, Query(alias="sessionDate")] = None,
) -> MarketBriefingPreviewRead:
    if briefing_type not in MARKET_BRIEFING_TYPES:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="시장 브리핑 유형이 아닙니다.")
    settings: Settings = request.app.state.settings
    service = _schedule_service(settings)
    market = MarketCode.KRX if briefing_type.value.startswith("KRX") else MarketCode.NASDAQ
    timezone = ZoneInfo("Asia/Seoul" if market is MarketCode.KRX else "America/New_York")
    target = session_date or datetime.now(timezone).date()
    return MarketBriefingPreviewService(session, settings, service).preview(
        briefing_type, session_date=target
    )


@router.get(
    "/operations/market-briefing-status",
    response_model=MarketBriefingStatusRead,
)
def market_briefing_status(
    request: Request,
    session: SessionDependency,
) -> MarketBriefingStatusRead:
    preference = session.get(NotificationPreferenceRecord, "default")
    settings: Settings = request.app.state.settings
    service = _schedule_service(settings)
    now = datetime.now(UTC)
    schedules = [
        service.next_schedule(kind, now=now, preference=preference)
        for kind in MARKET_BRIEFING_TYPES
    ]
    enabled = [schedule for schedule in schedules if schedule.enabled]
    next_enabled = min(
        (schedule for schedule in enabled if schedule.scheduled_at is not None),
        key=lambda item: item.scheduled_at or now,
        default=None,
    )

    def last_for(types: tuple[BriefingType, ...]) -> datetime | None:
        return session.scalar(
            select(BriefingRecord.generated_at)
            .where(BriefingRecord.briefing_type.in_(types))
            .order_by(BriefingRecord.generated_at.desc())
            .limit(1)
        )

    return MarketBriefingStatusRead(
        calendar_configured=service.adapter.configured,
        krx_calendar_status=schedules[0].session.schedule_status,
        nasdaq_calendar_status=schedules[2].session.schedule_status,
        next_market_briefing=(_next_read(next_enabled) if next_enabled else None),
        enabled_market_briefing_count=len(enabled),
        email_provider_status=("READY" if settings.email_configured else "NOT_CONFIGURED"),
        scheduler_configured=settings.scheduler_configured,
        last_krx_briefing=last_for((BriefingType.KRX_PRE_OPEN, BriefingType.KRX_POST_CLOSE)),
        last_nasdaq_briefing=last_for(
            (
                BriefingType.NASDAQ_PRE_OPEN,
                BriefingType.NASDAQ_POST_CLOSE,
            )
        ),
        actual_email_sent_count=sent_email_count(session),
    )
