from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api import (
    analysis_router,
    analyst_references_router,
    briefings_router,
    disclosures_router,
    instruments_router,
    market_briefings_router,
    news_router,
    operations_router,
    portfolio_router,
    providers_router,
    risk_profile_router,
)
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.core.logging import configure_logging
from app.database import Database
from app.models.database import RiskProfileRecord, SourceRecord
from app.models.disclosures import (
    CollectionRunRecord,
    CollectionRunType,
    CollectionStatus,
    DisclosureRecord,
    InformationEventRecord,
    InstrumentProviderMappingRecord,
    LifecycleStatus,
    MappingStatus,
    NewsReferenceRecord,
)
from app.models.market_data import ProviderSyncStateRecord, QuoteSnapshotRecord
from app.models.operations import (
    Availability,
    BriefingRecord,
    BriefingType,
    DeliveryStatus,
    NotificationDeliveryRecord,
    NotificationPreferenceRecord,
    OperatingMode,
    UsageSnapshotRecord,
)
from app.schemas.system import HealthResponse, SystemInfoResponse
from app.services.market_calendar import (
    MARKET_BRIEFING_TYPES,
    MarketScheduleService,
    ScheduleStatus,
    default_market_calendar,
)
from app.services.operations import BudgetService
from app.services.risk_recommendation import RiskRecommendationService

VERSION = "0.2.0"
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
) -> FastAPI:
    configure_logging()
    resolved = settings or Settings.from_env()
    resolved_database = database
    if resolved_database is None and resolved.database_configured:
        try:
            resolved_database = Database.from_settings(resolved)
        except (SQLAlchemyError, RuntimeError, ValueError) as exc:
            logger.error(
                "database_initialization_failed",
                extra={"context": {"errorType": type(exc).__name__}},
            )
    application = FastAPI(
        title="Investment AI Radar API",
        version=VERSION,
        description="Private information research API. No trading endpoints.",
    )
    application.state.settings = resolved
    application.state.database = resolved_database
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.include_router(portfolio_router)
    application.include_router(analysis_router)
    application.include_router(analyst_references_router)
    application.include_router(risk_profile_router)
    application.include_router(instruments_router)
    application.include_router(market_briefings_router)
    application.include_router(disclosures_router)
    application.include_router(news_router)
    application.include_router(briefings_router)
    application.include_router(operations_router)
    application.include_router(providers_router)

    @application.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        code = (
            "RISK_PROFILE_VALIDATION_ERROR"
            if request.url.path.startswith("/api/v1/risk-profile")
            else (
                "SALE_VALIDATION_ERROR"
                if "/sales" in request.url.path
                or "/historical-sales" in request.url.path
                or request.url.path.endswith("/historical-sale")
                else "PORTFOLIO_VALIDATION_ERROR"
            )
        )
        issues = [
            {
                "location": [str(part) for part in error["loc"]],
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": code,
                    "message": "요청 값이 올바르지 않습니다.",
                    "details": {"issues": issues},
                }
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
        logger.error(
            "database_operation_failed",
            extra={
                "context": {
                    "path": request.url.path,
                    "errorType": type(exc).__name__,
                }
            },
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "데이터베이스 요청을 처리할 수 없습니다.",
                    "details": {},
                }
            },
        )

    @application.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "internal_request_failed",
            extra={
                "context": {
                    "path": request.url.path,
                    "errorType": type(exc).__name__,
                }
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "요청을 처리할 수 없습니다.",
                    "details": {},
                }
            },
        )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            service=resolved.app_name,
            status="OK",
            version=VERSION,
            time=datetime.now(UTC),
        )

    @application.get(
        "/api/v1/system/info",
        response_model=SystemInfoResponse,
        tags=["system"],
    )
    async def system_info() -> SystemInfoResponse:
        database_reachable = bool(
            resolved.database_configured
            and resolved_database is not None
            and resolved_database.reachable()
        )
        last_instrument_sync_at = None
        last_disclosure_sync_at = None
        disclosure_database_count = 0
        event_count = 0
        configured_news_source_count = 0
        enabled_news_source_count = 0
        news_database_count = 0
        duplicate_news_count = 0
        stale_reused_count = 0
        corrected_news_count = 0
        denied_news_count = 0
        last_news_sync_at = None
        last_successful_news_sync_at = None
        last_email_sent_at = None
        monthly_app_email_sent_count = 0
        last_radar_cycle_at = None
        last_cleanup_at = None
        average_run_duration_seconds = None
        collection_success_rate = None
        delayed_run_count = 0
        database_bytes_availability = Availability.NOT_AVAILABLE
        database_bytes = None
        operating_mode = OperatingMode.NORMAL
        calendar_service = MarketScheduleService(
            default_market_calendar(enabled=resolved.market_calendar_enabled)
        )
        krx_calendar_status = ScheduleStatus.NOT_CONFIGURED
        nasdaq_calendar_status = ScheduleStatus.NOT_CONFIGURED
        next_market_briefing = None
        enabled_market_briefing_count = 0
        last_krx_briefing = None
        last_nasdaq_briefing = None
        risk_profile_configured = False
        risk_recommendation_available = False
        risk_recommendation_confidence = None
        risk_recommendation_stale = False
        portfolio_fingerprint_changed = False
        upbit_public_quote_status = (
            "READY" if resolved.upbit_public_market_enabled else "NOT_CONFIGURED"
        )
        binance_public_quote_status = (
            "READY" if resolved.binance_public_market_enabled else "NOT_CONFIGURED"
        )
        open_dart_status = "CONFIGURED" if resolved.open_dart_configured else "NOT_CONFIGURED"
        sec_status = "CONFIGURED" if resolved.sec_configured else "NOT_CONFIGURED"
        last_provider_sync_at = None
        provider_success_rate = None
        latest_quote_count = 0
        verified_mapping_count = 0
        unresolved_mapping_count = 0
        stale_mapping_count = 0
        if database_reachable and resolved_database is not None:
            with resolved_database.session_scope() as session:
                provider_states = list(session.scalars(select(ProviderSyncStateRecord)))
                state_by_provider = {item.provider: item for item in provider_states}
                if state_by_provider.get("UPBIT") is not None:
                    upbit_public_quote_status = state_by_provider["UPBIT"].status
                if state_by_provider.get("BINANCE") is not None:
                    binance_public_quote_status = state_by_provider["BINANCE"].status
                if (
                    resolved.open_dart_configured
                    and state_by_provider.get("OPENDART") is not None
                ):
                    open_dart_status = (
                        "READY"
                        if state_by_provider["OPENDART"].status == "SUCCEEDED"
                        else state_by_provider["OPENDART"].status
                    )
                if resolved.sec_configured and state_by_provider.get("SEC_EDGAR") is not None:
                    sec_status = (
                        "READY"
                        if state_by_provider["SEC_EDGAR"].status == "SUCCEEDED"
                        else state_by_provider["SEC_EDGAR"].status
                    )
                last_provider_sync_at = max(
                    (
                        item.last_success_at
                        for item in provider_states
                        if item.last_success_at is not None
                    ),
                    default=None,
                )
                provider_request_count = sum(item.request_count for item in provider_states)
                provider_success_count = sum(item.success_count for item in provider_states)
                if provider_request_count:
                    provider_success_rate = min(
                        100,
                        round(provider_success_count / provider_request_count * 100),
                    )
                latest_quotes = (
                    select(
                        QuoteSnapshotRecord.provider,
                        QuoteSnapshotRecord.instrument_id,
                    )
                    .group_by(
                        QuoteSnapshotRecord.provider,
                        QuoteSnapshotRecord.instrument_id,
                    )
                    .subquery()
                )
                latest_quote_count = int(
                    session.scalar(select(func.count()).select_from(latest_quotes)) or 0
                )
                verified_mapping_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(InstrumentProviderMappingRecord)
                        .where(
                            InstrumentProviderMappingRecord.mapping_status
                            == MappingStatus.VERIFIED
                        )
                    )
                    or 0
                )
                unresolved_mapping_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(InstrumentProviderMappingRecord)
                        .where(
                            InstrumentProviderMappingRecord.mapping_status.in_(
                                (
                                    MappingStatus.UNRESOLVED,
                                    MappingStatus.CONFLICTING,
                                )
                            )
                        )
                    )
                    or 0
                )
                stale_mapping_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(InstrumentProviderMappingRecord)
                        .where(
                            InstrumentProviderMappingRecord.mapping_status
                            == MappingStatus.STALE
                        )
                    )
                    or 0
                )
                disclosure_database_count = int(
                    session.scalar(select(func.count()).select_from(DisclosureRecord)) or 0
                )
                event_count = int(
                    session.scalar(select(func.count()).select_from(InformationEventRecord))
                    or 0
                )
                configured_news_source_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(SourceRecord)
                        .where(SourceRecord.feed_url.is_not(None))
                    )
                    or 0
                )
                enabled_news_source_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(SourceRecord)
                        .where(
                            SourceRecord.feed_url.is_not(None),
                            SourceRecord.enabled.is_(True),
                        )
                    )
                    or 0
                )
                news_database_count = int(
                    session.scalar(select(func.count()).select_from(NewsReferenceRecord)) or 0
                )
                duplicate_news_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(NewsReferenceRecord)
                        .where(NewsReferenceRecord.duplicate_of_id.is_not(None))
                    )
                    or 0
                )
                stale_reused_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(NewsReferenceRecord)
                        .where(NewsReferenceRecord.stale_reused.is_(True))
                    )
                    or 0
                )
                corrected_news_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(NewsReferenceRecord)
                        .where(
                            NewsReferenceRecord.lifecycle_status == LifecycleStatus.CORRECTED
                        )
                    )
                    or 0
                )
                denied_news_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(NewsReferenceRecord)
                        .where(NewsReferenceRecord.lifecycle_status == LifecycleStatus.DENIED)
                    )
                    or 0
                )
                last_instrument_sync_at = session.scalar(
                    select(CollectionRunRecord.finished_at)
                    .where(
                        CollectionRunRecord.run_type == CollectionRunType.INSTRUMENT_SYNC,
                        CollectionRunRecord.status == CollectionStatus.SUCCEEDED,
                    )
                    .order_by(CollectionRunRecord.finished_at.desc())
                    .limit(1)
                )
                last_disclosure_sync_at = session.scalar(
                    select(CollectionRunRecord.finished_at)
                    .where(
                        CollectionRunRecord.run_type == CollectionRunType.DISCLOSURE_SYNC,
                        CollectionRunRecord.status == CollectionStatus.SUCCEEDED,
                    )
                    .order_by(CollectionRunRecord.finished_at.desc())
                    .limit(1)
                )
                last_news_sync_at = session.scalar(
                    select(CollectionRunRecord.finished_at)
                    .where(CollectionRunRecord.run_type == CollectionRunType.NEWS_SYNC)
                    .order_by(CollectionRunRecord.finished_at.desc())
                    .limit(1)
                )
                last_successful_news_sync_at = session.scalar(
                    select(CollectionRunRecord.finished_at)
                    .where(
                        CollectionRunRecord.run_type == CollectionRunType.NEWS_SYNC,
                        CollectionRunRecord.status == CollectionStatus.SUCCEEDED,
                    )
                    .order_by(CollectionRunRecord.finished_at.desc())
                    .limit(1)
                )
                current = datetime.now(UTC)
                month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_email_sent_at = session.scalar(
                    select(NotificationDeliveryRecord.delivered_at)
                    .where(NotificationDeliveryRecord.status == DeliveryStatus.SENT)
                    .order_by(NotificationDeliveryRecord.delivered_at.desc())
                    .limit(1)
                )
                monthly_app_email_sent_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(NotificationDeliveryRecord)
                        .where(
                            NotificationDeliveryRecord.status == DeliveryStatus.SENT,
                            NotificationDeliveryRecord.delivered_at >= month_start,
                        )
                    )
                    or 0
                )
                last_radar_cycle_at = session.scalar(
                    select(CollectionRunRecord.finished_at)
                    .where(CollectionRunRecord.run_type == CollectionRunType.RADAR_CYCLE)
                    .order_by(CollectionRunRecord.finished_at.desc())
                    .limit(1)
                )
                last_cleanup_at = session.scalar(
                    select(CollectionRunRecord.finished_at)
                    .where(CollectionRunRecord.run_type == CollectionRunType.RETENTION_CLEANUP)
                    .order_by(CollectionRunRecord.finished_at.desc())
                    .limit(1)
                )
                latest_usage = session.scalar(
                    select(UsageSnapshotRecord)
                    .order_by(UsageSnapshotRecord.collected_at.desc())
                    .limit(1)
                )
                if latest_usage:
                    average_run_duration_seconds = latest_usage.average_duration_seconds
                    collection_success_rate = latest_usage.collection_success_rate
                    delayed_run_count = latest_usage.delayed_run_count
                    database_bytes_availability = latest_usage.database_bytes_availability
                    database_bytes = latest_usage.database_bytes
                    operating_mode = latest_usage.operating_mode
                preference = session.get(NotificationPreferenceRecord, "default")
                schedules = [
                    calendar_service.next_schedule(
                        kind, now=datetime.now(UTC), preference=preference
                    )
                    for kind in MARKET_BRIEFING_TYPES
                ]
                krx_calendar_status = schedules[0].session.schedule_status
                nasdaq_calendar_status = schedules[2].session.schedule_status
                enabled_market_briefing_count = sum(int(item.enabled) for item in schedules)
                next_times = [
                    item.scheduled_at
                    for item in schedules
                    if item.enabled and item.scheduled_at is not None
                ]
                next_market_briefing = min(next_times) if next_times else None
                last_krx_briefing = session.scalar(
                    select(BriefingRecord.generated_at)
                    .where(
                        BriefingRecord.briefing_type.in_(
                            (
                                BriefingType.KRX_PRE_OPEN,
                                BriefingType.KRX_POST_CLOSE,
                            )
                        )
                    )
                    .order_by(BriefingRecord.generated_at.desc())
                    .limit(1)
                )
                last_nasdaq_briefing = session.scalar(
                    select(BriefingRecord.generated_at)
                    .where(
                        BriefingRecord.briefing_type.in_(
                            (
                                BriefingType.NASDAQ_PRE_OPEN,
                                BriefingType.NASDAQ_POST_CLOSE,
                            )
                        )
                    )
                    .order_by(BriefingRecord.generated_at.desc())
                    .limit(1)
                )
                risk_profile_configured = session.get(RiskProfileRecord, "default") is not None
                risk_recommendation = RiskRecommendationService(session).recommend()
                risk_recommendation_available = True
                risk_recommendation_confidence = risk_recommendation.confidence
                risk_recommendation_stale = risk_recommendation.portfolio_changed
                portfolio_fingerprint_changed = risk_recommendation.portfolio_changed
        news_configured = bool(resolved.news_configured and enabled_news_source_count > 0)
        return SystemInfoResponse(
            environment=resolved.app_env,
            database_configured=resolved.database_configured,
            database_reachable=database_reachable,
            database_type=resolved.database_type,
            email_configured=resolved.email_configured,
            scheduler_configured=resolved.scheduler_configured,
            market_providers_configured=resolved.market_providers_configured,
            news_providers_configured=news_configured,
            instrument_master_configured=resolved.instrument_master_configured,
            open_dart_configured=resolved.open_dart_configured,
            open_dart_status=open_dart_status,
            sec_configured=resolved.sec_configured,
            sec_status=sec_status,
            upbit_public_quote_status=upbit_public_quote_status,
            binance_public_quote_status=binance_public_quote_status,
            last_provider_sync_at=last_provider_sync_at,
            provider_success_rate=provider_success_rate,
            latest_quote_count=latest_quote_count,
            verified_mapping_count=verified_mapping_count,
            unresolved_mapping_count=unresolved_mapping_count,
            stale_mapping_count=stale_mapping_count,
            official_disclosure_sync_enabled=(resolved.official_disclosure_sync_enabled),
            last_instrument_sync_at=last_instrument_sync_at,
            last_disclosure_sync_at=last_disclosure_sync_at,
            retention_cleanup_enabled=resolved.retention_cleanup_enabled,
            raw_document_ttl_hours=resolved.raw_document_ttl_hours,
            disclosure_database_count=disclosure_database_count,
            event_count=event_count,
            news_configured=news_configured,
            news_sync_enabled=resolved.news_sync_enabled,
            news_provider_status=("READY" if news_configured else "NOT_CONFIGURED"),
            configured_news_source_count=configured_news_source_count,
            enabled_news_source_count=enabled_news_source_count,
            last_news_sync_at=last_news_sync_at,
            last_successful_news_sync_at=last_successful_news_sync_at,
            news_database_count=news_database_count,
            duplicate_news_count=duplicate_news_count,
            stale_reused_count=stale_reused_count,
            corrected_news_count=corrected_news_count,
            denied_news_count=denied_news_count,
            raw_news_ttl_hours=resolved.news_raw_content_ttl_hours,
            email_provider_status=("READY" if resolved.email_configured else "NOT_CONFIGURED"),
            last_email_sent_at=last_email_sent_at,
            monthly_app_email_sent_count=monthly_app_email_sent_count,
            last_radar_cycle_at=last_radar_cycle_at,
            average_run_duration_seconds=average_run_duration_seconds,
            collection_success_rate=collection_success_rate,
            delayed_run_count=delayed_run_count,
            database_bytes_availability=database_bytes_availability,
            database_bytes=database_bytes,
            operating_mode=operating_mode,
            budget_configured=BudgetService(resolved).configured,
            retention_auto_confirm=resolved.retention_auto_confirm,
            last_cleanup_at=last_cleanup_at,
            next_cleanup_scheduled=False,
            github_actions_usage_connected=False,
            market_calendar_configured=calendar_service.adapter.configured,
            krx_calendar_status=krx_calendar_status,
            nasdaq_calendar_status=nasdaq_calendar_status,
            next_market_briefing=next_market_briefing,
            enabled_market_briefing_count=enabled_market_briefing_count,
            last_krx_briefing=last_krx_briefing,
            last_nasdaq_briefing=last_nasdaq_briefing,
            risk_profile_configured=risk_profile_configured,
            risk_recommendation_available=risk_recommendation_available,
            risk_recommendation_confidence=(risk_recommendation_confidence),
            risk_recommendation_stale=risk_recommendation_stale,
            portfolio_fingerprint_changed=(portfolio_fingerprint_changed),
            ai_automation_enabled=False,
            automatic_trading_enabled=False,
            version=VERSION,
            time=datetime.now(UTC),
        )

    return application


app = create_app()
