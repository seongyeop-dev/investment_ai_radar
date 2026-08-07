from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.disclosures import (
    CollectionRunRecord,
    CollectionRunType,
    CollectionStatus,
    ProviderName,
)
from app.models.operations import (
    BriefingRecord,
    BriefingType,
    NotificationPreferenceRecord,
    OperatingMode,
)
from app.services.analysis import AnalysisService
from app.services.briefings import BriefingService
from app.services.disclosure_sync import OfficialDisclosureSyncService
from app.services.email_delivery import EmailDeliveryService
from app.services.market_briefings import MarketBriefingPreviewService
from app.services.market_calendar import (
    MarketScheduleService,
    default_market_calendar,
)
from app.services.news import NewsSyncService
from app.services.operations import UsageService
from app.services.retention import RetentionService


class RadarCycleService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def run(
        self,
        *,
        now: datetime | None = None,
        scheduled_for: datetime | None = None,
        dry_run: bool = True,
        confirm_send: bool = False,
    ) -> dict[str, object]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        started = perf_counter()
        usage_service = UsageService(self.session, self.settings)
        preflight_usage = usage_service.collect(now=current, persist=False)
        operating_mode = preflight_usage.operating_mode
        sync_results: dict[str, dict[str, int | str]] = {}
        if not dry_run:
            official_sync = OfficialDisclosureSyncService(self.session, self.settings)
            if self.settings.open_dart_configured:
                sync_results["openDart"] = official_sync.sync(
                    ProviderName.OPENDART, now=current
                )
            if self.settings.sec_configured:
                sync_results["sec"] = official_sync.sync(ProviderName.SEC_EDGAR, now=current)
            if self.settings.news_configured:
                if operating_mode in {
                    OperatingMode.MINIMAL,
                    OperatingMode.PAUSED,
                }:
                    sync_results["news"] = {
                        "status": "SKIPPED_BUDGET_MODE",
                        "fetched": 0,
                        "created": 0,
                    }
                else:
                    sync_results["news"] = NewsSyncService(self.session, self.settings).sync(
                        now=current, operating_mode=operating_mode
                    )
            structured_impacts = AnalysisService(self.session).sync_direct_impacts()
        else:
            structured_impacts = 0
        preference = self.session.get(NotificationPreferenceRecord, "default")
        minimum_priority = preference.minimum_priority if preference else 0
        market_schedule_service = MarketScheduleService(default_market_calendar())
        existing_market_keys = set(self.session.scalars(select(BriefingRecord.idempotency_key)))
        due_market_schedules = market_schedule_service.due_schedules(
            now=current,
            preference=preference,
            existing_keys=existing_market_keys,
        )
        market_briefings: list[dict[str, object]] = []
        for schedule in due_market_schedules:
            preview = MarketBriefingPreviewService(
                self.session, self.settings, market_schedule_service
            ).preview(
                schedule.briefing_type,
                session_date=schedule.session.session_date,
                now=current,
            )
            market_generation = BriefingService(self.session).generate(
                period_start=preview.investigation_start,
                period_end=preview.investigation_end,
                now=current,
                briefing_type=schedule.briefing_type,
                minimum_priority=minimum_priority,
                persist=not dry_run,
                idempotency_key_override=schedule.idempotency_key,
                preserve_briefing_type=True,
                include_no_change=bool(
                    preference and preference.send_no_material_change_briefing
                ),
                provider_complete=not preview.data_missing,
            )
            market_delivery = "PREVIEW"
            if (
                not dry_run
                and not preview.data_missing
                and market_generation.items
                and preference
                and preference.enabled
                and self.settings.email_configured
            ):
                delivery = EmailDeliveryService(self.session, self.settings).send(
                    market_generation.briefing,
                    recipient=preference.recipient_email,
                    now=current,
                    confirm=confirm_send,
                )
                market_delivery = delivery.status.value
            elif not self.settings.email_configured:
                market_delivery = "NOT_CONFIGURED"
            market_briefings.append(
                {
                    "briefingType": schedule.briefing_type.value,
                    "sessionDate": schedule.session.session_date.isoformat(),
                    "idempotencyKey": schedule.idempotency_key,
                    "briefingStatus": market_generation.briefing.status.value,
                    "deliveryStatus": market_delivery,
                    "dataMissing": preview.data_missing,
                }
            )
        generation = BriefingService(self.session).generate(
            period_start=current - timedelta(hours=1),
            period_end=current,
            now=current,
            briefing_type=(
                BriefingType.MANUAL_PREVIEW if dry_run else BriefingType.CHANGE_BRIEFING
            ),
            minimum_priority=minimum_priority,
            persist=not dry_run,
        )
        delivery_status = "SKIPPED"
        if not dry_run and generation.items and preference and preference.enabled:
            delivery = EmailDeliveryService(self.session, self.settings).send(
                generation.briefing,
                recipient=preference.recipient_email,
                now=current,
                confirm=confirm_send,
            )
            delivery_status = delivery.status.value
        retention_status = "DISABLED"
        retention_deleted = 0
        if (
            not dry_run
            and self.settings.retention_cleanup_enabled
            and self.settings.retention_auto_confirm
        ):
            retention = RetentionService(self.session, self.settings).run(
                now=current, dry_run=False, confirm=True
            )
            retention_status = retention.status
            retention_deleted = sum(
                value
                for key, value in retention.as_dict().items()
                if key != "status" and isinstance(value, int)
            )
        usage_service.collect(now=current, persist=not dry_run)
        duration_ms = round((perf_counter() - started) * 1000)
        failed_syncs = [
            name
            for name, result in sync_results.items()
            if result.get("status")
            not in {
                "SUCCEEDED",
                "NOT_CONFIGURED",
                "DRY_RUN",
                "SKIPPED_BUDGET_MODE",
            }
        ]
        successful_syncs = [
            name for name, result in sync_results.items() if result.get("status") == "SUCCEEDED"
        ]
        cycle_status = (
            "DRY_RUN"
            if dry_run
            else "PARTIAL_SUCCESS"
            if failed_syncs and successful_syncs
            else "FAILED"
            if failed_syncs
            else "SUCCEEDED"
        )
        output: dict[str, object] = {
            "status": cycle_status,
            "providerStatus": {
                "openDart": (
                    "READY" if self.settings.open_dart_configured else "NOT_CONFIGURED"
                ),
                "sec": "READY" if self.settings.sec_configured else "NOT_CONFIGURED",
                "news": ("READY" if self.settings.news_configured else "NOT_CONFIGURED"),
                "email": ("READY" if self.settings.email_configured else "NOT_CONFIGURED"),
            },
            "briefingStatus": generation.briefing.status.value,
            "candidateCount": len(generation.items),
            "excludedDuplicateCount": generation.excluded_duplicates,
            "deliveryStatus": delivery_status,
            "retentionStatus": retention_status,
            "operatingMode": operating_mode.value,
            "durationMilliseconds": duration_ms,
            "syncResults": sync_results,
            "portfolioImpactCreatedCount": structured_impacts,
            "quoteSyncCallCount": 0,
            "marketBriefings": market_briefings,
            "marketCalendarStatus": (
                "READY" if market_schedule_service.adapter.configured else "NOT_CONFIGURED"
            ),
        }
        if not dry_run:
            delay = (
                max(0, int((current - scheduled_for).total_seconds() * 1000))
                if scheduled_for
                else None
            )
            self.session.add(
                CollectionRunRecord(
                    provider=ProviderName.SYSTEM_BASELINE,
                    run_type=CollectionRunType.RADAR_CYCLE,
                    scheduled_for=scheduled_for,
                    started_at=current,
                    finished_at=current,
                    duration_milliseconds=duration_ms,
                    delay_milliseconds=delay,
                    status=(
                        CollectionStatus.FAILED if failed_syncs else CollectionStatus.SUCCEEDED
                    ),
                    success=not failed_syncs,
                    partial_success=bool(failed_syncs and successful_syncs),
                    material_change_count=generation.briefing.material_change_count,
                    email_attempt_count=int(delivery_status != "SKIPPED"),
                    email_sent_count=int(delivery_status == "SENT"),
                    retention_deleted_count=retention_deleted,
                    estimated_compute_seconds=max(0, round(duration_ms / 1000)),
                    error_count=len(failed_syncs),
                    result_details=output,
                )
            )
            self.session.flush()
        return output
