from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from importlib.util import find_spec
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models.operations import BriefingType, NotificationPreferenceRecord


class MarketCode(StrEnum):
    KRX = "KRX"
    NASDAQ = "NASDAQ"


class ScheduleStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    ESTIMATED = "ESTIMATED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    CLOSED = "CLOSED"


MARKET_TIMEZONES = {
    MarketCode.KRX: "Asia/Seoul",
    MarketCode.NASDAQ: "America/New_York",
}

MARKET_BRIEFING_TYPES = (
    BriefingType.KRX_PRE_OPEN,
    BriefingType.KRX_POST_CLOSE,
    BriefingType.NASDAQ_PRE_OPEN,
    BriefingType.NASDAQ_POST_CLOSE,
)


@dataclass(frozen=True, slots=True)
class MarketSession:
    market: MarketCode
    session_date: date
    market_timezone: str
    open_at: datetime | None
    close_at: datetime | None
    holiday: bool
    early_close: bool
    schedule_status: ScheduleStatus
    source: str | None
    fetched_at: datetime | None
    verified_at: datetime | None


@dataclass(frozen=True, slots=True)
class BriefingSchedule:
    briefing_type: BriefingType
    market: MarketCode
    session: MarketSession
    scheduled_at: datetime | None
    scheduled_at_kst: datetime | None
    offset_minutes: int
    enabled: bool
    idempotency_key: str


class MarketCalendarAdapter(Protocol):
    @property
    def configured(self) -> bool: ...

    def session(self, market: MarketCode, session_date: date) -> MarketSession: ...


class UnavailableMarketCalendarAdapter:
    @property
    def configured(self) -> bool:
        return False

    def session(self, market: MarketCode, session_date: date) -> MarketSession:
        return MarketSession(
            market=market,
            session_date=session_date,
            market_timezone=MARKET_TIMEZONES[market],
            open_at=None,
            close_at=None,
            holiday=False,
            early_close=False,
            schedule_status=ScheduleStatus.NOT_CONFIGURED,
            source=None,
            fetched_at=None,
            verified_at=None,
        )


class ExchangeCalendarsAdapter:
    """Optional adapter. It is active only when exchange_calendars is installed."""

    _names = {MarketCode.KRX: "XKRX", MarketCode.NASDAQ: "XNYS"}

    def __init__(self) -> None:
        import exchange_calendars  # type: ignore[import-not-found]

        self._module = exchange_calendars
        self._calendars = {
            market: exchange_calendars.get_calendar(name)
            for market, name in self._names.items()
        }

    @property
    def configured(self) -> bool:
        return True

    def session(self, market: MarketCode, session_date: date) -> MarketSession:
        calendar = self._calendars[market]
        label = session_date.isoformat()
        checked_at = datetime.now(UTC)
        if not calendar.is_session(label):
            return MarketSession(
                market=market,
                session_date=session_date,
                market_timezone=MARKET_TIMEZONES[market],
                open_at=None,
                close_at=None,
                holiday=True,
                early_close=False,
                schedule_status=ScheduleStatus.CLOSED,
                source=f"exchange_calendars:{self._names[market]}",
                fetched_at=checked_at,
                verified_at=checked_at,
            )
        opened = calendar.session_open(label).to_pydatetime().astimezone(UTC)
        closed = calendar.session_close(label).to_pydatetime().astimezone(UTC)
        local_close = closed.astimezone(ZoneInfo(MARKET_TIMEZONES[market]))
        regular_close_hour = 15 if market is MarketCode.KRX else 16
        return MarketSession(
            market=market,
            session_date=session_date,
            market_timezone=MARKET_TIMEZONES[market],
            open_at=opened,
            close_at=closed,
            holiday=False,
            early_close=local_close.hour < regular_close_hour,
            schedule_status=ScheduleStatus.CONFIRMED,
            source=f"exchange_calendars:{self._names[market]}",
            fetched_at=checked_at,
            verified_at=checked_at,
        )


def default_market_calendar(*, enabled: bool = True) -> MarketCalendarAdapter:
    if not enabled or find_spec("exchange_calendars") is None:
        return UnavailableMarketCalendarAdapter()
    try:
        return ExchangeCalendarsAdapter()
    except (ImportError, KeyError, RuntimeError, ValueError):
        return UnavailableMarketCalendarAdapter()


def briefing_market(briefing_type: BriefingType) -> MarketCode:
    if briefing_type in {
        BriefingType.KRX_PRE_OPEN,
        BriefingType.KRX_POST_CLOSE,
    }:
        return MarketCode.KRX
    if briefing_type in {
        BriefingType.NASDAQ_PRE_OPEN,
        BriefingType.NASDAQ_POST_CLOSE,
    }:
        return MarketCode.NASDAQ
    raise ValueError("시장 브리핑 유형이 아닙니다.")


def market_briefing_idempotency_key(briefing_type: BriefingType, session_date: date) -> str:
    return f"{briefing_type.value}:{session_date.isoformat()}"


class MarketScheduleService:
    def __init__(self, adapter: MarketCalendarAdapter) -> None:
        self.adapter = adapter

    def schedule(
        self,
        briefing_type: BriefingType,
        session_date: date,
        preference: NotificationPreferenceRecord | None = None,
    ) -> BriefingSchedule:
        market = briefing_market(briefing_type)
        session = self.adapter.session(market, session_date)
        offset, enabled = self._preference(briefing_type, preference)
        scheduled_at: datetime | None = None
        if session.schedule_status is ScheduleStatus.CONFIRMED:
            if briefing_type in {
                BriefingType.KRX_PRE_OPEN,
                BriefingType.NASDAQ_PRE_OPEN,
            }:
                if session.open_at is not None:
                    scheduled_at = session.open_at - timedelta(minutes=offset)
            elif session.close_at is not None:
                scheduled_at = session.close_at + timedelta(minutes=offset)
        return BriefingSchedule(
            briefing_type=briefing_type,
            market=market,
            session=session,
            scheduled_at=scheduled_at,
            scheduled_at_kst=(
                scheduled_at.astimezone(ZoneInfo("Asia/Seoul")) if scheduled_at else None
            ),
            offset_minutes=offset,
            enabled=enabled,
            idempotency_key=market_briefing_idempotency_key(briefing_type, session_date),
        )

    def next_schedule(
        self,
        briefing_type: BriefingType,
        *,
        now: datetime,
        preference: NotificationPreferenceRecord | None = None,
    ) -> BriefingSchedule:
        current = now.astimezone(UTC)
        market = briefing_market(briefing_type)
        local_date = current.astimezone(ZoneInfo(MARKET_TIMEZONES[market])).date()
        first = self.schedule(briefing_type, local_date, preference)
        if first.session.schedule_status is ScheduleStatus.NOT_CONFIGURED:
            return first
        for days in range(0, 371):
            candidate = self.schedule(
                briefing_type, local_date + timedelta(days=days), preference
            )
            if (
                candidate.session.schedule_status is ScheduleStatus.CONFIRMED
                and candidate.scheduled_at is not None
                and candidate.scheduled_at >= current
            ):
                return candidate
        return BriefingSchedule(
            briefing_type=briefing_type,
            market=market,
            session=MarketSession(
                market=market,
                session_date=local_date,
                market_timezone=MARKET_TIMEZONES[market],
                open_at=None,
                close_at=None,
                holiday=False,
                early_close=False,
                schedule_status=ScheduleStatus.UNAVAILABLE,
                source=None,
                fetched_at=None,
                verified_at=None,
            ),
            scheduled_at=None,
            scheduled_at_kst=None,
            offset_minutes=first.offset_minutes,
            enabled=first.enabled,
            idempotency_key=market_briefing_idempotency_key(briefing_type, local_date),
        )

    def due_schedules(
        self,
        *,
        now: datetime,
        preference: NotificationPreferenceRecord | None,
        existing_keys: set[str],
    ) -> list[BriefingSchedule]:
        current = now.astimezone(UTC)
        due: list[BriefingSchedule] = []
        for briefing_type in MARKET_BRIEFING_TYPES:
            market = briefing_market(briefing_type)
            local_day = current.astimezone(ZoneInfo(MARKET_TIMEZONES[market])).date()
            schedule = self.schedule(briefing_type, local_day, preference)
            if (
                schedule.enabled
                and schedule.session.schedule_status is ScheduleStatus.CONFIRMED
                and schedule.scheduled_at is not None
                and schedule.scheduled_at <= current
                and schedule.idempotency_key not in existing_keys
            ):
                due.append(schedule)
        return due

    @staticmethod
    def _preference(
        briefing_type: BriefingType,
        preference: NotificationPreferenceRecord | None,
    ) -> tuple[int, bool]:
        values = {
            BriefingType.KRX_PRE_OPEN: (
                "krx_pre_open_offset_minutes",
                "krx_pre_open_enabled",
                40,
            ),
            BriefingType.KRX_POST_CLOSE: (
                "krx_post_close_offset_minutes",
                "krx_post_close_enabled",
                20,
            ),
            BriefingType.NASDAQ_PRE_OPEN: (
                "nasdaq_pre_open_offset_minutes",
                "nasdaq_pre_open_enabled",
                60,
            ),
            BriefingType.NASDAQ_POST_CLOSE: (
                "nasdaq_post_close_offset_minutes",
                "nasdaq_post_close_enabled",
                20,
            ),
        }
        offset_name, enabled_name, default = values[briefing_type]
        if preference is None:
            return default, False
        stored_offset = getattr(preference, offset_name)
        return (
            int(stored_offset if stored_offset is not None else default),
            bool(getattr(preference, enabled_name)),
        )
