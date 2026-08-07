from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.database import Database
from app.models.contracts import VerificationStatus
from app.models.database import (
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
)
from app.models.disclosures import (
    AssetType,
    CollectionRunRecord,
    CollectionRunType,
    CollectionStatus,
    InformationEventRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    LifecycleStatus,
    ProviderName,
)
from app.models.operations import (
    Availability,
    BriefingItemRecord,
    BriefingRecord,
    BriefingStatus,
    BriefingType,
    DeliveryStatus,
    NotificationDeliveryRecord,
    NotificationProvider,
    OperatingMode,
)
from app.providers.email import FakeEmailProvider
from app.services.briefings import BriefingService
from app.services.email_delivery import EmailDeliveryService, mask_email
from app.services.news import NewsSyncService
from app.services.operations import BudgetService, UsageService
from app.services.radar_cycle import RadarCycleService
from app.services.retention import RetentionService

NOW = datetime(2026, 7, 26, 12, tzinfo=UTC)


def email_settings(**values: str) -> Settings:
    environment = {
        "DATABASE_URL": "sqlite+pysqlite://",
        "EMAIL_ENABLED": "true",
        "EMAIL_PROVIDER": "SMTP",
        "EMAIL_FROM": "sender@example.invalid",
        "EMAIL_TO": "recipient@example.invalid",
        "SMTP_HOST": "smtp.example.invalid",
        "SMTP_USERNAME": "fixture-user",
        "SMTP_PASSWORD": "fixture-password",
        "EMAIL_MAX_RETRIES": "3",
    }
    environment.update(values)
    return Settings.from_env(environment)


def add_event(
    session,
    *,
    verification: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION,
    lifecycle: LifecycleStatus = LifecycleStatus.UPDATED,
    material_change: bool = True,
    changed_value: str = "new fact",
    symbol: str = "005930",
    last_seen_at: datetime = NOW,
) -> InformationEventRecord:
    instrument = InstrumentRecord(
        canonical_symbol=symbol,
        display_name=f"Fixture {symbol}",
        market="KRX",
        country="KR",
        currency=Currency.KRW,
        asset_type=AssetType.EQUITY,
        verification_status=InstrumentVerificationStatus.VERIFIED,
        verified_at=NOW,
    )
    session.add(instrument)
    session.flush()
    record = InformationEventRecord(
        event_key=f"event-{uuid4()}",
        instrument_id=instrument.id,
        event_type="NEWS",
        normalized_claim=f"{symbol} material event",
        claim_fingerprint=str(uuid4()).replace("-", ""),
        first_seen_at=last_seen_at,
        last_seen_at=last_seen_at,
        latest_material_change_at=last_seen_at if material_change else None,
        lifecycle_status=lifecycle,
        verification_status=verification,
        source_count=1,
        official_source_count=int(verification is VerificationStatus.OFFICIAL_CONFIRMED),
        changed_facts=([{"field": "claim", "value": changed_value}] if changed_value else []),
        current_summary=f"{symbol} event",
        material_change=material_change,
    )
    session.add(record)
    session.flush()
    return record


def generate(session, event: InformationEventRecord):
    return BriefingService(session).generate(
        period_start=event.last_seen_at - timedelta(hours=1),
        period_end=event.last_seen_at + timedelta(hours=1),
        now=event.last_seen_at + timedelta(hours=1),
    )


def test_material_change_creates_compact_ready_briefing(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        event = add_event(session)
        result = generate(session, event)
        assert result.briefing.status is BriefingStatus.READY
        assert result.briefing.material_change_count == 1
        assert result.items[0].changed_facts == event.changed_facts
        assert "new fact" in result.items[0].short_summary


def test_no_material_change_is_skipped(api_database: Database) -> None:
    with api_database.session_scope() as session:
        event = add_event(
            session,
            lifecycle=LifecycleStatus.ACTIVE,
            material_change=False,
            changed_value="",
        )
        result = generate(session, event)
        assert result.briefing.status is BriefingStatus.SKIPPED_NO_CHANGE
        assert result.items == ()


@pytest.mark.parametrize(
    ("verification", "lifecycle", "expected_type", "priority"),
    [
        (
            VerificationStatus.OFFICIAL_CONFIRMED,
            LifecycleStatus.ACTIVE,
            BriefingType.CHANGE_BRIEFING,
            80,
        ),
        (
            VerificationStatus.CORRECTED,
            LifecycleStatus.CORRECTED,
            BriefingType.CORRECTION_NOTICE,
            100,
        ),
        (
            VerificationStatus.OFFICIALLY_DENIED,
            LifecycleStatus.DENIED,
            BriefingType.CORRECTION_NOTICE,
            100,
        ),
    ],
)
def test_official_correction_and_denial_are_prioritized(
    api_database: Database,
    verification: VerificationStatus,
    lifecycle: LifecycleStatus,
    expected_type: BriefingType,
    priority: int,
) -> None:
    with api_database.session_scope() as session:
        event = add_event(
            session,
            verification=verification,
            lifecycle=lifecycle,
            material_change=False,
        )
        result = generate(session, event)
        assert result.briefing.briefing_type is expected_type
        assert result.items[0].priority == priority


def test_same_state_idempotency_returns_existing_briefing(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        event = add_event(session)
        first = generate(session, event)
        second = generate(session, event)
        assert second.briefing.id == first.briefing.id
        assert session.scalar(select(func.count()).select_from(BriefingItemRecord)) == 1


def test_changed_state_creates_only_new_changed_fact(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        event = add_event(session, changed_value="amount 100")
        first = generate(session, event)
        event.changed_facts = [{"field": "amount", "value": "amount 200"}]
        event.latest_material_change_at = NOW + timedelta(hours=2)
        event.last_seen_at = NOW + timedelta(hours=2)
        second = BriefingService(session).generate(
            period_start=NOW,
            period_end=NOW + timedelta(hours=3),
            now=NOW + timedelta(hours=3),
        )
        assert second.briefing.id != first.briefing.id
        assert second.items[0].changed_facts == event.changed_facts
        assert "amount 100" not in second.items[0].short_summary


def test_email_configuration_validation_and_disabled_state() -> None:
    disabled = Settings.from_env({})
    assert disabled.email_configured is False
    assert disabled.email_provider == "DISABLED"
    assert email_settings().email_configured is True
    assert (
        email_settings(
            EMAIL_PROVIDER="RESEND",
            RESEND_API_KEY="fixture-key",
            SMTP_HOST="",
            SMTP_USERNAME="",
            SMTP_PASSWORD="",
        ).email_configured
        is True
    )


def test_fake_email_send_masks_recipient_and_blocks_duplicate(
    api_database: Database,
) -> None:
    fake = FakeEmailProvider()
    with api_database.session_scope() as session:
        briefing = generate(session, add_event(session)).briefing
        service = EmailDeliveryService(
            session, email_settings(), provider=fake, sleep=lambda _: None
        )
        first = service.send(briefing, now=NOW, confirm=True)
        second = service.send(briefing, now=NOW, confirm=True)
        assert first.status is DeliveryStatus.SENT
        assert second.duplicate is True
        assert fake.attempts == 1
        assert mask_email("recipient@example.invalid") == "re***@example.invalid"
        assert "사실일 확률이 아니라" in fake.messages[0]["content"]
        assert "자동 주문이 아닙니다" in fake.messages[0]["content"]


def test_email_failure_respects_retry_cap_and_never_marks_sent(
    api_database: Database,
) -> None:
    fake = FakeEmailProvider(failures_before_success=99)
    settings = email_settings(EMAIL_MAX_RETRIES="2")
    with api_database.session_scope() as session:
        briefing = generate(session, add_event(session)).briefing
        result = EmailDeliveryService(
            session, settings, provider=fake, sleep=lambda _: None
        ).send(briefing, now=NOW, confirm=True)
        assert result.status is DeliveryStatus.FAILED
        assert fake.attempts == 2
        assert briefing.status is BriefingStatus.FAILED


def test_unconfigured_email_does_not_mark_ready_briefing_sent(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        briefing = generate(session, add_event(session)).briefing
        result = EmailDeliveryService(
            session, Settings.from_env({}), sleep=lambda _: None
        ).send(briefing, now=NOW, confirm=True)
        assert result.status is DeliveryStatus.NOT_CONFIGURED
        assert briefing.status is BriefingStatus.READY


@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        (10, OperatingMode.NORMAL),
        (70, OperatingMode.WARNING),
        (80, OperatingMode.SAVING),
        (90, OperatingMode.MINIMAL),
        (98, OperatingMode.PAUSED),
    ],
)
def test_budget_modes(percent: int, expected: OperatingMode) -> None:
    settings = Settings.from_env({"MONTHLY_EMAIL_BUDGET_COUNT": "100"})
    assert (
        BudgetService(settings).mode(
            compute_minutes=0,
            email_count=percent,
            database_bytes=None,
        )
        is expected
    )


def test_budget_unconfigured_and_saving_scope_preserve_quality() -> None:
    service = BudgetService(Settings.from_env({}))
    assert service.configured is False
    scope = service.scope(OperatingMode.MINIMAL)
    assert scope["holdingOfficial"] is True
    assert scope["correctionAndDenial"] is True
    assert scope["deduplication"] is True
    assert scope["watchlistNews"] is False
    assert scope["recommendationsEnabled"] is False


def test_saving_mode_limits_news_targets_to_holdings(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        holding_event = add_event(session, symbol="000101")
        watch_event = add_event(session, symbol="000102")
        session.add_all(
            [
                PortfolioItemRecord(
                    instrument_id=holding_event.instrument_id,
                    asset_type=AssetType.EQUITY,
                    symbol="000101",
                    name="Holding",
                    market="KRX",
                    currency=Currency.KRW,
                    holding_status=HoldingStatus.HOLDING,
                    quantity=Decimal("1"),
                    average_price=Decimal("1"),
                    investment_horizon=InvestmentHorizon.UNSET,
                    strategy="",
                ),
                PortfolioItemRecord(
                    instrument_id=watch_event.instrument_id,
                    asset_type=AssetType.EQUITY,
                    symbol="000102",
                    name="Watch",
                    market="KRX",
                    currency=Currency.KRW,
                    holding_status=HoldingStatus.WATCHLIST,
                    quantity=Decimal("0"),
                    investment_horizon=InvestmentHorizon.UNSET,
                    strategy="",
                ),
            ]
        )
        session.flush()
        candidates = NewsSyncService(session, Settings.from_env({}))._eligible_instruments(
            None, OperatingMode.SAVING
        )
        assert [instrument.canonical_symbol for instrument, _ in candidates] == ["000101"]


def test_usage_calculates_duration_delay_success_and_app_email_count(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        briefing = generate(session, add_event(session)).briefing
        session.add(
            NotificationDeliveryRecord(
                briefing_id=briefing.id,
                provider=NotificationProvider.FAKE,
                recipient_hash="fixture",
                status=DeliveryStatus.SENT,
                attempted_at=NOW,
                delivered_at=NOW,
                retry_count=0,
                idempotency_key="fixture-delivery",
            )
        )
        session.add_all(
            [
                CollectionRunRecord(
                    provider=ProviderName.SYSTEM_BASELINE,
                    run_type=CollectionRunType.NEWS_SYNC,
                    started_at=NOW - timedelta(seconds=30),
                    finished_at=NOW,
                    status=CollectionStatus.SUCCEEDED,
                    scheduled_for=NOW - timedelta(minutes=1),
                    duration_milliseconds=30_000,
                    delay_milliseconds=30_000,
                ),
                CollectionRunRecord(
                    provider=ProviderName.SYSTEM_BASELINE,
                    run_type=CollectionRunType.DISCLOSURE_SYNC,
                    started_at=NOW - timedelta(seconds=30),
                    finished_at=NOW,
                    status=CollectionStatus.FAILED,
                    duration_milliseconds=30_000,
                ),
            ]
        )
        session.flush()
        snapshot = UsageService(
            session, Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
        ).collect(now=NOW)
        assert snapshot.locally_estimated_compute_minutes == 1
        assert snapshot.collection_success_rate == 50
        assert snapshot.average_duration_seconds == 30
        assert snapshot.delayed_run_count == 1
        assert snapshot.email_sent_count == 1
        assert snapshot.action_minutes_availability is Availability.NOT_CONFIGURED
        assert snapshot.provider_reported_action_minutes is None


def test_usage_measures_real_sqlite_file(tmp_path: Path) -> None:
    path = tmp_path / "usage.sqlite3"
    url = f"sqlite+pysqlite:///{path.as_posix()}"
    database = Database(url)
    database.create_schema()
    with database.session_scope() as session:
        snapshot = UsageService(session, Settings.from_env({"DATABASE_URL": url})).collect(
            now=NOW
        )
        assert snapshot.database_bytes_availability is Availability.AVAILABLE
        assert snapshot.database_bytes is not None
        assert snapshot.database_bytes > 0


def test_radar_cycle_dry_run_has_no_email_or_run_mutation(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        add_event(session)
        result = RadarCycleService(session, Settings.from_env({})).run(now=NOW, dry_run=True)
        assert result["status"] == "DRY_RUN"
        assert result["deliveryStatus"] == "SKIPPED"
        assert result["quoteSyncCallCount"] == 0
        assert session.scalar(select(func.count()).select_from(CollectionRunRecord)) == 0
        assert session.scalar(select(func.count()).select_from(NotificationDeliveryRecord)) == 0


def test_briefing_and_preference_api_masks_email(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        briefing_id = generate(session, add_event(session)).briefing.id
    preference = api_client.put(
        "/api/v1/notification-preferences",
        json={
            "enabled": True,
            "recipientEmail": "private@example.com",
            "hourlyChangeBriefingEnabled": True,
        },
    )
    assert preference.status_code == 200
    assert preference.json()["recipientEmailMasked"] == "pr***@example.com"
    assert "recipientEmail" not in preference.json()
    listing = api_client.get("/api/v1/briefings?limit=1&offset=0")
    detail = api_client.get(f"/api/v1/briefings/{briefing_id}")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["items"][0]["informationEventId"]
    assert "rawHtml" not in str(detail.json())


def test_invalid_preference_email_is_rejected(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/notification-preferences",
        json={"enabled": True, "recipientEmail": "not-an-email"},
    )
    assert response.status_code == 422


def test_preference_update_preserves_masked_recipient(
    api_client: TestClient,
) -> None:
    first = api_client.put(
        "/api/v1/notification-preferences",
        json={"enabled": True, "recipientEmail": "private@example.com"},
    )
    second = api_client.put(
        "/api/v1/notification-preferences",
        json={"enabled": True, "dailyDigestEnabled": True},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["recipientEmailMasked"] == "pr***@example.com"
    assert second.json()["dailyDigestEnabled"] is True


def test_briefing_missing_id_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/briefings/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BRIEFING_NOT_FOUND"


def test_operations_api_and_system_safety(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        UsageService(session, Settings.from_env({})).collect(now=NOW)
    assert api_client.get("/api/v1/operations/metrics").status_code == 200
    usage = api_client.get("/api/v1/operations/usage").json()
    status = api_client.get("/api/v1/operations/status").json()
    system = api_client.get("/api/v1/system/info").json()
    assert usage["total"] == 1
    assert usage["items"][0]["actionMinutesAvailability"] == "NOT_CONFIGURED"
    assert status["githubActionsUsageConnected"] is False
    assert status["automaticTradingEnabled"] is False
    assert system["automaticTradingEnabled"] is False
    assert system["aiAutomationEnabled"] is False


def test_radar_cycle_records_partial_provider_failure(
    api_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "OFFICIAL_DISCLOSURE_SYNC_ENABLED": "true",
            "OPENDART_SYNC_ENABLED": "true",
            "OPENDART_API_KEY": "1234567890123456789012345678901234567890",
            "NEWS_SYNC_ENABLED": "true",
            "NEWS_FEED_SYNC_ENABLED": "true",
        }
    )

    def official_success(*args: object, **kwargs: object) -> dict[str, int | str]:
        return {"status": "SUCCEEDED", "fetched": 1, "created": 1}

    def news_failure(*args: object, **kwargs: object) -> dict[str, int | str]:
        return {
            "status": "FAILED",
            "fetched": 0,
            "created": 0,
            "errors": 1,
        }

    monkeypatch.setattr(
        "app.services.radar_cycle.OfficialDisclosureSyncService.sync",
        official_success,
    )
    monkeypatch.setattr(
        "app.services.radar_cycle.NewsSyncService.sync",
        news_failure,
    )
    with api_database.session_scope() as session:
        output = RadarCycleService(session, settings).run(now=NOW, dry_run=False)
        run = session.scalar(
            select(CollectionRunRecord).where(
                CollectionRunRecord.run_type == CollectionRunType.RADAR_CYCLE
            )
        )
        assert output["status"] == "PARTIAL_SUCCESS"
        assert run is not None
        assert run.status is CollectionStatus.FAILED
        assert run.partial_success is True
        assert run.error_count == 1


def test_paused_budget_mode_skips_automatic_news(
    api_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "NEWS_SYNC_ENABLED": "true",
            "NEWS_FEED_SYNC_ENABLED": "true",
            "MONTHLY_COMPUTE_BUDGET_MINUTES": "1",
        }
    )

    def unexpected_news(*args: object, **kwargs: object) -> dict[str, int | str]:
        raise AssertionError("PAUSED mode must not call the news provider")

    monkeypatch.setattr("app.services.radar_cycle.NewsSyncService.sync", unexpected_news)
    with api_database.session_scope() as session:
        session.add(
            CollectionRunRecord(
                provider=ProviderName.SYSTEM_BASELINE,
                run_type=CollectionRunType.NEWS_SYNC,
                started_at=NOW - timedelta(minutes=2),
                finished_at=NOW - timedelta(minutes=1),
                duration_milliseconds=60_000,
                status=CollectionStatus.SUCCEEDED,
            )
        )
        session.flush()
        output = RadarCycleService(session, settings).run(now=NOW, dry_run=False)
        assert output["operatingMode"] == "PAUSED"
        assert output["syncResults"]["news"]["status"] == "SKIPPED_BUDGET_MODE"


def test_old_nonimportant_briefing_retention_dry_run_and_cleanup(
    api_database: Database,
) -> None:
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "RETENTION_CLEANUP_ENABLED": "true",
            "IMPORTANT_BRIEFING_RETENTION_DAYS": "90",
        }
    )
    with api_database.session_scope() as session:
        briefing = generate(
            session,
            add_event(session, last_seen_at=NOW - timedelta(days=100)),
        ).briefing
        briefing.updated_at = NOW - timedelta(days=100)
        session.flush()
        preview = RetentionService(session, settings).run(now=NOW, dry_run=True)
        assert preview.briefing_records == 1
        assert session.get(BriefingRecord, briefing.id) is not None
        RetentionService(session, settings).run(now=NOW, dry_run=False, confirm=True)
        assert session.get(BriefingRecord, briefing.id) is None


def test_correction_briefing_is_retention_protected(
    api_database: Database,
) -> None:
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "RETENTION_CLEANUP_ENABLED": "true",
            "IMPORTANT_BRIEFING_RETENTION_DAYS": "90",
        }
    )
    with api_database.session_scope() as session:
        briefing = generate(
            session,
            add_event(
                session,
                verification=VerificationStatus.CORRECTED,
                lifecycle=LifecycleStatus.CORRECTED,
                last_seen_at=NOW - timedelta(days=100),
            ),
        ).briefing
        briefing.updated_at = NOW - timedelta(days=100)
        session.flush()
        RetentionService(session, settings).run(now=NOW, dry_run=False, confirm=True)
        assert session.get(BriefingRecord, briefing.id) is not None


def test_manual_briefing_generation_preview_confirm_and_duplicate_guard(
    api_database: Database,
    api_client: TestClient,
) -> None:
    with api_database.session_scope() as session:
        add_event(
            session,
            verification=VerificationStatus.OFFICIAL_CONFIRMED,
            changed_value="공식 발표 내용 확인",
        )
        before_briefings = int(
            session.scalar(select(func.count()).select_from(BriefingRecord)) or 0
        )
        before_items = int(
            session.scalar(select(func.count()).select_from(BriefingItemRecord)) or 0
        )

    payload = {
        "periodStart": "2026-07-25T00:00:00Z",
        "periodEnd": "2026-07-27T23:59:59Z",
        "minimumPriority": 0,
        "includedItemsConfirmed": True,
        "confirm": False,
    }
    preview = api_client.post("/api/v1/briefings/generate", json=payload)
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["confirmed"] is False
    assert preview_body["persisted"] is False
    assert preview_body["emailDeliveryCreated"] is False
    assert preview_body["wouldCreate"] is True
    assert preview_body["canConfirm"] is True
    assert preview_body["briefing"]["itemCount"] == 1
    assert preview_body["briefing"]["items"][0]["id"]
    assert preview_body["briefing"]["items"][0]["verificationStatus"] == ("OFFICIAL_CONFIRMED")

    with api_database.session_scope() as session:
        assert (
            int(session.scalar(select(func.count()).select_from(BriefingRecord)) or 0)
            == before_briefings
        )
        assert (
            int(session.scalar(select(func.count()).select_from(BriefingItemRecord)) or 0)
            == before_items
        )

    missing_confirmation = api_client.post(
        "/api/v1/briefings/generate",
        json={
            **payload,
            "includedItemsConfirmed": False,
            "confirm": True,
        },
    )
    assert missing_confirmation.status_code == 422
    assert (
        missing_confirmation.json()["error"]["code"] == "BRIEFING_GENERATION_VALIDATION_ERROR"
    )

    confirmed = api_client.post(
        "/api/v1/briefings/generate",
        json={**payload, "confirm": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    confirmed_body = confirmed.json()
    assert confirmed_body["confirmed"] is True
    assert confirmed_body["persisted"] is True
    assert confirmed_body["emailDeliveryCreated"] is False
    briefing_id = confirmed_body["briefing"]["id"]

    with api_database.session_scope() as session:
        assert session.get(BriefingRecord, briefing_id) is not None
        assert (
            int(session.scalar(select(func.count()).select_from(BriefingItemRecord)) or 0)
            == before_items + 1
        )

    duplicate_preview = api_client.post(
        "/api/v1/briefings/generate",
        json=payload,
    )
    assert duplicate_preview.status_code == 200
    duplicate_body = duplicate_preview.json()
    assert duplicate_body["wouldCreate"] is False
    assert duplicate_body["canConfirm"] is False
    assert duplicate_body["existingBriefingId"] == briefing_id

    duplicate_confirm = api_client.post(
        "/api/v1/briefings/generate",
        json={**payload, "confirm": True},
    )
    assert duplicate_confirm.status_code == 409
    assert duplicate_confirm.json()["error"]["code"] == "BRIEFING_GENERATION_VALIDATION_ERROR"

    openapi = api_client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/v1/briefings/generate" in openapi.json()["paths"]
