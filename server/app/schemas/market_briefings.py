from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.operations import BriefingType
from app.services.market_calendar import MarketCode, ScheduleStatus


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class MarketSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class MarketSessionRead(MarketSchema):
    market: MarketCode
    session_date: date
    market_timezone: str
    open_at: datetime | None
    close_at: datetime | None
    pre_open_briefing_at: datetime | None
    post_close_briefing_at: datetime | None
    holiday: bool
    early_close: bool
    schedule_status: ScheduleStatus
    source: str | None
    fetched_at: datetime | None
    verified_at: datetime | None


class MarketSessionList(MarketSchema):
    items: list[MarketSessionRead]
    calendar_configured: bool


class NextMarketBriefingRead(MarketSchema):
    briefing_type: BriefingType
    market: MarketCode
    session_date: date
    market_timezone: str
    schedule_status: ScheduleStatus
    scheduled_at: datetime | None
    scheduled_at_kst: datetime | None
    offset_minutes: int
    enabled: bool
    holiday: bool
    early_close: bool
    source: str | None


class NextMarketBriefingList(MarketSchema):
    items: list[NextMarketBriefingRead]
    calendar_configured: bool


class MarketBriefingPreviewRead(MarketSchema):
    status: str = "PREVIEW"
    briefing_type: BriefingType
    market: MarketCode
    session_date: date
    schedule_status: ScheduleStatus
    investigation_start: datetime
    investigation_end: datetime
    related_instrument_count: int
    official_disclosure_count: int
    news_reference_count: int
    material_change_count: int
    data_missing: bool
    data_status_message: str
    email_subject: str
    body_sections: list[dict[str, object]] = Field(default_factory=list)
    source_links: list[dict[str, str]] = Field(default_factory=list)
    persisted: bool = False
    delivery_created: bool = False


class MarketBriefingStatusRead(MarketSchema):
    calendar_configured: bool
    krx_calendar_status: ScheduleStatus
    nasdaq_calendar_status: ScheduleStatus
    next_market_briefing: NextMarketBriefingRead | None
    enabled_market_briefing_count: int
    email_provider_status: str
    scheduler_configured: bool
    last_krx_briefing: datetime | None
    last_nasdaq_briefing: datetime | None
    actual_email_sent_count: int
