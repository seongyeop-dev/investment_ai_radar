from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.contracts import VerificationStatus
from app.models.operations import (
    Availability,
    BriefingStatus,
    BriefingType,
    OperatingMode,
)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class OperationSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, from_attributes=True
    )


class BriefingItemRead(OperationSchema):
    id: str
    information_event_id: str
    priority: int
    category: str
    headline: str
    short_summary: str
    verification_status: VerificationStatus
    trust_score: int
    trust_score_explanation: str = "사실일 확률이 아니라 현재 확보된 증거 강도입니다."
    material_change: bool
    changed_facts: list[dict[str, object]]
    source_links: list[dict[str, str]]
    official_reference_links: list[dict[str, str]]
    published_at: datetime
    portfolio_item_id: str | None = None
    portfolio_name: str | None = None
    current_status: str | None = None
    management_direction: str = "INSUFFICIENT_DATA"
    importance: int = 0
    what_happened: str = ""
    official_confirmation: str = "NEEDS_VERIFICATION"
    thesis_effect: str = "UNKNOWN"
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    conditions_to_add: list[str] = Field(default_factory=list)
    conditions_to_reduce: list[str] = Field(default_factory=list)
    conditions_to_exit: list[str] = Field(default_factory=list)
    next_information: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    information_valid_until: datetime | None = None
    human_decision_required: bool = True


class BriefingRead(OperationSchema):
    id: str
    briefing_type: BriefingType
    status: BriefingStatus
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    title: str
    compact_summary: str
    item_count: int
    material_change_count: int
    correction_count: int
    denial_count: int
    official_confirmed_count: int
    needs_verification_count: int
    related_instrument_ids: list[str]
    valid_until: datetime
    items: list[BriefingItemRead] = Field(default_factory=list)


class BriefingList(OperationSchema):
    items: list[BriefingRead]
    total: int
    limit: int
    offset: int
    email_configured: bool


class BriefingGenerationRequest(OperationSchema):
    period_start: datetime
    period_end: datetime
    minimum_priority: int = Field(default=0, ge=0, le=100)
    included_items_confirmed: bool = False
    confirm: bool = False

    @field_validator("period_start", "period_end")
    @classmethod
    def aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("브리핑 기간에는 시간대 정보가 필요합니다.")
        return value.astimezone(UTC)


class BriefingGenerationPreview(OperationSchema):
    briefing: BriefingRead
    excluded_duplicates: int
    existing_briefing_id: str | None
    would_create: bool
    can_confirm: bool
    confirmed: Literal[False] = False
    persisted: Literal[False] = False
    email_delivery_created: Literal[False] = False


class BriefingGenerationConfirmed(OperationSchema):
    briefing: BriefingRead
    excluded_duplicates: int
    created: Literal[True] = True
    confirmed: Literal[True] = True
    persisted: Literal[True] = True
    email_delivery_created: Literal[False] = False


class NotificationPreferenceInput(OperationSchema):
    enabled: bool = False
    hourly_change_briefing_enabled: bool = False
    daily_digest_enabled: bool = False
    krx_pre_open_enabled: bool = False
    krx_post_close_enabled: bool = False
    nasdaq_pre_open_enabled: bool = False
    nasdaq_post_close_enabled: bool = False
    immediate_material_change_enabled: bool = False
    correction_notice_enabled: bool = True
    provider_failure_notice_enabled: bool = False
    recipient_email: str | None = None
    timezone: str = "Asia/Seoul"
    daily_digest_hour: int = Field(default=8, ge=0, le=23)
    minimum_priority: int = Field(default=50, ge=0, le=100)
    include_watchlist: bool = True
    include_reentry_watch: bool = False
    include_sold: bool = False
    send_no_material_change_briefing: bool = False
    krx_pre_open_offset_minutes: int = Field(default=40, ge=0, le=240)
    krx_post_close_offset_minutes: int = Field(default=20, ge=0, le=240)
    nasdaq_pre_open_offset_minutes: int = Field(default=60, ge=0, le=240)
    nasdaq_post_close_offset_minutes: int = Field(default=20, ge=0, le=240)

    @field_validator("recipient_email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("수신 이메일 형식이 올바르지 않습니다.")
        return normalized

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 64:
            raise ValueError("시간대를 확인해 주세요.")
        return normalized


class NotificationPreferenceRead(OperationSchema):
    configured: bool
    email_provider_status: str
    enabled: bool
    hourly_change_briefing_enabled: bool
    daily_digest_enabled: bool
    krx_pre_open_enabled: bool
    krx_post_close_enabled: bool
    nasdaq_pre_open_enabled: bool
    nasdaq_post_close_enabled: bool
    immediate_material_change_enabled: bool
    correction_notice_enabled: bool
    provider_failure_notice_enabled: bool
    recipient_email_masked: str | None
    timezone: str
    daily_digest_hour: int
    minimum_priority: int
    include_watchlist: bool
    include_reentry_watch: bool
    include_sold: bool
    include_holdings: bool = True
    send_no_material_change_briefing: bool
    krx_pre_open_offset_minutes: int
    krx_post_close_offset_minutes: int
    nasdaq_pre_open_offset_minutes: int
    nasdaq_post_close_offset_minutes: int
    created_at: datetime | None
    updated_at: datetime | None


class OperationMetricRead(OperationSchema):
    id: str
    run_type: str
    scheduled_for: datetime | None
    started_at: datetime
    finished_at: datetime | None
    duration_milliseconds: int | None
    delay_milliseconds: int | None
    success: bool | None
    partial_success: bool
    provider: str
    fetched_count: int
    created_count: int
    updated_count: int
    duplicate_count: int
    material_change_count: int
    error_count: int
    email_attempt_count: int
    email_sent_count: int
    retention_deleted_count: int
    estimated_compute_seconds: int | None


class OperationMetricList(OperationSchema):
    items: list[OperationMetricRead]
    total: int
    limit: int
    offset: int


class UsageSnapshotRead(OperationSchema):
    id: str | None = None
    period: str
    collected_at: datetime
    action_minutes_availability: Availability
    provider_reported_action_minutes: int | None
    locally_estimated_compute_minutes: int
    database_bytes_availability: Availability
    database_bytes: int | None
    email_count_availability: Availability
    email_sent_count: int
    collection_success_rate: int | None
    scheduled_run_count: int
    delayed_run_count: int
    failed_run_count: int
    average_duration_seconds: int | None
    operating_mode: OperatingMode
    budget_configured: bool = False
    success_rate_formula: str = (
        "SUCCEEDED CollectionRun 수 / (SUCCEEDED + FAILED CollectionRun 수) × 100"
    )


class UsageSnapshotList(OperationSchema):
    items: list[UsageSnapshotRead]
    total: int
    limit: int
    offset: int


class OperationStatusRead(OperationSchema):
    email_configured: bool
    email_provider_status: str
    last_email_sent_at: datetime | None
    monthly_app_email_sent_count: int
    last_radar_cycle_at: datetime | None
    last_cleanup_at: datetime | None
    retention_cleanup_enabled: bool
    retention_auto_confirm: bool
    budget_configured: bool
    action_minutes_availability: Availability
    operating_mode: OperatingMode
    github_actions_usage_connected: bool
    automatic_trading_enabled: bool = False
    ai_automation_enabled: bool = False
