from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.schemas.analysis import (
    AnalysisPacket,
    DecisionReviewAcknowledge,
    DecisionReviewList,
    DecisionReviewRead,
    DecisionReviewRefresh,
    EconomicEventImportConfirmed,
    EconomicEventImportDuplicate,
    EconomicEventImportPortfolioItem,
    EconomicEventImportPreview,
    EconomicEventImportRequest,
    EconomicEventList,
    EconomicEventRead,
    InvestmentThesisInput,
    InvestmentThesisRead,
    PortfolioImpactList,
    PortfolioImpactRead,
)
from app.services.analysis import AnalysisService

router = APIRouter(tags=["analysis"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _service(session: Session) -> AnalysisService:
    return AnalysisService(session)


@router.get(
    "/api/v1/portfolio/{item_id}/thesis",
    response_model=InvestmentThesisRead,
)
def get_thesis(item_id: UUID, session: SessionDependency) -> InvestmentThesisRead:
    return _service(session).thesis(str(item_id))


@router.put(
    "/api/v1/portfolio/{item_id}/thesis",
    response_model=InvestmentThesisRead,
)
def put_thesis(
    item_id: UUID,
    payload: InvestmentThesisInput,
    session: SessionDependency,
) -> InvestmentThesisRead:
    return InvestmentThesisRead.model_validate(
        _service(session).save_thesis(str(item_id), payload)
    )


@router.get(
    "/api/v1/portfolio/{item_id}/impacts",
    response_model=PortfolioImpactList,
)
def portfolio_impacts(item_id: UUID, session: SessionDependency) -> PortfolioImpactList:
    items = _service(session).impacts(portfolio_item_id=str(item_id))
    return PortfolioImpactList(
        items=[PortfolioImpactRead.model_validate(item) for item in items],
        total=len(items),
    )


@router.get("/api/v1/events/{event_id}/impacts", response_model=PortfolioImpactList)
def event_impacts(event_id: UUID, session: SessionDependency) -> PortfolioImpactList:
    items = _service(session).impacts(event_id=str(event_id))
    return PortfolioImpactList(
        items=[PortfolioImpactRead.model_validate(item) for item in items],
        total=len(items),
    )


@router.get("/api/v1/impacts", response_model=PortfolioImpactList)
def list_impacts(
    session: SessionDependency,
    portfolio_item_id: Annotated[UUID | None, Query(alias="portfolioItemId")] = None,
    event_id: Annotated[UUID | None, Query(alias="eventId")] = None,
) -> PortfolioImpactList:
    items = _service(session).impacts(
        portfolio_item_id=(str(portfolio_item_id) if portfolio_item_id is not None else None),
        event_id=str(event_id) if event_id is not None else None,
    )
    return PortfolioImpactList(
        items=[PortfolioImpactRead.model_validate(item) for item in items],
        total=len(items),
    )


@router.get(
    "/api/v1/portfolio/{item_id}/decision-review",
    response_model=DecisionReviewRead,
)
def get_decision_review(item_id: UUID, session: SessionDependency) -> DecisionReviewRead:
    return _service(session).latest_review(str(item_id))


@router.get("/api/v1/decision-reviews", response_model=DecisionReviewList)
def list_decision_reviews(session: SessionDependency) -> DecisionReviewList:
    items = _service(session).list_reviews()
    return DecisionReviewList(items=items, total=len(items))


@router.post(
    "/api/v1/portfolio/{item_id}/decision-review/refresh",
    response_model=DecisionReviewRead,
)
def refresh_decision_review(
    item_id: UUID,
    payload: DecisionReviewRefresh,
    session: SessionDependency,
) -> DecisionReviewRead:
    record = _service(session).refresh_review(
        str(item_id), manual_reference_price=payload.manual_reference_price
    )
    return DecisionReviewRead.model_validate(record)


@router.post(
    "/api/v1/portfolio/{item_id}/decision-review/acknowledge",
    response_model=DecisionReviewRead,
)
def acknowledge_decision_review(
    item_id: UUID,
    payload: DecisionReviewAcknowledge,
    session: SessionDependency,
) -> DecisionReviewRead:
    return DecisionReviewRead.model_validate(
        _service(session).acknowledge(str(item_id), user_decision=payload.user_decision)
    )


@router.get(
    "/api/v1/portfolio/{item_id}/analysis-packet",
    response_model=AnalysisPacket,
)
def get_analysis_packet(item_id: UUID, session: SessionDependency) -> AnalysisPacket:
    return _service(session).analysis_packet(str(item_id))


@router.get("/api/v1/economic-events", response_model=EconomicEventList)
def economic_events(session: SessionDependency) -> EconomicEventList:
    items = _service(session).economic_events()
    return EconomicEventList(items=items, total=len(items))


@router.get("/api/v1/economic-events/upcoming", response_model=EconomicEventList)
def upcoming_economic_events(session: SessionDependency) -> EconomicEventList:
    items = _service(session).economic_events(upcoming_only=True)
    return EconomicEventList(items=items, total=len(items))


@router.post(
    "/api/v1/economic-events/import-link",
    response_model=EconomicEventImportPreview | EconomicEventImportConfirmed,
)
def import_economic_event(
    payload: EconomicEventImportRequest,
    session: SessionDependency,
) -> EconomicEventImportPreview | EconomicEventImportConfirmed:
    service = _service(session)
    plan = service.plan_economic_event_import(payload)
    portfolio_items = [
        EconomicEventImportPortfolioItem(
            id=item.id,
            symbol=item.symbol,
            name=item.name,
            market=item.market,
        )
        for item in plan.portfolio_items
    ]
    duplicate = EconomicEventImportDuplicate(
        duplicate=plan.duplicate is not None,
        existing_event_id=(plan.duplicate.id if plan.duplicate is not None else None),
    )

    if not payload.confirm:
        return EconomicEventImportPreview(
            normalized_url=plan.canonical_url,
            source_domain=plan.source_domain,
            scheduled_at=payload.scheduled_at,
            portfolio_items=portfolio_items,
            duplicate=duplicate,
            official_source_confirmed=plan.official_source_confirmed,
            validation_warnings=list(plan.validation_warnings),
            would_create=plan.would_create,
            can_confirm=plan.can_confirm,
        )

    if not plan.official_source_confirmed:
        raise HTTPException(
            status_code=422,
            detail="공식 원문과 발표 예정 시각 확인이 필요합니다.",
        )
    if plan.duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail="이미 등록된 경제·기업 일정입니다.",
        )

    record = service.create_economic_event(payload, plan)
    return EconomicEventImportConfirmed(
        event=EconomicEventRead.model_validate(record),
        portfolio_items=portfolio_items,
        validation_warnings=list(plan.validation_warnings),
    )
