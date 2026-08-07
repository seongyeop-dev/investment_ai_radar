from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.contracts import VerificationStatus
from app.models.database import SourceGrade
from app.models.disclosures import (
    DisclosureRecord,
    InstrumentRecord,
    LifecycleStatus,
    NewsReferenceRecord,
)
from app.repositories.news import MAX_NEWS_LIMIT, NewsRepository
from app.schemas.instruments import InstrumentSummary
from app.schemas.news import (
    ImportantInformationImportClassification,
    ImportantInformationImportConfirmed,
    ImportantInformationImportDuplicate,
    ImportantInformationImportPortfolioItem,
    ImportantInformationImportPreview,
    ImportantInformationImportRequest,
    NewsList,
    NewsRead,
    OfficialNewsReference,
)
from app.services.news import ImportantInformationImportService, NewsService

router = APIRouter(prefix="/api/v1/news", tags=["news-references"])
SessionDependency = Annotated[Session, Depends(get_session)]


def news_read(session: Session, record: NewsReferenceRecord) -> NewsRead:
    value = NewsRead.model_validate(record)
    instrument = session.get(InstrumentRecord, record.instrument_id)
    official = [
        disclosure
        for disclosure_id in record.official_reference_ids
        if (disclosure := session.get(DisclosureRecord, disclosure_id)) is not None
    ]
    return value.model_copy(
        update={
            "related_instrument": (
                InstrumentSummary.model_validate(instrument) if instrument else None
            ),
            "official_references": [
                OfficialNewsReference(
                    id=disclosure.id,
                    title=disclosure.title,
                    official_url=disclosure.official_url,
                    provider=disclosure.provider.value,
                )
                for disclosure in official
            ],
        }
    )


@router.get("", response_model=NewsList)
def list_news(
    session: SessionDependency,
    instrument_id: Annotated[UUID | None, Query(alias="instrumentId")] = None,
    portfolio_item_id: Annotated[UUID | None, Query(alias="portfolioItemId")] = None,
    source_grade: Annotated[SourceGrade | None, Query(alias="sourceGrade")] = None,
    verification_status: Annotated[
        VerificationStatus | None, Query(alias="verificationStatus")
    ] = None,
    lifecycle_status: Annotated[LifecycleStatus | None, Query(alias="lifecycleStatus")] = None,
    material_change: Annotated[bool | None, Query(alias="materialChange")] = None,
    stale_reused: Annotated[bool | None, Query(alias="staleReused")] = None,
    published_from: Annotated[datetime | None, Query(alias="publishedFrom")] = None,
    published_to: Annotated[datetime | None, Query(alias="publishedTo")] = None,
    query: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_NEWS_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NewsList:
    rows, total = NewsRepository(session).list(
        instrument_id=str(instrument_id) if instrument_id else None,
        portfolio_item_id=str(portfolio_item_id) if portfolio_item_id else None,
        source_grade=source_grade,
        verification_status=verification_status,
        lifecycle_status=lifecycle_status,
        material_change=material_change,
        stale_reused=stale_reused,
        published_from=published_from,
        published_to=published_to,
        query=query,
        limit=limit,
        offset=offset,
    )
    return NewsList(
        items=[news_read(session, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/import-link",
    response_model=(ImportantInformationImportPreview | ImportantInformationImportConfirmed),
)
def import_important_information(
    payload: ImportantInformationImportRequest,
    session: SessionDependency,
) -> ImportantInformationImportPreview | ImportantInformationImportConfirmed:
    service = ImportantInformationImportService(session)
    try:
        plan = service.preview(
            source_url=payload.source_url,
            publisher_name=payload.publisher_name,
            portfolio_item_id=str(payload.portfolio_item_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    preview = ImportantInformationImportPreview(
        normalized_url=plan.canonical_url,
        portfolio_item=ImportantInformationImportPortfolioItem.model_validate(
            plan.portfolio_item
        ),
        duplicate=ImportantInformationImportDuplicate(
            duplicate=plan.duplicate is not None,
            existing_reference_id=(plan.duplicate.id if plan.duplicate is not None else None),
        ),
        classification=ImportantInformationImportClassification(
            source_name=payload.publisher_name,
            source_domain=plan.source_domain,
            source_grade=plan.source_grade,
            official_source=plan.official_source,
            predicted_verification_status=(
                VerificationStatus.OFFICIAL_CONFIRMED
                if plan.official_source
                else VerificationStatus.NEEDS_VERIFICATION
            ),
        ),
        would_create_source=plan.would_create_source,
        would_create_instrument=plan.would_create_instrument,
        validation_warnings=list(plan.validation_warnings),
        would_create=plan.duplicate is None,
    )
    if not payload.confirm:
        return preview
    if not preview.would_create:
        raise HTTPException(
            status_code=409,
            detail="동일한 공개 링크로 등록된 중요 정보가 이미 있습니다.",
        )

    try:
        result = service.confirm(
            source_url=payload.source_url,
            publisher_name=payload.publisher_name,
            title=payload.title,
            published_at=payload.published_at,
            primary_claim=payload.primary_claim,
            public_summary=payload.public_summary,
            portfolio_item_id=str(payload.portfolio_item_id),
            language=payload.language,
            material_change=payload.material_change,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ImportantInformationImportConfirmed(
        normalized_url=plan.canonical_url,
        reference=news_read(session, result.ingest.reference),
        information_event_id=result.ingest.event.id,
        source_created=result.source_created,
        instrument_created=result.instrument_created,
        validation_warnings=list(result.validation_warnings),
    )


@router.get("/{reference_id}", response_model=NewsRead)
def get_news(reference_id: UUID, session: SessionDependency) -> NewsRead:
    return news_read(session, NewsService(session).get(str(reference_id)))
