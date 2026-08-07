from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import Settings
from app.database import Database
from app.models.analysis import PortfolioImpactRecord
from app.models.database import PortfolioItemRecord
from app.models.disclosures import ProviderName
from app.models.market_data import ProviderSyncStateRecord
from app.models.operations import (
    BriefingType,
    NotificationPreferenceRecord,
)
from app.providers.opendart import OpenDartProvider
from app.providers.sec import SecEdgarProvider
from app.repositories.instruments import InstrumentRepository
from app.services.analysis import AnalysisService
from app.services.briefings import BriefingService
from app.services.disclosure_sync import OfficialDisclosureSyncService
from app.services.email_delivery import EmailDeliveryService, mask_email
from app.services.instruments import InstrumentService
from app.services.market_briefings import MarketBriefingPreviewService
from app.services.market_calendar import (
    MarketScheduleService,
    default_market_calendar,
    market_briefing_idempotency_key,
)
from app.services.market_sessions import MarketSessionCacheService
from app.services.news import NewsSyncService
from app.services.operations import UsageService, collection_success_formula
from app.services.public_quotes import PublicQuoteService
from app.services.radar_cycle import RadarCycleService
from app.services.retention import RetentionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="investment-ai-radar")
    commands = parser.add_subparsers(dest="command", required=True)
    instruments = commands.add_parser("sync-instruments")
    instruments.add_argument("--provider", choices=["OPENDART", "SEC_EDGAR"], required=True)
    instruments.add_argument("--dry-run", action="store_true")
    instruments.add_argument("--confirm", action="store_true")
    instruments.add_argument("--limit", type=int, default=3)
    instruments.add_argument("--portfolio-id")
    instruments.add_argument("--symbol")
    instruments.add_argument("--since")
    instruments.add_argument("--verbose", action="store_true")
    for name in (
        "sync-opendart-company-codes",
        "sync-sec-company-tickers",
        "sync-instrument-mappings",
    ):
        command = commands.add_parser(name)
        if name == "sync-instrument-mappings":
            command.add_argument(
                "--provider",
                choices=["OPENDART", "SEC_EDGAR"],
                required=True,
            )
        command.add_argument("--portfolio-id")
        command.add_argument("--symbol")
        command.add_argument("--since")
        command.add_argument("--limit", type=int, default=3)
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--confirm", action="store_true")
        command.add_argument("--verbose", action="store_true")
    disclosures = commands.add_parser("sync-disclosures")
    disclosures.add_argument("--provider", choices=["OPENDART", "SEC_EDGAR"], required=True)
    disclosures.add_argument("--portfolio-only", action="store_true")
    disclosures.add_argument("--since")
    disclosures.add_argument("--instrument-id")
    disclosures.add_argument("--portfolio-id")
    disclosures.add_argument("--symbol")
    disclosures.add_argument("--dry-run", action="store_true")
    disclosures.add_argument("--confirm", action="store_true")
    disclosures.add_argument("--limit", type=int, default=30)
    disclosures.add_argument("--verbose", action="store_true")
    for name in ("sync-opendart-disclosures", "sync-sec-disclosures"):
        command = commands.add_parser(name)
        command.add_argument("--portfolio-id")
        command.add_argument("--symbol")
        command.add_argument("--since")
        command.add_argument("--limit", type=int, default=30)
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--confirm", action="store_true")
        command.add_argument("--verbose", action="store_true")
        command.set_defaults(instrument_id=None, portfolio_only=True)
    for name in ("process-disclosure-events", "refresh-decision-reviews"):
        command = commands.add_parser(name)
        command.add_argument("--provider", choices=["OPENDART", "SEC_EDGAR"])
        command.add_argument("--portfolio-id")
        command.add_argument("--symbol")
        command.add_argument("--since")
        command.add_argument("--limit", type=int, default=100)
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--confirm", action="store_true")
        command.add_argument("--verbose", action="store_true")
    official_smoke = commands.add_parser("official-disclosure-smoke")
    official_smoke.add_argument(
        "--provider",
        choices=["OPENDART", "SEC_EDGAR"],
        required=True,
    )
    official_smoke.add_argument("--portfolio-id")
    official_smoke.add_argument("--symbol")
    official_smoke.add_argument("--since")
    official_smoke.add_argument("--limit", type=int, default=10)
    official_smoke.add_argument("--dry-run", action="store_true")
    official_smoke.add_argument("--confirm", action="store_true")
    official_smoke.add_argument("--verbose", action="store_true")
    retention = commands.add_parser("retention")
    retention.add_argument("--dry-run", action="store_true")
    retention.add_argument("--confirm", action="store_true")
    news = commands.add_parser("sync-news")
    news.add_argument(
        "--provider",
        choices=["RSS", "ATOM", "OFFICIAL_IR_FEED"],
        default="RSS",
    )
    news.add_argument("--source-id")
    news.add_argument("--instrument-id")
    news.add_argument("--portfolio-only", action="store_true")
    news.add_argument("--since")
    news.add_argument("--limit", type=int, default=50)
    news.add_argument("--dry-run", action="store_true")
    news.add_argument("--verbose", action="store_true")
    preview = commands.add_parser("briefing-preview")
    preview.add_argument("--hours", type=int, default=24)
    preview.add_argument("--minimum-priority", type=int, default=0)
    send = commands.add_parser("send-briefing")
    send.add_argument("--briefing-id")
    send.add_argument("--confirm", action="store_true")
    send.add_argument("--dry-run", action="store_true")
    cycle = commands.add_parser("radar-cycle")
    cycle.add_argument("--dry-run", action="store_true")
    cycle.add_argument("--confirm-send", action="store_true")
    usage = commands.add_parser("usage-snapshot")
    usage.add_argument("--dry-run", action="store_true")
    quotes = commands.add_parser("sync-public-quotes")
    quotes.add_argument("--provider", choices=["UPBIT", "BINANCE"])
    quotes.add_argument("--dry-run", action="store_true")
    quotes.add_argument("--confirm", action="store_true")
    calendar = commands.add_parser("sync-market-calendar")
    calendar.add_argument("--since")
    calendar.add_argument("--limit", type=int, default=45)
    calendar.add_argument("--dry-run", action="store_true")
    calendar.add_argument("--confirm", action="store_true")
    commands.add_parser("provider-status")
    smoke = commands.add_parser("provider-smoke")
    smoke.add_argument("--provider", choices=["UPBIT", "BINANCE"])
    smoke.add_argument("--dry-run", action="store_true")
    smoke.add_argument("--confirm", action="store_true")
    for name in ("market-briefing-preview", "market-briefings"):
        market = commands.add_parser(name)
        market.add_argument("--market", choices=["KRX", "NASDAQ"], required=True)
        market.add_argument(
            "--briefing-type",
            choices=[
                "KRX_PRE_OPEN",
                "KRX_POST_CLOSE",
                "NASDAQ_PRE_OPEN",
                "NASDAQ_POST_CLOSE",
            ],
            required=True,
        )
        market.add_argument("--session-date")
        market.add_argument("--dry-run", action="store_true")
        market.add_argument("--verbose", action="store_true")
        market.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    instrument_aliases = {
        "sync-opendart-company-codes": "OPENDART",
        "sync-sec-company-tickers": "SEC_EDGAR",
    }
    disclosure_aliases = {
        "sync-opendart-disclosures": "OPENDART",
        "sync-sec-disclosures": "SEC_EDGAR",
    }
    if args.command in instrument_aliases:
        args.provider = instrument_aliases[args.command]
        args.command = "sync-instruments"
    elif args.command == "sync-instrument-mappings":
        args.command = "sync-instruments"
    elif args.command in disclosure_aliases:
        args.provider = disclosure_aliases[args.command]
        args.command = "sync-disclosures"
    settings = Settings.from_env()
    if args.command == "official-disclosure-smoke":
        if not args.dry_run and not args.confirm:
            print(json.dumps({"status": "CONFIRM_REQUIRED"}, sort_keys=True))
            return 2
        provider = (
            OpenDartProvider(settings)
            if args.provider == "OPENDART"
            else SecEdgarProvider(settings)
        )
        result = (
            provider.fetch_company_codes()
            if args.provider == "OPENDART"
            else provider.fetch_company_tickers()
        )
        output = {
            "status": result.status.value,
            "provider": args.provider,
            "requestCount": result.request_count,
            "companyCount": min(len(result.companies), max(args.limit, 0)),
            "errorCode": result.error_code,
            "secretsExposed": False,
        }
        if result.diagnostics is not None:
            output.update(
                {
                    "httpStatus": result.diagnostics.http_status,
                    "contentType": result.diagnostics.content_type,
                    "contentLength": result.diagnostics.content_length,
                    "contentDispositionPresent": (
                        result.diagnostics.content_disposition_present
                    ),
                    "payloadKind": result.diagnostics.payload_kind,
                    "zipSignatureValid": (result.diagnostics.zip_signature_valid),
                    "redirectCount": result.diagnostics.redirect_count,
                    "officialStatusCode": (result.diagnostics.official_status_code),
                    "officialMessage": result.diagnostics.official_message,
                }
            )
        print(json.dumps(output, sort_keys=True))
        return (
            1
            if result.status.value in {"FAILED", "ERROR", "NETWORK_UNAVAILABLE", "RATE_LIMITED"}
            else 0
        )
    if args.command in {
        "process-disclosure-events",
        "refresh-decision-reviews",
    }:
        if not args.dry_run and not args.confirm:
            print(json.dumps({"status": "CONFIRM_REQUIRED"}, sort_keys=True))
            return 2
        if not settings.database_configured:
            print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
            return 0
        database = Database.from_settings(settings)
        with database.session_scope() as session:
            service = AnalysisService(session)
            if args.command == "process-disclosure-events":
                reprocessed = OfficialDisclosureSyncService(
                    session, settings
                ).reprocess_existing(dry_run=args.dry_run)
                created = 0 if args.dry_run else service.sync_direct_impacts()
                output = {
                    "status": "DRY_RUN" if args.dry_run else "SUCCEEDED",
                    "created": created,
                    "providerRequests": 0,
                    "reprocessed": reprocessed,
                }
            else:
                statement = select(PortfolioItemRecord).where(
                    PortfolioItemRecord.archived_at.is_(None)
                )
                if not args.portfolio_id and not args.symbol:
                    statement = statement.join(
                        PortfolioImpactRecord,
                        PortfolioImpactRecord.portfolio_item_id == PortfolioItemRecord.id,
                    ).distinct()
                if args.portfolio_id:
                    statement = statement.where(PortfolioItemRecord.id == args.portfolio_id)
                if args.symbol:
                    statement = statement.where(
                        PortfolioItemRecord.symbol == args.symbol.strip().upper()
                    )
                items = list(session.scalars(statement.limit(args.limit)))
                changed = 0
                if not args.dry_run:
                    for item in items:
                        before = service.latest_review(item.id)
                        after = service.refresh_review(item.id, manual_reference_price=None)
                        changed += int(before.id is None or str(before.id) != str(after.id))
                output = {
                    "status": "DRY_RUN" if args.dry_run else "SUCCEEDED",
                    "candidateCount": len(items),
                    "changed": changed,
                    "providerRequests": 0,
                }
        print(json.dumps(output, sort_keys=True))
        return 0
    if args.command in {"sync-public-quotes", "provider-smoke"}:
        if not settings.database_configured:
            print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
            return 0
        database = Database.from_settings(settings)
        with database.session_scope() as session:
            output = PublicQuoteService(session, settings).sync(
                provider=args.provider,
                dry_run=args.dry_run,
                confirm=args.confirm,
            )
        print(json.dumps(output, sort_keys=True))
        return 0
    if args.command == "sync-market-calendar":
        if not settings.database_configured:
            print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
            return 0
        if not settings.market_calendar_enabled:
            print(json.dumps({"status": "NOT_CONFIGURED", "provider": "MARKET_CALENDAR"}))
            return 0
        database = Database.from_settings(settings)
        start = date.fromisoformat(args.since) if args.since else datetime.now(UTC).date()
        with database.session_scope() as session:
            output = MarketSessionCacheService(
                session,
                MarketScheduleService(
                    default_market_calendar(enabled=settings.market_calendar_enabled)
                ),
            ).sync(
                start=start,
                days=args.limit,
                dry_run=args.dry_run,
                confirm=args.confirm,
            )
        print(json.dumps(output, sort_keys=True))
        return 0
    if args.command == "provider-status":
        states: dict[str, dict[str, object]] = {}
        if settings.database_configured:
            database = Database.from_settings(settings)
            with database.session_scope() as session:
                states = {
                    state.provider: {
                        "status": ("READY" if state.status == "SUCCEEDED" else state.status),
                        "lastSuccessAt": (
                            state.last_success_at.isoformat() if state.last_success_at else None
                        ),
                        "lastErrorCode": state.last_error_code,
                        "requestCount": int(state.request_count or 0),
                    }
                    for state in session.scalars(
                        select(ProviderSyncStateRecord).where(
                            ProviderSyncStateRecord.capability == "OFFICIAL_DISCLOSURE"
                        )
                    )
                }

        def official_status(
            provider: str, configured: bool, secret_set: bool
        ) -> dict[str, object]:
            state = states.get(provider)
            return {
                "status": (
                    state["status"]
                    if configured and state
                    else "CONFIGURED"
                    if configured
                    else "NOT_CONFIGURED"
                ),
                "secret": "SET" if secret_set else "NOT_SET",
                "lastSuccessAt": state["lastSuccessAt"] if state else None,
                "lastErrorCode": state["lastErrorCode"] if state else None,
                "requestCount": state["requestCount"] if state else 0,
            }

        output = {
            "OPENDART": official_status(
                "OPENDART",
                settings.open_dart_configured,
                bool(settings.opendart_api_key),
            ),
            "SEC_EDGAR": official_status(
                "SEC_EDGAR",
                settings.sec_configured,
                bool(settings.sec_user_agent),
            ),
            "OFFICIAL_DISCLOSURE_SYNC": (
                "ENABLED" if settings.official_disclosure_sync_enabled else "DISABLED"
            ),
            "UPBIT": "READY" if settings.upbit_public_market_enabled else "NOT_CONFIGURED",
            "BINANCE": (
                "READY" if settings.binance_public_market_enabled else "NOT_CONFIGURED"
            ),
            "MARKET_CALENDAR": (
                "READY"
                if settings.market_calendar_enabled and default_market_calendar().configured
                else "NOT_CONFIGURED"
            ),
        }
        print(json.dumps(output, sort_keys=True))
        return 0
    if args.command == "sync-instruments":
        if not args.dry_run and not args.confirm:
            print(json.dumps({"status": "CONFIRM_REQUIRED"}, sort_keys=True))
            return 2
        provider = (
            OpenDartProvider(settings)
            if args.provider == "OPENDART"
            else SecEdgarProvider(settings)
        )
        result = (
            provider.fetch_company_codes()
            if args.provider == "OPENDART"
            else provider.fetch_company_tickers()
        )
        if result.status.value == "NOT_CONFIGURED":
            print(
                json.dumps(
                    {"status": "NOT_CONFIGURED", "provider": args.provider},
                    sort_keys=True,
                )
            )
            return 0
        if not settings.database_configured:
            print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
            return 0
        database = Database.from_settings(settings)
        with database.session_scope() as session:
            output = InstrumentService(InstrumentRepository(session)).sync_companies(
                result,
                dry_run=args.dry_run,
                limit=args.limit,
                portfolio_id=args.portfolio_id,
                symbol=args.symbol,
            )
        print(json.dumps(output, sort_keys=True))
        return (
            1
            if output["status"] in {"FAILED", "ERROR", "NETWORK_UNAVAILABLE", "RATE_LIMITED"}
            else 0
        )
    if args.command == "sync-disclosures":
        if not args.dry_run and not args.confirm:
            print(json.dumps({"status": "CONFIRM_REQUIRED"}, sort_keys=True))
            return 2
        provider_configured = settings.official_disclosure_sync_enabled and (
            settings.open_dart_configured
            if args.provider == "OPENDART"
            else settings.sec_configured
        )
        if not provider_configured:
            print(
                json.dumps(
                    {"status": "NOT_CONFIGURED", "provider": args.provider},
                    sort_keys=True,
                )
            )
            return 0
        if not settings.database_configured:
            print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
            return 0
        database = Database.from_settings(settings)
        provider = ProviderName(args.provider)
        since = datetime.fromisoformat(args.since).astimezone(UTC) if args.since else None
        with database.session_scope() as session:
            output = OfficialDisclosureSyncService(session, settings).sync(
                provider,
                since=since,
                instrument_id=args.instrument_id,
                portfolio_id=args.portfolio_id,
                symbol=args.symbol,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        print(json.dumps(output, sort_keys=True))
        return (
            1
            if output["status"] in {"FAILED", "ERROR", "NETWORK_UNAVAILABLE", "RATE_LIMITED"}
            else 0
        )
    if args.command == "sync-news":
        if not settings.news_sync_enabled or not settings.news_feed_sync_enabled:
            print(
                json.dumps(
                    {"status": "NOT_CONFIGURED", "provider": args.provider},
                    sort_keys=True,
                )
            )
            return 0
        if not settings.database_configured:
            print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
            return 0
        database = Database.from_settings(settings)
        since = datetime.fromisoformat(args.since).astimezone(UTC) if args.since else None
        with database.session_scope() as session:
            output = NewsSyncService(session, settings).sync(
                source_id=args.source_id,
                instrument_id=args.instrument_id,
                since=since,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        print(json.dumps(output, sort_keys=True))
        return 0
    if args.command in {
        "briefing-preview",
        "send-briefing",
        "radar-cycle",
        "usage-snapshot",
        "market-briefing-preview",
        "market-briefings",
    }:
        if not settings.database_configured:
            print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
            return 0
        database = Database.from_settings(settings)
        now = datetime.now(UTC)
        with database.session_scope() as session:
            if args.command in {"market-briefing-preview", "market-briefings"}:
                briefing_type = BriefingType(args.briefing_type)
                expected_market = briefing_type.value.split("_", 1)[0]
                if args.market != expected_market:
                    print(
                        json.dumps(
                            {
                                "status": "INVALID_ARGUMENT",
                                "reason": "market and briefing type mismatch",
                            },
                            sort_keys=True,
                        )
                    )
                    return 2
                target = (
                    date.fromisoformat(args.session_date) if args.session_date else now.date()
                )
                schedule_service = MarketScheduleService(default_market_calendar())
                preview_result = MarketBriefingPreviewService(
                    session, settings, schedule_service
                ).preview(briefing_type, session_date=target, now=now)
                if args.command == "market-briefing-preview" or args.dry_run:
                    output = preview_result.model_dump(mode="json", by_alias=True)
                elif not args.confirm:
                    output = {
                        "status": "CONFIRM_REQUIRED",
                        "deliveryStatus": "SKIPPED",
                    }
                elif not schedule_service.adapter.configured:
                    output = {
                        "status": "NOT_CONFIGURED",
                        "reason": "MARKET_CALENDAR",
                        "deliveryStatus": "NOT_CONFIGURED",
                    }
                else:
                    preference = session.get(NotificationPreferenceRecord, "default")
                    generation = BriefingService(session).generate(
                        period_start=preview_result.investigation_start,
                        period_end=preview_result.investigation_end,
                        now=now,
                        briefing_type=briefing_type,
                        minimum_priority=(preference.minimum_priority if preference else 0),
                        idempotency_key_override=(
                            market_briefing_idempotency_key(briefing_type, target)
                        ),
                        preserve_briefing_type=True,
                        include_no_change=bool(
                            preference and preference.send_no_material_change_briefing
                        ),
                        provider_complete=not preview_result.data_missing,
                    )
                    output = {
                        "status": generation.briefing.status.value,
                        "briefingType": briefing_type.value,
                        "sessionDate": target.isoformat(),
                        "idempotencyKey": generation.briefing.idempotency_key,
                        "deliveryStatus": (
                            "NOT_CONFIGURED"
                            if not settings.email_configured
                            else "READY_FOR_EXPLICIT_SEND"
                        ),
                    }
            elif args.command == "briefing-preview":
                result = BriefingService(session).generate(
                    period_start=now - timedelta(hours=args.hours),
                    period_end=now,
                    now=now,
                    minimum_priority=args.minimum_priority,
                )
                preference = session.get(NotificationPreferenceRecord, "default")
                output = {
                    "status": result.briefing.status.value,
                    "candidateCount": len(result.items),
                    "excludedDuplicateCount": result.excluded_duplicates,
                    "materialChangeCount": (result.briefing.material_change_count),
                    "title": result.briefing.title,
                    "summary": result.briefing.compact_summary,
                    "recipient": mask_email(preference.recipient_email if preference else None),
                }
            elif args.command == "send-briefing":
                if not settings.email_configured and not args.dry_run:
                    output = {
                        "status": "NOT_CONFIGURED",
                        "provider": settings.email_provider,
                    }
                else:
                    service = BriefingService(session)
                    briefing = (
                        service.get(args.briefing_id)
                        if args.briefing_id
                        else service.generate(
                            period_start=now - timedelta(hours=1),
                            period_end=now,
                            now=now,
                        ).briefing
                    )
                    preference = session.get(NotificationPreferenceRecord, "default")
                    result = EmailDeliveryService(session, settings).send(
                        briefing,
                        recipient=(preference.recipient_email if preference else None),
                        now=now,
                        confirm=args.confirm,
                        dry_run=args.dry_run,
                    )
                    output = {
                        "status": result.status.value,
                        "duplicate": result.duplicate,
                        "recipient": mask_email(
                            preference.recipient_email if preference else settings.email_to
                        ),
                    }
            elif args.command == "radar-cycle":
                output = RadarCycleService(session, settings).run(
                    now=now,
                    dry_run=args.dry_run or not args.confirm_send,
                    confirm_send=args.confirm_send,
                )
            else:
                snapshot = UsageService(session, settings).collect(
                    now=now, persist=not args.dry_run
                )
                output = {
                    "status": "DRY_RUN" if args.dry_run else "SUCCEEDED",
                    "period": snapshot.period,
                    "actionMinutesAvailability": (snapshot.action_minutes_availability.value),
                    "providerReportedActionMinutes": (
                        snapshot.provider_reported_action_minutes
                    ),
                    "locallyEstimatedComputeMinutes": (
                        snapshot.locally_estimated_compute_minutes
                    ),
                    "databaseBytesAvailability": (snapshot.database_bytes_availability.value),
                    "databaseBytes": snapshot.database_bytes,
                    "emailSentCount": snapshot.email_sent_count,
                    "collectionSuccessRate": (snapshot.collection_success_rate),
                    "successRateFormula": collection_success_formula(),
                    "operatingMode": snapshot.operating_mode.value,
                }
        print(json.dumps(output, sort_keys=True))
        return 0
    if not settings.database_configured:
        print(json.dumps({"status": "NOT_CONFIGURED", "reason": "DATABASE_URL"}))
        return 0
    database = Database.from_settings(settings)
    with database.session_scope() as session:
        output = RetentionService(session, settings).run(
            now=datetime.now(UTC),
            dry_run=args.dry_run or not args.confirm,
            confirm=args.confirm,
        )
    print(json.dumps(output.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
