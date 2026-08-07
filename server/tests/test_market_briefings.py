from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database import Database
from app.models.operations import BriefingType, NotificationPreferenceRecord
from app.services.briefings import BriefingService
from app.services.market_briefings import MarketBriefingPreviewService
from app.services.market_calendar import (
    MARKET_TIMEZONES,
    MarketCode,
    MarketScheduleService,
    MarketSession,
    ScheduleStatus,
    UnavailableMarketCalendarAdapter,
    market_briefing_idempotency_key,
)


class StaticCalendar:
    def __init__(self, sessions: dict[tuple[MarketCode, date], MarketSession]) -> None:
        self.sessions = sessions

    @property
    def configured(self) -> bool:
        return True

    def session(self, market: MarketCode, session_date: date) -> MarketSession:
        return self.sessions.get(
            (market, session_date),
            MarketSession(
                market=market,
                session_date=session_date,
                market_timezone=MARKET_TIMEZONES[market],
                open_at=None,
                close_at=None,
                holiday=True,
                early_close=False,
                schedule_status=ScheduleStatus.CLOSED,
                source="verified-test-calendar",
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                verified_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        )


def confirmed(
    market: MarketCode,
    session_date: date,
    opened: datetime,
    closed: datetime,
    *,
    early_close: bool = False,
) -> MarketSession:
    return MarketSession(
        market=market,
        session_date=session_date,
        market_timezone=MARKET_TIMEZONES[market],
        open_at=opened,
        close_at=closed,
        holiday=False,
        early_close=early_close,
        schedule_status=ScheduleStatus.CONFIRMED,
        source="verified-test-calendar",
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        verified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_krx_pre_open_and_post_close_offsets() -> None:
    day = date(2026, 7, 27)
    adapter = StaticCalendar(
        {
            (MarketCode.KRX, day): confirmed(
                MarketCode.KRX,
                day,
                datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
                datetime(2026, 7, 27, 6, 30, tzinfo=UTC),
            )
        }
    )
    service = MarketScheduleService(adapter)
    pre = service.schedule(BriefingType.KRX_PRE_OPEN, day)
    post = service.schedule(BriefingType.KRX_POST_CLOSE, day)
    assert pre.scheduled_at == datetime(2026, 7, 26, 23, 20, tzinfo=UTC)
    assert pre.scheduled_at_kst.hour == 8
    assert pre.scheduled_at_kst.minute == 20
    assert post.scheduled_at == datetime(2026, 7, 27, 6, 50, tzinfo=UTC)


@pytest.mark.parametrize(
    ("day", "opened", "expected_kst_hour"),
    [
        (
            date(2026, 7, 27),
            datetime(2026, 7, 27, 13, 30, tzinfo=UTC),
            21,
        ),
        (
            date(2026, 1, 5),
            datetime(2026, 1, 5, 14, 30, tzinfo=UTC),
            22,
        ),
    ],
)
def test_nasdaq_dst_and_standard_time(
    day: date, opened: datetime, expected_kst_hour: int
) -> None:
    adapter = StaticCalendar(
        {
            (MarketCode.NASDAQ, day): confirmed(
                MarketCode.NASDAQ,
                day,
                opened,
                opened.replace(hour=opened.hour + 6, minute=0),
            )
        }
    )
    schedule = MarketScheduleService(adapter).schedule(BriefingType.NASDAQ_PRE_OPEN, day)
    assert schedule.scheduled_at == opened.replace(hour=opened.hour - 1)
    assert schedule.scheduled_at_kst.hour == expected_kst_hour
    assert ZoneInfo(schedule.session.market_timezone).key == "America/New_York"


def test_holiday_has_no_schedule() -> None:
    day = date(2026, 7, 28)
    schedule = MarketScheduleService(StaticCalendar({})).schedule(
        BriefingType.KRX_PRE_OPEN, day
    )
    assert schedule.session.schedule_status is ScheduleStatus.CLOSED
    assert schedule.session.holiday is True
    assert schedule.scheduled_at is None


def test_early_close_uses_actual_close() -> None:
    day = date(2026, 7, 3)
    closed = datetime(2026, 7, 3, 17, 0, tzinfo=UTC)
    adapter = StaticCalendar(
        {
            (MarketCode.NASDAQ, day): confirmed(
                MarketCode.NASDAQ,
                day,
                datetime(2026, 7, 3, 13, 30, tzinfo=UTC),
                closed,
                early_close=True,
            )
        }
    )
    schedule = MarketScheduleService(adapter).schedule(BriefingType.NASDAQ_POST_CLOSE, day)
    assert schedule.session.early_close is True
    assert schedule.scheduled_at == datetime(2026, 7, 3, 17, 20, tzinfo=UTC)


def test_unconfigured_calendar_never_estimates_time() -> None:
    schedule = MarketScheduleService(UnavailableMarketCalendarAdapter()).schedule(
        BriefingType.NASDAQ_PRE_OPEN, date(2026, 7, 27)
    )
    assert schedule.session.schedule_status is ScheduleStatus.NOT_CONFIGURED
    assert schedule.scheduled_at is None
    assert schedule.session.source is None


def test_market_idempotency_key_is_type_and_session() -> None:
    assert (
        market_briefing_idempotency_key(BriefingType.KRX_PRE_OPEN, date(2026, 7, 27))
        == "KRX_PRE_OPEN:2026-07-27"
    )


def test_due_schedule_respects_enabled_time_and_duplicate() -> None:
    day = date(2026, 7, 27)
    adapter = StaticCalendar(
        {
            (MarketCode.KRX, day): confirmed(
                MarketCode.KRX,
                day,
                datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
                datetime(2026, 7, 27, 6, 30, tzinfo=UTC),
            )
        }
    )
    preference = NotificationPreferenceRecord(
        krx_pre_open_enabled=True,
        krx_post_close_enabled=False,
    )
    service = MarketScheduleService(adapter)
    due = service.due_schedules(
        now=datetime(2026, 7, 26, 23, 30, tzinfo=UTC),
        preference=preference,
        existing_keys=set(),
    )
    assert [item.briefing_type for item in due] == [BriefingType.KRX_PRE_OPEN]
    blocked = service.due_schedules(
        now=datetime(2026, 7, 26, 23, 30, tzinfo=UTC),
        preference=preference,
        existing_keys={"KRX_PRE_OPEN:2026-07-27"},
    )
    assert blocked == []


def test_notification_market_preferences_roundtrip(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/notification-preferences",
        json={
            "krxPreOpenEnabled": True,
            "krxPostCloseEnabled": True,
            "nasdaqPreOpenEnabled": True,
            "nasdaqPostCloseEnabled": True,
            "dailyDigestEnabled": True,
            "immediateMaterialChangeEnabled": True,
            "correctionNoticeEnabled": True,
            "providerFailureNoticeEnabled": True,
            "includeWatchlist": True,
            "includeReentryWatch": True,
            "includeSold": False,
            "sendNoMaterialChangeBriefing": True,
            "krxPreOpenOffsetMinutes": 35,
            "krxPostCloseOffsetMinutes": 25,
            "nasdaqPreOpenOffsetMinutes": 55,
            "nasdaqPostCloseOffsetMinutes": 15,
            "timezone": "Asia/Seoul",
            "minimumPriority": 70,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["krxPreOpenEnabled"] is True
    assert body["includeReentryWatch"] is True
    assert body["includeHoldings"] is True
    assert body["includeSold"] is False
    assert body["nasdaqPreOpenOffsetMinutes"] == 55
    assert body["emailProviderStatus"] == "NOT_CONFIGURED"


def test_notification_offset_range_rejected(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/notification-preferences",
        json={"krxPreOpenOffsetMinutes": 241},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "briefing_type",
    [
        "KRX_PRE_OPEN",
        "KRX_POST_CLOSE",
        "NASDAQ_PRE_OPEN",
        "NASDAQ_POST_CLOSE",
    ],
)
def test_market_preview_is_non_persistent_and_marks_missing_data(
    api_client: TestClient, briefing_type: str
) -> None:
    response = api_client.get(
        "/api/v1/briefings/market-preview",
        params={
            "briefingType": briefing_type,
            "sessionDate": "2026-07-27",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "PREVIEW"
    assert body["scheduleStatus"] == "NOT_CONFIGURED"
    assert body["dataMissing"] is True
    assert body["persisted"] is False
    assert body["deliveryCreated"] is False
    assert "기사 전문" not in str(body)


def test_market_session_and_status_apis_are_safe_when_unconfigured(
    api_client: TestClient,
) -> None:
    sessions = api_client.get("/api/v1/market-sessions", params={"sessionDate": "2026-07-27"})
    assert sessions.status_code == 200
    assert len(sessions.json()["items"]) == 2
    assert all(item["scheduleStatus"] == "NOT_CONFIGURED" for item in sessions.json()["items"])
    next_response = api_client.get("/api/v1/market-sessions/next")
    assert next_response.status_code == 200
    assert len(next_response.json()["items"]) == 4
    status = api_client.get("/api/v1/operations/market-briefing-status")
    assert status.status_code == 200
    assert status.json()["schedulerConfigured"] is False
    assert status.json()["actualEmailSentCount"] == 0


def test_provider_failure_is_not_reported_as_no_change(
    api_database: Database,
) -> None:
    day = date(2026, 7, 27)
    schedule_service = MarketScheduleService(
        StaticCalendar(
            {
                (MarketCode.KRX, day): confirmed(
                    MarketCode.KRX,
                    day,
                    datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
                    datetime(2026, 7, 27, 6, 30, tzinfo=UTC),
                )
            }
        )
    )
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        preview = MarketBriefingPreviewService(session, settings, schedule_service).preview(
            BriefingType.KRX_PRE_OPEN,
            session_date=day,
            now=datetime(2026, 7, 26, 23, 30, tzinfo=UTC),
        )
    assert preview.data_missing is True
    assert "완전한 확인이 불가능" in preview.data_status_message
    assert "중요 공시" not in preview.data_status_message


def test_complete_providers_can_report_no_material_change(
    api_database: Database,
) -> None:
    day = date(2026, 7, 27)
    schedule_service = MarketScheduleService(
        StaticCalendar(
            {
                (MarketCode.KRX, day): confirmed(
                    MarketCode.KRX,
                    day,
                    datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
                    datetime(2026, 7, 27, 6, 30, tzinfo=UTC),
                )
            }
        )
    )
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "OPENDART_SYNC_ENABLED": "true",
            "OPENDART_API_KEY": "1234567890123456789012345678901234567890",
            "NEWS_SYNC_ENABLED": "true",
            "NEWS_FEED_SYNC_ENABLED": "true",
        }
    )
    with api_database.session_scope() as session:
        preview = MarketBriefingPreviewService(session, settings, schedule_service).preview(
            BriefingType.KRX_POST_CLOSE,
            session_date=day,
            now=datetime(2026, 7, 27, 7, 0, tzinfo=UTC),
        )
    assert preview.data_missing is False
    assert "새롭게 확인된" in preview.data_status_message


def test_expanded_risk_profile_and_conditional_policy(
    api_client: TestClient,
) -> None:
    payload = {
        "riskStyle": "CUSTOM",
        "primaryGoal": "BALANCED_GROWTH",
        "defaultInvestmentHorizon": "LONG",
        "maxSinglePositionPercent": "20.1250",
        "portfolioLossReviewPercent": "15.5000",
        "defaultLossReviewPercent": "8.2500",
        "defaultProfitReviewPercent": "25.7500",
        "minimumCashPercent": "10.0000",
        "maxSingleAdditionalBuyPercent": "5.0000",
        "averagingDownPolicy": "CONDITIONAL",
        "maxAveragingDownCount": 2,
        "requireOfficialEvidenceForAveragingDown": True,
        "highVolatilityAssetLimitPercent": "25.0000",
        "cryptoAssetLimitPercent": "10.0000",
        "notes": "검토 기준",
        "acknowledgedAt": "2026-07-26T00:00:00Z",
    }
    response = api_client.put("/api/v1/risk-profile", json=payload)
    assert response.status_code == 200, response.text
    profile = response.json()["profile"]
    assert profile["riskStyle"] == "CUSTOM"
    assert profile["maxSinglePositionPercent"] == "20.1250"
    assert profile["averagingDownPolicy"] == "CONDITIONAL"
    assert profile["acknowledgedAt"] == "2026-07-26T00:00:00Z"


def test_conditional_averaging_requires_condition(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/risk-profile",
        json={"averagingDownPolicy": "CONDITIONAL"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RISK_PROFILE_VALIDATION_ERROR"


def test_market_briefing_exact_session_key_reuses_record(
    api_database: Database,
) -> None:
    key = "KRX_PRE_OPEN:2026-07-27"
    with api_database.session_scope() as session:
        service = BriefingService(session)
        first = service.generate(
            period_start=datetime(2026, 7, 26, 0, 0, tzinfo=UTC),
            period_end=datetime(2026, 7, 26, 23, 20, tzinfo=UTC),
            now=datetime(2026, 7, 26, 23, 20, tzinfo=UTC),
            briefing_type=BriefingType.KRX_PRE_OPEN,
            idempotency_key_override=key,
            preserve_briefing_type=True,
            include_no_change=True,
        )
        second = service.generate(
            period_start=datetime(2026, 7, 26, 0, 0, tzinfo=UTC),
            period_end=datetime(2026, 7, 26, 23, 20, tzinfo=UTC),
            now=datetime(2026, 7, 26, 23, 21, tzinfo=UTC),
            briefing_type=BriefingType.KRX_PRE_OPEN,
            idempotency_key_override=key,
            preserve_briefing_type=True,
            include_no_change=True,
        )
        assert second.briefing.id == first.briefing.id
        assert second.briefing.idempotency_key == key


def test_openapi_exposes_read_only_market_operations(
    api_client: TestClient,
) -> None:
    schema = api_client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    expected = {
        "/api/v1/market-sessions",
        "/api/v1/market-sessions/next",
        "/api/v1/briefings/market-preview",
        "/api/v1/operations/market-briefing-status",
    }
    assert expected <= set(paths)
    read_only_market_paths = {path: paths[path] for path in expected}
    assert all("post" not in methods for methods in read_only_market_paths.values())
    assert "post" in paths["/api/v1/briefings/generate"]
