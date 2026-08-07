from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.operations import Availability, OperatingMode
from app.schemas.risk import RiskRecommendationConfidence
from app.services.market_calendar import ScheduleStatus


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: (
            value.split("_")[0] + "".join(part.capitalize() for part in value.split("_")[1:])
        ),
        populate_by_name=True,
    )


class HealthResponse(ApiSchema):
    service: str
    status: Literal["OK"]
    version: str
    time: datetime


class SystemInfoResponse(ApiSchema):
    environment: str
    database_configured: bool
    database_reachable: bool
    database_type: Literal["NOT_CONFIGURED", "SQLITE", "POSTGRESQL", "OTHER"]
    email_configured: bool
    scheduler_configured: bool
    market_providers_configured: bool
    news_providers_configured: bool
    instrument_master_configured: bool
    open_dart_configured: bool
    open_dart_status: str
    sec_configured: bool
    sec_status: str
    upbit_public_quote_status: str
    binance_public_quote_status: str
    last_provider_sync_at: datetime | None
    provider_success_rate: int | None
    latest_quote_count: int
    verified_mapping_count: int
    unresolved_mapping_count: int
    stale_mapping_count: int
    official_disclosure_sync_enabled: bool
    last_instrument_sync_at: datetime | None
    last_disclosure_sync_at: datetime | None
    retention_cleanup_enabled: bool
    raw_document_ttl_hours: int
    disclosure_database_count: int
    event_count: int
    news_configured: bool
    news_sync_enabled: bool
    news_provider_status: str
    configured_news_source_count: int
    enabled_news_source_count: int
    last_news_sync_at: datetime | None
    last_successful_news_sync_at: datetime | None
    news_database_count: int
    duplicate_news_count: int
    stale_reused_count: int
    corrected_news_count: int
    denied_news_count: int
    raw_news_ttl_hours: int
    email_provider_status: str
    last_email_sent_at: datetime | None
    monthly_app_email_sent_count: int
    last_radar_cycle_at: datetime | None
    average_run_duration_seconds: int | None
    collection_success_rate: int | None
    delayed_run_count: int
    database_bytes_availability: Availability
    database_bytes: int | None
    operating_mode: OperatingMode
    budget_configured: bool
    retention_auto_confirm: bool
    last_cleanup_at: datetime | None
    next_cleanup_scheduled: bool
    github_actions_usage_connected: bool
    market_calendar_configured: bool
    krx_calendar_status: ScheduleStatus
    nasdaq_calendar_status: ScheduleStatus
    next_market_briefing: datetime | None
    enabled_market_briefing_count: int
    last_krx_briefing: datetime | None
    last_nasdaq_briefing: datetime | None
    risk_profile_configured: bool
    risk_recommendation_available: bool
    risk_recommendation_confidence: RiskRecommendationConfidence | None
    risk_recommendation_stale: bool
    portfolio_fingerprint_changed: bool
    ai_automation_enabled: Literal[False] = False
    automatic_trading_enabled: Literal[False] = False
    version: str
    time: datetime
