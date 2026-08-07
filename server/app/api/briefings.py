from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.core.config import Settings
from app.core.errors import (
    briefing_generation_validation,
    notification_preference_validation,
)
from app.core.time import SystemClock
from app.models.analysis import PortfolioImpactRecord
from app.models.database import PortfolioItemRecord
from app.models.operations import (
    BriefingRecord,
    BriefingType,
    NotificationPreferenceRecord,
)
from app.schemas.operations import (
    BriefingGenerationConfirmed,
    BriefingGenerationPreview,
    BriefingGenerationRequest,
    BriefingItemRead,
    BriefingList,
    BriefingRead,
    NotificationPreferenceInput,
    NotificationPreferenceRead,
)
from app.services.analysis import AnalysisService
from app.services.briefings import BriefingService
from app.services.email_delivery import mask_email

router = APIRouter(prefix="/api/v1", tags=["briefings"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _briefing(
    record: BriefingRecord,
    service: BriefingService,
    *,
    with_items: bool,
) -> BriefingRead:
    return BriefingRead.model_validate(record).model_copy(
        update={
            "items": (
                [_briefing_item(item, record, service) for item in service.items(record.id)]
                if with_items
                else []
            )
        }
    )


def _briefing_generation(
    record: BriefingRecord,
    items: tuple[object, ...],
    service: BriefingService,
) -> BriefingRead:
    return BriefingRead.model_validate(record).model_copy(
        update={"items": [_briefing_item(item, record, service) for item in items]}
    )


def _briefing_item(
    item: object,
    briefing: BriefingRecord,
    service: BriefingService,
) -> BriefingItemRead:
    value = BriefingItemRead.model_validate(item)
    impact = service.session.scalar(
        select(PortfolioImpactRecord)
        .where(
            PortfolioImpactRecord.event_id == value.information_event_id,
        )
        .order_by(PortfolioImpactRecord.generated_at.desc())
        .limit(1)
    )
    if impact is None:
        return value.model_copy(
            update={
                "importance": value.priority,
                "what_happened": value.short_summary,
                "official_confirmation": value.verification_status.value,
                "information_valid_until": briefing.valid_until,
                "human_decision_required": True,
            }
        )
    portfolio = service.session.get(PortfolioItemRecord, impact.portfolio_item_id)
    review = AnalysisService(service.session).latest_review(impact.portfolio_item_id)
    return value.model_copy(
        update={
            "portfolio_item_id": impact.portfolio_item_id,
            "portfolio_name": portfolio.name if portfolio else None,
            "current_status": (
                f"{portfolio.position_status.value}/{portfolio.tracking_status.value}"
                if portfolio
                else None
            ),
            "management_direction": review.direction.value,
            "importance": value.priority,
            "what_happened": value.short_summary,
            "official_confirmation": value.verification_status.value,
            "thesis_effect": impact.thesis_effect,
            "positive_factors": impact.supporting_factors,
            "negative_factors": impact.opposing_factors,
            "conditions_to_add": review.conditions_to_add,
            "conditions_to_reduce": review.conditions_to_reduce,
            "conditions_to_exit": review.conditions_to_exit,
            "next_information": impact.missing_information,
            "invalidation_conditions": review.invalidation_conditions,
            "information_valid_until": briefing.valid_until,
            "human_decision_required": True,
        }
    )


@router.get("/briefings", response_model=BriefingList)
def list_briefings(
    request: Request,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> BriefingList:
    records = list(
        session.scalars(
            select(BriefingRecord)
            .order_by(BriefingRecord.generated_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    total = int(session.scalar(select(func.count()).select_from(BriefingRecord)) or 0)
    service = BriefingService(session)
    settings: Settings = request.app.state.settings
    return BriefingList(
        items=[_briefing(record, service, with_items=True) for record in records],
        total=total,
        limit=limit,
        offset=offset,
        email_configured=settings.email_configured,
    )


@router.post(
    "/briefings/generate",
    response_model=BriefingGenerationPreview | BriefingGenerationConfirmed,
)
def generate_briefing(
    payload: BriefingGenerationRequest,
    session: SessionDependency,
) -> BriefingGenerationPreview | BriefingGenerationConfirmed:
    now = SystemClock().now()
    if payload.period_start >= payload.period_end:
        raise briefing_generation_validation(
            "브리핑 시작 시각은 종료 시각보다 이전이어야 합니다."
        )
    if payload.period_end > now + timedelta(minutes=5):
        raise briefing_generation_validation(
            "브리핑 종료 시각은 현재 시각 이후로 설정할 수 없습니다."
        )

    service = BriefingService(session)
    preview_result = service.generate(
        period_start=payload.period_start,
        period_end=payload.period_end,
        now=now,
        briefing_type=BriefingType.CHANGE_BRIEFING,
        minimum_priority=payload.minimum_priority,
        persist=False,
    )
    existing = session.get(BriefingRecord, preview_result.briefing.id)
    would_create = existing is None and bool(preview_result.items)
    preview = BriefingGenerationPreview(
        briefing=_briefing_generation(
            preview_result.briefing,
            preview_result.items,
            service,
        ),
        excluded_duplicates=preview_result.excluded_duplicates,
        existing_briefing_id=existing.id if existing is not None else None,
        would_create=would_create,
        can_confirm=would_create and payload.included_items_confirmed,
    )

    if not payload.confirm:
        return preview
    if not payload.included_items_confirmed:
        raise briefing_generation_validation("포함 항목과 기간을 직접 확인해 주세요.")
    if not would_create:
        raise briefing_generation_validation(
            "새로 생성할 브리핑 항목이 없습니다.",
            status_code=409,
        )

    result = service.generate(
        period_start=payload.period_start,
        period_end=payload.period_end,
        now=now,
        briefing_type=BriefingType.CHANGE_BRIEFING,
        minimum_priority=payload.minimum_priority,
        persist=True,
    )
    return BriefingGenerationConfirmed(
        briefing=_briefing_generation(result.briefing, result.items, service),
        excluded_duplicates=result.excluded_duplicates,
    )


@router.get("/briefings/{briefing_id}", response_model=BriefingRead)
def get_briefing(
    briefing_id: str,
    session: SessionDependency,
) -> BriefingRead:
    service = BriefingService(session)
    return _briefing(service.get(briefing_id), service, with_items=True)


def _preference_response(
    record: NotificationPreferenceRecord | None,
    settings: Settings,
) -> NotificationPreferenceRead:
    return NotificationPreferenceRead(
        configured=settings.email_configured,
        email_provider_status=("READY" if settings.email_configured else "NOT_CONFIGURED"),
        enabled=record.enabled if record else False,
        hourly_change_briefing_enabled=(
            record.hourly_change_briefing_enabled if record else False
        ),
        daily_digest_enabled=record.daily_digest_enabled if record else False,
        krx_pre_open_enabled=record.krx_pre_open_enabled if record else False,
        krx_post_close_enabled=record.krx_post_close_enabled if record else False,
        nasdaq_pre_open_enabled=(record.nasdaq_pre_open_enabled if record else False),
        nasdaq_post_close_enabled=(record.nasdaq_post_close_enabled if record else False),
        immediate_material_change_enabled=(
            record.immediate_material_change_enabled if record else False
        ),
        correction_notice_enabled=(record.correction_notice_enabled if record else True),
        provider_failure_notice_enabled=(
            record.provider_failure_notice_enabled if record else False
        ),
        recipient_email_masked=mask_email(record.recipient_email if record else None),
        timezone=record.timezone if record else "Asia/Seoul",
        daily_digest_hour=record.daily_digest_hour if record else 8,
        minimum_priority=record.minimum_priority if record else 50,
        include_watchlist=record.include_watchlist if record else True,
        include_reentry_watch=(record.include_reentry_watch if record else False),
        include_sold=record.include_sold if record else False,
        include_holdings=True,
        send_no_material_change_briefing=(
            record.send_no_material_change_briefing if record else False
        ),
        krx_pre_open_offset_minutes=(record.krx_pre_open_offset_minutes if record else 40),
        krx_post_close_offset_minutes=(record.krx_post_close_offset_minutes if record else 20),
        nasdaq_pre_open_offset_minutes=(
            record.nasdaq_pre_open_offset_minutes if record else 60
        ),
        nasdaq_post_close_offset_minutes=(
            record.nasdaq_post_close_offset_minutes if record else 20
        ),
        created_at=record.created_at if record else None,
        updated_at=record.updated_at if record else None,
    )


@router.get(
    "/notification-preferences",
    response_model=NotificationPreferenceRead,
)
def get_notification_preferences(
    request: Request,
    session: SessionDependency,
) -> NotificationPreferenceRead:
    return _preference_response(
        session.get(NotificationPreferenceRecord, "default"),
        request.app.state.settings,
    )


@router.put(
    "/notification-preferences",
    response_model=NotificationPreferenceRead,
)
def put_notification_preferences(
    payload: NotificationPreferenceInput,
    request: Request,
    session: SessionDependency,
) -> NotificationPreferenceRead:
    record = session.get(NotificationPreferenceRecord, "default")
    if record is None:
        record = NotificationPreferenceRecord(id="default")
        session.add(record)
    if payload.enabled and not payload.recipient_email and not record.recipient_email:
        raise notification_preference_validation(
            "이메일 알림 사용 시 수신 이메일이 필요합니다."
        )
    for name, value in payload.model_dump().items():
        if name == "recipient_email" and value is None:
            continue
        setattr(record, name, value)
    session.flush()
    return _preference_response(record, request.app.state.settings)
