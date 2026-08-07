from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.disclosures import (
    CollectionRunRecord,
    CollectionStatus,
)
from app.models.operations import (
    Availability,
    DeliveryStatus,
    NotificationDeliveryRecord,
    OperatingMode,
    UsageSnapshotRecord,
)


class BudgetService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return any(
            value is not None
            for value in (
                self.settings.monthly_compute_budget_minutes,
                self.settings.monthly_email_budget_count,
                self.settings.database_budget_bytes,
            )
        )

    def mode(
        self,
        *,
        compute_minutes: int,
        email_count: int,
        database_bytes: int | None,
    ) -> OperatingMode:
        ratios: list[float] = []
        if self.settings.monthly_compute_budget_minutes:
            ratios.append(compute_minutes / self.settings.monthly_compute_budget_minutes * 100)
        if self.settings.monthly_email_budget_count:
            ratios.append(email_count / self.settings.monthly_email_budget_count * 100)
        if self.settings.database_budget_bytes and database_bytes is not None:
            ratios.append(database_bytes / self.settings.database_budget_bytes * 100)
        if not ratios:
            return OperatingMode.NORMAL
        usage = max(ratios)
        if usage >= self.settings.pause_threshold_percent:
            return OperatingMode.PAUSED
        if usage >= self.settings.minimal_threshold_percent:
            return OperatingMode.MINIMAL
        if usage >= self.settings.saving_threshold_percent:
            return OperatingMode.SAVING
        if usage >= self.settings.warning_threshold_percent:
            return OperatingMode.WARNING
        return OperatingMode.NORMAL

    @staticmethod
    def scope(mode: OperatingMode) -> dict[str, bool]:
        return {
            "holdingOfficial": True,
            "correctionAndDenial": True,
            "deduplication": True,
            "watchlistNews": mode in {OperatingMode.NORMAL, OperatingMode.WARNING},
            "generalNews": mode not in {OperatingMode.MINIMAL, OperatingMode.PAUSED},
            "automaticNewsPaused": mode is OperatingMode.PAUSED,
            "recommendationsEnabled": False,
        }


class UsageService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def collect(
        self, *, now: datetime | None = None, persist: bool = True
    ) -> UsageSnapshotRecord:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        runs = list(
            self.session.scalars(
                select(CollectionRunRecord).where(
                    CollectionRunRecord.started_at >= start,
                    CollectionRunRecord.finished_at.is_not(None),
                )
            )
        )
        durations = [
            (
                run.duration_milliseconds
                if run.duration_milliseconds is not None
                else int((run.finished_at - run.started_at).total_seconds() * 1000)
            )
            for run in runs
            if run.finished_at is not None
        ]
        estimated_minutes = math.ceil(sum(durations) / 60_000)
        completed = [
            run
            for run in runs
            if run.status in {CollectionStatus.SUCCEEDED, CollectionStatus.FAILED}
        ]
        success_count = sum(int(run.status is CollectionStatus.SUCCEEDED) for run in completed)
        success_rate = round(success_count / len(completed) * 100) if completed else None
        database_availability, database_bytes = self._database_size()
        email_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(NotificationDeliveryRecord)
                .where(
                    NotificationDeliveryRecord.status == DeliveryStatus.SENT,
                    NotificationDeliveryRecord.delivered_at >= start,
                )
            )
            or 0
        )
        mode = BudgetService(self.settings).mode(
            compute_minutes=estimated_minutes,
            email_count=email_count,
            database_bytes=database_bytes,
        )
        snapshot = UsageSnapshotRecord(
            period=current.strftime("%Y-%m"),
            collected_at=current,
            action_minutes_availability=Availability.NOT_CONFIGURED,
            provider_reported_action_minutes=None,
            locally_estimated_compute_minutes=estimated_minutes,
            database_bytes_availability=database_availability,
            database_bytes=database_bytes,
            email_count_availability=Availability.AVAILABLE,
            email_sent_count=email_count,
            collection_success_rate=success_rate,
            scheduled_run_count=sum(int(run.scheduled_for is not None) for run in runs),
            delayed_run_count=sum(int((run.delay_milliseconds or 0) > 0) for run in runs),
            failed_run_count=sum(int(run.status is CollectionStatus.FAILED) for run in runs),
            average_duration_seconds=(
                round(sum(durations) / len(durations) / 1000) if durations else None
            ),
            operating_mode=mode,
        )
        if persist:
            self.session.add(snapshot)
            self.session.flush()
        return snapshot

    def latest(self) -> UsageSnapshotRecord | None:
        return self.session.scalar(
            select(UsageSnapshotRecord)
            .order_by(UsageSnapshotRecord.collected_at.desc())
            .limit(1)
        )

    def _database_size(self) -> tuple[Availability, int | None]:
        bind = self.session.get_bind()
        try:
            if bind.dialect.name == "sqlite":
                database = make_url(self.settings.database_url).database
                if not database or database == ":memory:":
                    return Availability.NOT_AVAILABLE, None
                path = Path(database)
                if not path.is_absolute():
                    path = path.resolve()
                return (
                    (Availability.AVAILABLE, path.stat().st_size)
                    if path.exists()
                    else (Availability.NOT_AVAILABLE, None)
                )
            if bind.dialect.name == "postgresql":
                value = self.session.scalar(
                    select(func.pg_database_size(func.current_database()))
                )
                return Availability.AVAILABLE, int(value) if value else 0
        except (OSError, SQLAlchemyError, ValueError):
            return Availability.NOT_AVAILABLE, None
        return Availability.NOT_AVAILABLE, None


def collection_success_formula() -> str:
    return "SUCCEEDED CollectionRun 수 / (SUCCEEDED + FAILED CollectionRun 수) × 100"
