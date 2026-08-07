from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.core.config import Settings
from app.models.disclosures import (
    CollectionRunRecord,
    CollectionRunType,
)
from app.models.operations import (
    Availability,
    DeliveryStatus,
    NotificationDeliveryRecord,
    OperatingMode,
    UsageSnapshotRecord,
)
from app.schemas.operations import (
    OperationMetricList,
    OperationMetricRead,
    OperationStatusRead,
    UsageSnapshotList,
    UsageSnapshotRead,
)
from app.services.operations import BudgetService, collection_success_formula

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/metrics", response_model=OperationMetricList)
def list_metrics(
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> OperationMetricList:
    records = list(
        session.scalars(
            select(CollectionRunRecord)
            .order_by(CollectionRunRecord.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    total = int(session.scalar(select(func.count()).select_from(CollectionRunRecord)) or 0)
    return OperationMetricList(
        items=[OperationMetricRead.model_validate(record) for record in records],
        total=total,
        limit=limit,
        offset=offset,
    )


def _usage(record: UsageSnapshotRecord, settings: Settings) -> UsageSnapshotRead:
    return UsageSnapshotRead.model_validate(record).model_copy(
        update={
            "budget_configured": BudgetService(settings).configured,
            "success_rate_formula": collection_success_formula(),
        }
    )


@router.get("/usage", response_model=UsageSnapshotList)
def list_usage(
    request: Request,
    session: SessionDependency,
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> UsageSnapshotList:
    records = list(
        session.scalars(
            select(UsageSnapshotRecord)
            .order_by(UsageSnapshotRecord.collected_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    total = int(session.scalar(select(func.count()).select_from(UsageSnapshotRecord)) or 0)
    return UsageSnapshotList(
        items=[_usage(record, request.app.state.settings) for record in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/status", response_model=OperationStatusRead)
def operation_status(
    request: Request,
    session: SessionDependency,
) -> OperationStatusRead:
    settings: Settings = request.app.state.settings
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_sent = session.scalar(
        select(NotificationDeliveryRecord.delivered_at)
        .where(NotificationDeliveryRecord.status == DeliveryStatus.SENT)
        .order_by(NotificationDeliveryRecord.delivered_at.desc())
        .limit(1)
    )
    sent_count = int(
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

    def last_run(run_type: CollectionRunType) -> datetime | None:
        return session.scalar(
            select(CollectionRunRecord.finished_at)
            .where(CollectionRunRecord.run_type == run_type)
            .order_by(CollectionRunRecord.finished_at.desc())
            .limit(1)
        )

    latest_usage = session.scalar(
        select(UsageSnapshotRecord).order_by(UsageSnapshotRecord.collected_at.desc()).limit(1)
    )
    return OperationStatusRead(
        email_configured=settings.email_configured,
        email_provider_status=("READY" if settings.email_configured else "NOT_CONFIGURED"),
        last_email_sent_at=last_sent,
        monthly_app_email_sent_count=sent_count,
        last_radar_cycle_at=last_run(CollectionRunType.RADAR_CYCLE),
        last_cleanup_at=last_run(CollectionRunType.RETENTION_CLEANUP),
        retention_cleanup_enabled=settings.retention_cleanup_enabled,
        retention_auto_confirm=settings.retention_auto_confirm,
        budget_configured=BudgetService(settings).configured,
        action_minutes_availability=(
            latest_usage.action_minutes_availability
            if latest_usage
            else Availability.NOT_CONFIGURED
        ),
        operating_mode=(latest_usage.operating_mode if latest_usage else OperatingMode.NORMAL),
        github_actions_usage_connected=False,
        automatic_trading_enabled=False,
        ai_automation_enabled=False,
    )
