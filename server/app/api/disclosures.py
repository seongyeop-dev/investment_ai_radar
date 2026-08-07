from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.contracts import VerificationStatus
from app.models.database import PortfolioItemRecord, SourceGrade
from app.models.disclosures import (
    DisclosureRecord,
    InstrumentRecord,
    LifecycleStatus,
    NewsReferenceRecord,
    ProviderName,
)
from app.repositories.disclosures import MAX_DISCLOSURE_LIMIT, DisclosureRepository
from app.schemas.disclosures import (
    DisclosureList,
    DisclosureRead,
    InformationEventDetail,
    InformationEventList,
    InformationEventRead,
    OfficialDisclosureImportClassification,
    OfficialDisclosureImportConfirmed,
    OfficialDisclosureImportDuplicate,
    OfficialDisclosureImportPortfolioItem,
    OfficialDisclosureImportPreview,
    OfficialDisclosureImportRequest,
    PortfolioDisclosureReference,
)
from app.schemas.instruments import InstrumentSummary
from app.services.disclosures import DisclosureService, canonical_official_url

router = APIRouter(prefix="/api/v1", tags=["official-disclosures"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _disclosure_read(session: Session, record: DisclosureRecord) -> DisclosureRead:
    value = DisclosureRead.model_validate(record)
    instrument = session.get(InstrumentRecord, record.instrument_id)
    portfolios = (
        list(
            session.scalars(
                select(PortfolioItemRecord).where(
                    PortfolioItemRecord.archived_at.is_(None),
                    or_(
                        PortfolioItemRecord.instrument_id == record.instrument_id,
                        (
                            PortfolioItemRecord.instrument_id.is_(None)
                            & (PortfolioItemRecord.market == instrument.market)
                            & (PortfolioItemRecord.symbol == instrument.canonical_symbol)
                        ),
                    ),
                )
            )
        )
        if instrument
        else []
    )
    return value.model_copy(
        update={
            "related_instrument": (
                InstrumentSummary.model_validate(instrument) if instrument else None
            ),
            "related_portfolio_items": [
                PortfolioDisclosureReference.model_validate(item) for item in portfolios
            ],
        }
    )


@router.get("/disclosures", response_model=DisclosureList)
def list_disclosures(
    session: SessionDependency,
    instrument_id: Annotated[UUID | None, Query(alias="instrumentId")] = None,
    portfolio_item_id: Annotated[UUID | None, Query(alias="portfolioItemId")] = None,
    provider: ProviderName | None = None,
    form_type: Annotated[str | None, Query(alias="formType")] = None,
    verification_status: Annotated[
        VerificationStatus | None, Query(alias="verificationStatus")
    ] = None,
    lifecycle_status: Annotated[LifecycleStatus | None, Query(alias="lifecycleStatus")] = None,
    material_change: Annotated[bool | None, Query(alias="materialChange")] = None,
    published_from: Annotated[datetime | None, Query(alias="publishedFrom")] = None,
    published_to: Annotated[datetime | None, Query(alias="publishedTo")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_DISCLOSURE_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DisclosureList:
    rows, total = DisclosureRepository(session).list_disclosures(
        instrument_id=str(instrument_id) if instrument_id else None,
        portfolio_item_id=str(portfolio_item_id) if portfolio_item_id else None,
        provider=provider,
        form_type=form_type,
        verification_status=verification_status,
        lifecycle_status=lifecycle_status,
        material_change=material_change,
        published_from=published_from,
        published_to=published_to,
        limit=limit,
        offset=offset,
    )
    return DisclosureList(
        items=[_disclosure_read(session, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/disclosures/import-link",
    response_model=(OfficialDisclosureImportPreview | OfficialDisclosureImportConfirmed),
)
def import_official_disclosure(
    payload: OfficialDisclosureImportRequest,
    session: SessionDependency,
) -> OfficialDisclosureImportPreview | OfficialDisclosureImportConfirmed:
    service = DisclosureService(DisclosureRepository(session))
    try:
        plan = service.preview_import(
            official_url=payload.official_url,
            portfolio_item_id=str(payload.portfolio_item_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    preview = OfficialDisclosureImportPreview(
        normalized_url=plan.canonical_url,
        provider_document_id=plan.provider_document_id,
        portfolio_item=OfficialDisclosureImportPortfolioItem.model_validate(
            plan.portfolio_item
        ),
        duplicate=OfficialDisclosureImportDuplicate(
            duplicate=plan.duplicate is not None,
            existing_disclosure_id=(plan.duplicate.id if plan.duplicate is not None else None),
        ),
        classification=OfficialDisclosureImportClassification(
            provider=plan.provider,
            provider_label=(
                "미국 SEC" if plan.provider is ProviderName.SEC_EDGAR else "국내 OpenDART"
            ),
            source_grade=SourceGrade.A,
            predicted_verification_status=VerificationStatus.OFFICIAL_CONFIRMED,
        ),
        would_create_instrument=plan.would_create_instrument,
        validation_warnings=list(plan.validation_warnings),
        would_create=plan.duplicate is None,
    )
    if not payload.confirm:
        return preview
    if not preview.would_create:
        raise HTTPException(
            status_code=409,
            detail="동일한 공식 공시가 이미 등록되어 있습니다.",
        )

    try:
        result = service.confirm_import(
            official_url=payload.official_url,
            title=payload.title,
            published_at=payload.published_at,
            claim=payload.claim,
            summary=payload.summary,
            portfolio_item_id=str(payload.portfolio_item_id),
            form_type=payload.form_type,
            material_change=payload.material_change,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return OfficialDisclosureImportConfirmed(
        normalized_url=plan.canonical_url,
        disclosure=_disclosure_read(session, result.disclosure),
        information_event_id=result.event.id,
        instrument_created=result.instrument_created,
        validation_warnings=list(result.validation_warnings),
    )


@router.get("/disclosures/{record_id}", response_model=DisclosureRead)
def get_disclosure(record_id: UUID, session: SessionDependency) -> DisclosureRead:
    record = DisclosureService(DisclosureRepository(session)).get_disclosure(str(record_id))
    return _disclosure_read(session, record)


@router.get("/information-events", response_model=InformationEventList)
def list_information_events(
    session: SessionDependency,
    instrument_id: Annotated[UUID | None, Query(alias="instrumentId")] = None,
    event_type: Annotated[str | None, Query(alias="eventType")] = None,
    verification_status: Annotated[
        VerificationStatus | None, Query(alias="verificationStatus")
    ] = None,
    lifecycle_status: Annotated[LifecycleStatus | None, Query(alias="lifecycleStatus")] = None,
    material_change_only: Annotated[bool, Query(alias="materialChangeOnly")] = False,
    first_seen_from: Annotated[datetime | None, Query(alias="firstSeenFrom")] = None,
    last_seen_to: Annotated[datetime | None, Query(alias="lastSeenTo")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_DISCLOSURE_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InformationEventList:
    rows, total = DisclosureRepository(session).list_events(
        instrument_id=str(instrument_id) if instrument_id else None,
        event_type=event_type,
        verification_status=verification_status,
        lifecycle_status=lifecycle_status,
        material_change_only=material_change_only,
        first_seen_from=first_seen_from,
        last_seen_to=last_seen_to,
        limit=limit,
        offset=offset,
    )
    return InformationEventList(
        items=[InformationEventRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/information-events/{event_id}", response_model=InformationEventDetail)
def get_information_event(event_id: UUID, session: SessionDependency) -> InformationEventDetail:
    record = DisclosureService(DisclosureRepository(session)).get_event(str(event_id))
    instrument = session.get(InstrumentRecord, record.instrument_id)
    disclosures = list(
        session.scalars(
            select(DisclosureRecord)
            .where(DisclosureRecord.event_id == record.id)
            .order_by(DisclosureRecord.published_at.asc())
        )
    )
    news = list(
        session.scalars(
            select(NewsReferenceRecord)
            .where(NewsReferenceRecord.information_event_id == record.id)
            .order_by(NewsReferenceRecord.published_at.asc())
        )
    )
    unique_disclosures: list[DisclosureRecord] = []
    seen_disclosures: set[str] = set()
    seen_urls: set[str] = set()
    for disclosure in disclosures:
        document_key = (
            disclosure.receipt_number
            or disclosure.accession_number
            or disclosure.provider_document_id
            or disclosure.id
        )
        canonical_url = canonical_official_url(disclosure.official_url)
        if document_key in seen_disclosures or canonical_url in seen_urls:
            continue
        seen_disclosures.add(document_key)
        seen_urls.add(canonical_url)
        unique_disclosures.append(disclosure)
    return InformationEventDetail(
        **InformationEventRead.model_validate(record).model_dump(),
        related_instrument=(
            InstrumentSummary.model_validate(instrument) if instrument else None
        ),
        official_references=[
            _disclosure_read(session, disclosure) for disclosure in unique_disclosures
        ],
        news_references=news,
    )
