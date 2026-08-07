from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from app.core.local_env import (
    load_local_environment,
    normalize_local_value,
    valid_contact_email,
    valid_opendart_key,
)


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(
    environment: Mapping[str, str],
    name: str,
    default: int,
    *,
    maximum: int | None = None,
) -> int:
    raw = environment.get(name, "").strip()
    value = int(raw) if raw else default
    if value <= 0 or (maximum is not None and value > maximum):
        upper = f" and at most {maximum}" if maximum is not None else ""
        raise ValueError(f"{name} must be positive{upper}")
    return value


def _optional_positive_int(environment: Mapping[str, str], name: str) -> int | None:
    raw = environment.get(name, "").strip()
    if not raw:
        return None
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_name: str
    database_url: str
    database_configured: bool
    email_configured: bool
    email_enabled: bool
    email_provider: str
    email_from: str
    email_to: str
    email_timeout_seconds: int
    email_max_retries: int
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_tls: bool
    resend_api_key: str
    app_public_base_url: str
    scheduler_configured: bool
    market_providers_configured: bool
    news_providers_configured: bool
    ai_automation_enabled: bool
    allowed_origins: tuple[str, ...]
    opendart_api_key: str
    opendart_sync_enabled: bool
    sec_user_agent: str
    sec_sync_enabled: bool
    upbit_public_market_enabled: bool
    binance_public_market_enabled: bool
    market_calendar_enabled: bool
    official_disclosure_sync_enabled: bool
    include_sold_in_disclosure_sync: bool
    retention_cleanup_enabled: bool
    retention_auto_confirm: bool
    raw_document_ttl_hours: int
    collection_log_retention_days: int
    duplicate_evidence_retention_days: int
    general_summary_retention_days: int
    event_fingerprint_retention_days: int
    important_briefing_retention_days: int
    news_sync_enabled: bool
    news_feed_sync_enabled: bool
    news_request_timeout_seconds: int
    news_max_items_per_source: int
    news_raw_content_ttl_hours: int
    news_source_config_path: str
    include_sold_in_news_sync: bool
    monthly_compute_budget_minutes: int | None
    monthly_email_budget_count: int | None
    database_budget_bytes: int | None
    warning_threshold_percent: int
    saving_threshold_percent: int
    minimal_threshold_percent: int
    pause_threshold_percent: int

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> Settings:
        env = environment if environment is not None else load_local_environment(os.environ)
        configured_database_url = env.get("DATABASE_URL", "").strip()
        allowed_origins = tuple(
            origin.strip()
            for origin in env.get(
                "ALLOWED_ORIGINS",
                (
                    "http://localhost:3000,"
                    "http://127.0.0.1:3000,"
                    "http://localhost:3001,"
                    "http://127.0.0.1:3001"
                ),
            ).split(",")
            if origin.strip()
        )
        email_provider = env.get("EMAIL_PROVIDER", "DISABLED").strip().upper() or "DISABLED"
        if email_provider not in {"DISABLED", "SMTP", "RESEND"}:
            raise ValueError("EMAIL_PROVIDER must be DISABLED, SMTP, or RESEND")
        email_enabled = _enabled(env.get("EMAIL_ENABLED"))
        email_from = env.get("EMAIL_FROM", "").strip()
        email_to = env.get("EMAIL_TO", "").strip()
        smtp_host = env.get("SMTP_HOST", "").strip()
        smtp_username = env.get("SMTP_USERNAME", "").strip()
        smtp_password = env.get("SMTP_PASSWORD", "").strip()
        resend_api_key = env.get("RESEND_API_KEY", "").strip()
        email_configured = (
            email_enabled
            and bool(email_from and email_to)
            and (
                (
                    email_provider == "SMTP"
                    and bool(smtp_host and smtp_username and smtp_password)
                )
                or (email_provider == "RESEND" and bool(resend_api_key))
            )
        )
        thresholds = (
            _positive_int(env, "WARNING_THRESHOLD_PERCENT", 70, maximum=100),
            _positive_int(env, "SAVING_THRESHOLD_PERCENT", 80, maximum=100),
            _positive_int(env, "MINIMAL_THRESHOLD_PERCENT", 90, maximum=100),
            _positive_int(env, "PAUSE_THRESHOLD_PERCENT", 98, maximum=100),
        )
        if thresholds != tuple(sorted(set(thresholds))):
            raise ValueError("budget thresholds must be strictly increasing")
        sec_app_name = (
            env.get("SEC_USER_AGENT_APP_NAME", "InvestmentAIRadar").strip()
            or "InvestmentAIRadar"
        )
        sec_contact_value = normalize_local_value(env.get("SEC_USER_AGENT_CONTACT", ""))
        sec_contact = sec_contact_value if valid_contact_email(sec_contact_value) else ""
        legacy_sec_user_agent = env.get("SEC_USER_AGENT", "").strip()
        sec_user_agent = legacy_sec_user_agent or (
            f"{sec_app_name}/0.2 {sec_contact}" if sec_contact else ""
        )
        return cls(
            app_env=env.get("APP_ENV", "local").strip() or "local",
            app_name=env.get("APP_NAME", "investment-ai-radar").strip()
            or "investment-ai-radar",
            database_url=(
                configured_database_url or "sqlite+pysqlite:///./investment_ai_radar.db"
            ),
            database_configured=bool(configured_database_url),
            email_configured=email_configured,
            email_enabled=email_enabled,
            email_provider=email_provider,
            email_from=email_from,
            email_to=email_to,
            email_timeout_seconds=_positive_int(env, "EMAIL_TIMEOUT_SECONDS", 10, maximum=60),
            email_max_retries=_positive_int(env, "EMAIL_MAX_RETRIES", 3, maximum=5),
            smtp_host=smtp_host,
            smtp_port=_positive_int(env, "SMTP_PORT", 587, maximum=65535),
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_use_tls=_enabled(env.get("SMTP_USE_TLS", "true")),
            resend_api_key=resend_api_key,
            app_public_base_url=env.get("APP_PUBLIC_BASE_URL", "http://127.0.0.1:3000")
            .strip()
            .rstrip("/"),
            scheduler_configured=_enabled(env.get("GITHUB_ACTIONS_ENABLED")),
            market_providers_configured=any(
                env.get(name, "").strip()
                for name in (
                    "MARKET_DATA_PROVIDER",
                    "GOLD_PROVIDER",
                    "OIL_PROVIDER",
                    "FX_PROVIDER",
                )
            ),
            news_providers_configured=bool(env.get("NEWS_PROVIDER", "").strip()),
            ai_automation_enabled=False,
            allowed_origins=allowed_origins,
            opendart_api_key=normalize_local_value(env.get("OPENDART_API_KEY", "")),
            opendart_sync_enabled=_enabled(
                env.get("OPENDART_ENABLED", env.get("OPENDART_SYNC_ENABLED"))
            ),
            sec_user_agent=sec_user_agent,
            sec_sync_enabled=_enabled(
                env.get("SEC_EDGAR_ENABLED", env.get("SEC_SYNC_ENABLED"))
            ),
            upbit_public_market_enabled=_enabled(
                env.get("UPBIT_PUBLIC_MARKET_ENABLED", "true")
            ),
            binance_public_market_enabled=_enabled(
                env.get("BINANCE_PUBLIC_MARKET_ENABLED", "true")
            ),
            market_calendar_enabled=_enabled(env.get("MARKET_CALENDAR_ENABLED")),
            official_disclosure_sync_enabled=_enabled(
                env.get("OFFICIAL_DISCLOSURE_SYNC_ENABLED")
            ),
            include_sold_in_disclosure_sync=_enabled(
                env.get("INCLUDE_SOLD_IN_DISCLOSURE_SYNC")
            ),
            retention_cleanup_enabled=_enabled(env.get("RETENTION_CLEANUP_ENABLED")),
            retention_auto_confirm=_enabled(env.get("RETENTION_AUTO_CONFIRM")),
            raw_document_ttl_hours=_positive_int(
                env,
                "RAW_DOCUMENT_TTL_HOURS",
                24,
                maximum=72,
            ),
            collection_log_retention_days=_positive_int(
                env,
                "COLLECTION_LOG_RETENTION_DAYS",
                14,
            ),
            duplicate_evidence_retention_days=_positive_int(
                env,
                "DUPLICATE_EVIDENCE_RETENTION_DAYS",
                30,
            ),
            general_summary_retention_days=_positive_int(
                env,
                "GENERAL_SUMMARY_RETENTION_DAYS",
                30,
            ),
            event_fingerprint_retention_days=_positive_int(
                env,
                "EVENT_FINGERPRINT_RETENTION_DAYS",
                180,
            ),
            important_briefing_retention_days=_positive_int(
                env,
                "IMPORTANT_BRIEFING_RETENTION_DAYS",
                90,
            ),
            news_sync_enabled=_enabled(env.get("NEWS_SYNC_ENABLED")),
            news_feed_sync_enabled=_enabled(env.get("NEWS_FEED_SYNC_ENABLED")),
            news_request_timeout_seconds=_positive_int(
                env, "NEWS_REQUEST_TIMEOUT_SECONDS", 10, maximum=60
            ),
            news_max_items_per_source=_positive_int(
                env, "NEWS_MAX_ITEMS_PER_SOURCE", 50, maximum=200
            ),
            news_raw_content_ttl_hours=_positive_int(
                env, "NEWS_RAW_CONTENT_TTL_HOURS", 24, maximum=24
            ),
            news_source_config_path=env.get("NEWS_SOURCE_CONFIG_PATH", "").strip(),
            include_sold_in_news_sync=_enabled(env.get("INCLUDE_SOLD_IN_NEWS_SYNC")),
            monthly_compute_budget_minutes=_optional_positive_int(
                env, "MONTHLY_COMPUTE_BUDGET_MINUTES"
            ),
            monthly_email_budget_count=_optional_positive_int(
                env, "MONTHLY_EMAIL_BUDGET_COUNT"
            ),
            database_budget_bytes=_optional_positive_int(env, "DATABASE_BUDGET_BYTES"),
            warning_threshold_percent=thresholds[0],
            saving_threshold_percent=thresholds[1],
            minimal_threshold_percent=thresholds[2],
            pause_threshold_percent=thresholds[3],
        )

    @property
    def open_dart_configured(self) -> bool:
        return self.opendart_sync_enabled and valid_opendart_key(self.opendart_api_key)

    @property
    def sec_configured(self) -> bool:
        return self.sec_sync_enabled and bool(self.sec_user_agent)

    @property
    def instrument_master_configured(self) -> bool:
        return self.open_dart_configured or self.sec_configured

    @property
    def news_configured(self) -> bool:
        return self.news_sync_enabled and self.news_feed_sync_enabled

    @property
    def database_type(self) -> str:
        if not self.database_configured:
            return "NOT_CONFIGURED"
        normalized = self.database_url.lower()
        if normalized.startswith("sqlite"):
            return "SQLITE"
        if normalized.startswith(("postgresql", "postgres")):
            return "POSTGRESQL"
        return "OTHER"
