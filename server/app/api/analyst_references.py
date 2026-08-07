from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystPublisherType,
    AnalystReferenceRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.repositories.analyst_references import (
    MAX_ANALYST_REFERENCE_LIMIT,
    AnalystReferenceRepository,
)
from app.repositories.reference_discovery_candidates import (
    MAX_REFERENCE_DISCOVERY_CANDIDATE_LIMIT,
)
from app.repositories.reference_subscriptions import (
    MAX_REFERENCE_SUBSCRIPTION_LIMIT,
    ReferenceSubscriptionRepository,
)
from app.schemas.analyst_references import (
    AnalystReferenceCoverageRead,
    AnalystReferenceImportLinkConfirmed,
    AnalystReferenceImportLinkPreview,
    AnalystReferenceImportLinkRequest,
    AnalystReferenceList,
    AnalystReferenceRead,
)
from app.schemas.reference_discovery_candidate_review import (
    ReferenceDiscoveryCandidateDismissRequest,
    ReferenceDiscoveryCandidatePromoteRequest,
    ReferenceDiscoveryCandidateReviewHistoryList,
    ReferenceDiscoveryCandidateReviewResult,
    ReferenceDiscoveryCandidateVerifyDateRequest,
)
from app.schemas.reference_discovery_candidates import (
    ReferenceDiscoveryCandidateList,
    ReferenceDiscoveryCandidateRead,
)
from app.schemas.reference_source_history import (
    ReferenceSourceChangeList,
    ReferenceSourceChangeRead,
)
from app.schemas.reference_source_management import (
    ReferenceSourceImportConfirmed,
    ReferenceSourceImportPreview,
    ReferenceSourceImportRequest,
    ReferenceSourceList,
    ReferenceSourceRead,
    ReferenceSourceUpdateRequest,
)
from app.schemas.reference_subscriptions import (
    ReferenceSubscriptionImportConfirmed,
    ReferenceSubscriptionImportPreview,
    ReferenceSubscriptionImportRequest,
    ReferenceSubscriptionList,
    ReferenceSubscriptionRead,
    ReferenceSubscriptionSourceList,
    ReferenceSubscriptionSourceRead,
    ReferenceSubscriptionUpdateRequest,
)
from app.services.analyst_references import (
    AnalystReferenceImportBlockedError,
    AnalystReferenceImportService,
)
from app.services.reference_discovery_candidate_review import (
    MAX_REFERENCE_DISCOVERY_CANDIDATE_HISTORY_LIMIT,
    ReferenceDiscoveryCandidateReviewError,
    ReferenceDiscoveryCandidateReviewNotFoundError,
    ReferenceDiscoveryCandidateReviewService,
)
from app.services.reference_discovery_candidates import (
    ReferenceDiscoveryCandidateReadService,
)
from app.services.reference_source_history_read import (
    MAX_REFERENCE_SOURCE_HISTORY_LIMIT,
    ReferenceSourceHistoryReadService,
)
from app.services.reference_source_management import (
    ReferenceSourceImportBlockedError,
    ReferenceSourceManagementService,
    ReferenceSourceUpdateConflictError,
    ReferenceSourceUpdateError,
)
from app.services.reference_subscriptions import (
    ReferenceSubscriptionImportBlockedError,
    ReferenceSubscriptionImportService,
    ReferenceSubscriptionManagementService,
    ReferenceSubscriptionUpdateConflictError,
    ReferenceSubscriptionUpdateError,
)

router = APIRouter(
    prefix="/api/v1/analyst-references",
    tags=["analyst-references"],
)

SessionDependency = Annotated[
    Session,
    Depends(get_session),
]


def analyst_reference_read(
    repository: AnalystReferenceRepository,
    record: AnalystReferenceRecord,
) -> AnalystReferenceRead:
    value = AnalystReferenceRead.model_validate(record)

    coverages = [
        AnalystReferenceCoverageRead.model_validate(coverage)
        for coverage in repository.coverages(record.id)
    ]

    return value.model_copy(
        update={
            "coverages": coverages,
        }
    )


@router.get(
    "",
    response_model=AnalystReferenceList,
)
def list_analyst_references(
    session: SessionDependency,
    portfolio_item_id: Annotated[
        UUID | None,
        Query(alias="portfolioItemId"),
    ] = None,
    publisher_type: Annotated[
        AnalystPublisherType | None,
        Query(alias="publisherType"),
    ] = None,
    access_type: Annotated[
        AnalystAccessType | None,
        Query(alias="accessType"),
    ] = None,
    document_type: Annotated[
        AnalystDocumentType | None,
        Query(alias="documentType"),
    ] = None,
    freshness_status: Annotated[
        AnalystFreshnessStatus | None,
        Query(alias="freshnessStatus"),
    ] = None,
    include_inactive: Annotated[
        bool,
        Query(alias="includeInactive"),
    ] = False,
    query: str | None = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_ANALYST_REFERENCE_LIMIT,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> AnalystReferenceList:
    repository = AnalystReferenceRepository(session)

    rows, total = repository.list(
        portfolio_item_id=(str(portfolio_item_id) if portfolio_item_id is not None else None),
        publisher_type=publisher_type,
        access_type=access_type,
        document_type=document_type,
        freshness_status=freshness_status,
        include_inactive=include_inactive,
        query=query,
        limit=limit,
        offset=offset,
    )

    return AnalystReferenceList(
        items=[analyst_reference_read(repository, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/portfolio/{portfolio_item_id}",
    response_model=AnalystReferenceList,
)
def portfolio_analyst_references(
    portfolio_item_id: UUID,
    session: SessionDependency,
    include_inactive: Annotated[
        bool,
        Query(alias="includeInactive"),
    ] = False,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_ANALYST_REFERENCE_LIMIT,
        ),
    ] = 5,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> AnalystReferenceList:
    repository = AnalystReferenceRepository(session)

    rows, total = repository.list(
        portfolio_item_id=str(portfolio_item_id),
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )

    return AnalystReferenceList(
        items=[analyst_reference_read(repository, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/import-link",
    response_model=(AnalystReferenceImportLinkPreview | AnalystReferenceImportLinkConfirmed),
)
def import_analyst_reference_link(
    payload: AnalystReferenceImportLinkRequest,
    response: Response,
    session: SessionDependency,
) -> AnalystReferenceImportLinkPreview | AnalystReferenceImportLinkConfirmed:
    service = AnalystReferenceImportService(session)

    if not payload.confirm:
        return service.preview(payload)

    try:
        result = service.confirm(payload)
    except AnalystReferenceImportBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ANALYST_REFERENCE_IMPORT_BLOCKED",
                "message": str(exc),
                "preview": exc.preview.model_dump(
                    mode="json",
                    by_alias=True,
                ),
            },
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ANALYST_REFERENCE_DUPLICATE",
                "message": ("The analyst reference conflicts with an existing record."),
            },
        ) from exc

    response.status_code = status.HTTP_201_CREATED
    return result


def reference_subscription_read(
    repository: ReferenceSubscriptionRepository,
    record: ReferenceSubscriptionRecord,
) -> ReferenceSubscriptionRead:
    source = repository.source_for(record.source_id)

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reference subscription source was not found.",
        )

    return ReferenceSubscriptionRead(
        id=record.id,
        source_id=record.source_id,
        subject_type=record.subject_type,
        display_name=record.display_name,
        match_mode=record.match_mode,
        match_terms=record.match_terms,
        enabled=record.enabled,
        created_at=record.created_at,
        updated_at=record.updated_at,
        automatic_reference_count=(repository.automatic_reference_count(record.id)),
        source=(ReferenceSubscriptionSourceRead.model_validate(source)),
    )


@router.get(
    "/subscriptions/source-management",
    response_model=ReferenceSourceList,
)
def list_reference_sources_for_management(
    session: SessionDependency,
    query: str | None = None,
    official: bool | None = None,
    enabled: bool | None = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_REFERENCE_SUBSCRIPTION_LIMIT,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> ReferenceSourceList:
    return ReferenceSourceManagementService(session).list(
        query=query,
        official=official,
        enabled=enabled,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/subscriptions/source-management/{source_id}",
    response_model=ReferenceSourceRead,
)
def get_reference_source_for_management(
    source_id: UUID,
    session: SessionDependency,
) -> ReferenceSourceRead:
    source = ReferenceSourceManagementService(session).get(str(source_id))

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REFERENCE_SOURCE_NOT_FOUND",
                "message": ("Reference source was not found."),
            },
        )

    return source


@router.get(
    ("/subscriptions/source-management/{source_id}/history"),
    response_model=ReferenceSourceChangeList,
)
def list_reference_source_change_history(
    source_id: UUID,
    session: SessionDependency,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_REFERENCE_SOURCE_HISTORY_LIMIT,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> ReferenceSourceChangeList:
    result = ReferenceSourceHistoryReadService(session).list(
        str(source_id),
        limit=limit,
        offset=offset,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ("REFERENCE_SOURCE_NOT_FOUND"),
                "message": ("Reference source was not found."),
            },
        )

    rows, total = result

    return ReferenceSourceChangeList(
        items=[ReferenceSourceChangeRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/subscriptions/source-management/import",
    response_model=(ReferenceSourceImportPreview | ReferenceSourceImportConfirmed),
)
def import_reference_source_for_management(
    payload: ReferenceSourceImportRequest,
    session: SessionDependency,
    response: Response,
) -> ReferenceSourceImportPreview | ReferenceSourceImportConfirmed:
    service = ReferenceSourceManagementService(session)

    if not payload.confirm:
        return service.preview(payload)

    try:
        result = service.confirm(payload)
    except ReferenceSourceImportBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ("REFERENCE_SOURCE_IMPORT_BLOCKED"),
                "message": str(exc),
                "preview": exc.preview.model_dump(
                    mode="json",
                    by_alias=True,
                ),
            },
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ("REFERENCE_SOURCE_DUPLICATE"),
                "message": ("The reference source conflicts with an existing source."),
            },
        ) from exc

    response.status_code = status.HTTP_201_CREATED
    return result


@router.patch(
    "/subscriptions/source-management/{source_id}",
    response_model=ReferenceSourceRead,
)
def update_reference_source_for_management(
    source_id: UUID,
    payload: ReferenceSourceUpdateRequest,
    session: SessionDependency,
) -> ReferenceSourceRead:
    service = ReferenceSourceManagementService(session)

    try:
        source = service.update(
            str(source_id),
            payload,
        )
    except ReferenceSourceUpdateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc
    except ReferenceSourceUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ("REFERENCE_SOURCE_UPDATE_INVALID"),
                "message": str(exc),
            },
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ("REFERENCE_SOURCE_DUPLICATE"),
                "message": ("The reference source conflicts with an existing source."),
            },
        ) from exc

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REFERENCE_SOURCE_NOT_FOUND",
                "message": ("Reference source was not found."),
            },
        )

    return source


@router.get(
    "/subscriptions/sources",
    response_model=ReferenceSubscriptionSourceList,
)
def list_reference_subscription_sources(
    session: SessionDependency,
    query: str | None = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_REFERENCE_SUBSCRIPTION_LIMIT,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> ReferenceSubscriptionSourceList:
    repository = ReferenceSubscriptionRepository(session)

    rows, total = repository.list_sources(
        query=query,
        limit=limit,
        offset=offset,
    )

    return ReferenceSubscriptionSourceList(
        items=[ReferenceSubscriptionSourceRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/subscriptions",
    response_model=ReferenceSubscriptionList,
)
def list_reference_subscriptions(
    session: SessionDependency,
    subject_type: Annotated[
        ReferenceSubjectType | None,
        Query(alias="subjectType"),
    ] = None,
    match_mode: Annotated[
        ReferenceMatchMode | None,
        Query(alias="matchMode"),
    ] = None,
    enabled: bool | None = None,
    query: str | None = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_REFERENCE_SUBSCRIPTION_LIMIT,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> ReferenceSubscriptionList:
    repository = ReferenceSubscriptionRepository(session)

    rows, total = repository.list(
        subject_type=subject_type,
        match_mode=match_mode,
        enabled=enabled,
        query=query,
        limit=limit,
        offset=offset,
    )

    return ReferenceSubscriptionList(
        items=[
            reference_subscription_read(
                repository,
                row,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/subscriptions/import",
    response_model=(ReferenceSubscriptionImportPreview | ReferenceSubscriptionImportConfirmed),
)
def import_reference_subscription(
    payload: ReferenceSubscriptionImportRequest,
    session: SessionDependency,
    response: Response,
) -> ReferenceSubscriptionImportPreview | ReferenceSubscriptionImportConfirmed:
    service = ReferenceSubscriptionImportService(session)

    if not payload.confirm:
        return service.preview(payload)

    try:
        result = service.confirm(payload)
    except ReferenceSubscriptionImportBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.preview.model_dump(
                by_alias=True,
                mode="json",
            ),
        ) from exc

    response.status_code = status.HTTP_201_CREATED
    return result


@router.patch(
    "/subscriptions/{subscription_id}",
    response_model=ReferenceSubscriptionRead,
)
def update_reference_subscription(
    subscription_id: UUID,
    payload: ReferenceSubscriptionUpdateRequest,
    session: SessionDependency,
) -> ReferenceSubscriptionRead:
    service = ReferenceSubscriptionManagementService(session)

    try:
        record = service.update(
            str(subscription_id),
            payload,
        )
    except ReferenceSubscriptionUpdateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ReferenceSubscriptionUpdateError as exc:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY),
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Reference subscription update conflicts with an existing record."),
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("Reference subscription was not found."),
        )

    repository = ReferenceSubscriptionRepository(session)

    return reference_subscription_read(
        repository,
        record,
    )


@router.get(
    "/subscriptions/{subscription_id}",
    response_model=ReferenceSubscriptionRead,
)
def get_reference_subscription(
    subscription_id: UUID,
    session: SessionDependency,
) -> ReferenceSubscriptionRead:
    repository = ReferenceSubscriptionRepository(session)

    record = repository.get(str(subscription_id))

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("Reference subscription was not found."),
        )

    return reference_subscription_read(
        repository,
        record,
    )


@router.get(
    "/discovery-candidates",
    response_model=ReferenceDiscoveryCandidateList,
)
def list_reference_discovery_candidates(
    session: SessionDependency,
    source_id: Annotated[
        UUID | None,
        Query(alias="sourceId"),
    ] = None,
    subscription_id: Annotated[
        UUID | None,
        Query(alias="subscriptionId"),
    ] = None,
    verification_status: Annotated[
        ReferenceDiscoveryCandidateStatus | None,
        Query(alias="verificationStatus"),
    ] = None,
    query: str | None = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_REFERENCE_DISCOVERY_CANDIDATE_LIMIT,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> ReferenceDiscoveryCandidateList:
    return ReferenceDiscoveryCandidateReadService(session).list(
        source_id=(str(source_id) if source_id is not None else None),
        subscription_id=(str(subscription_id) if subscription_id is not None else None),
        verification_status=verification_status,
        query=query,
        limit=limit,
        offset=offset,
    )


def _raise_candidate_review_error(
    error: ReferenceDiscoveryCandidateReviewError,
) -> None:
    status_code = status.HTTP_409_CONFLICT

    if isinstance(
        error,
        ReferenceDiscoveryCandidateReviewNotFoundError,
    ):
        status_code = status.HTTP_404_NOT_FOUND

    detail: dict[str, object] = {
        "code": error.code,
        "message": error.message,
    }

    if error.reason is not None:
        detail["reason"] = error.reason

    raise HTTPException(
        status_code=status_code,
        detail=detail,
    )


@router.post(
    "/discovery-candidates/{candidate_id}/verify-date",
    response_model=(ReferenceDiscoveryCandidateReviewResult),
)
def verify_reference_discovery_candidate_date(
    candidate_id: UUID,
    payload: (ReferenceDiscoveryCandidateVerifyDateRequest),
    session: SessionDependency,
) -> ReferenceDiscoveryCandidateReviewResult:
    try:
        return ReferenceDiscoveryCandidateReviewService(session).verify_date(
            str(candidate_id),
            payload,
        )
    except ReferenceDiscoveryCandidateReviewError as error:
        _raise_candidate_review_error(error)
        raise


@router.post(
    "/discovery-candidates/{candidate_id}/promote",
    response_model=(ReferenceDiscoveryCandidateReviewResult),
)
def promote_reference_discovery_candidate(
    candidate_id: UUID,
    payload: (ReferenceDiscoveryCandidatePromoteRequest),
    session: SessionDependency,
) -> ReferenceDiscoveryCandidateReviewResult:
    try:
        return ReferenceDiscoveryCandidateReviewService(session).promote(
            str(candidate_id),
            payload,
        )
    except ReferenceDiscoveryCandidateReviewError as error:
        _raise_candidate_review_error(error)
        raise


@router.post(
    "/discovery-candidates/{candidate_id}/dismiss",
    response_model=(ReferenceDiscoveryCandidateReviewResult),
)
def dismiss_reference_discovery_candidate(
    candidate_id: UUID,
    payload: (ReferenceDiscoveryCandidateDismissRequest),
    session: SessionDependency,
) -> ReferenceDiscoveryCandidateReviewResult:
    try:
        return ReferenceDiscoveryCandidateReviewService(session).dismiss(
            str(candidate_id),
            payload,
        )
    except ReferenceDiscoveryCandidateReviewError as error:
        _raise_candidate_review_error(error)
        raise


@router.get(
    ("/discovery-candidates/{candidate_id}/review-history"),
    response_model=(ReferenceDiscoveryCandidateReviewHistoryList),
)
def list_reference_discovery_candidate_history(
    candidate_id: UUID,
    session: SessionDependency,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=(MAX_REFERENCE_DISCOVERY_CANDIDATE_HISTORY_LIMIT),
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> ReferenceDiscoveryCandidateReviewHistoryList:
    try:
        return ReferenceDiscoveryCandidateReviewService(session).history(
            str(candidate_id),
            limit=limit,
            offset=offset,
        )
    except ReferenceDiscoveryCandidateReviewError as error:
        _raise_candidate_review_error(error)
        raise


@router.get(
    "/discovery-candidates/{candidate_id}",
    response_model=ReferenceDiscoveryCandidateRead,
)
def get_reference_discovery_candidate(
    candidate_id: UUID,
    session: SessionDependency,
) -> ReferenceDiscoveryCandidateRead:
    candidate = ReferenceDiscoveryCandidateReadService(session).get(str(candidate_id))

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ("REFERENCE_DISCOVERY_CANDIDATE_NOT_FOUND"),
                "message": ("Reference discovery candidate was not found."),
            },
        )

    return candidate


@router.get(
    "/{reference_id}",
    response_model=AnalystReferenceRead,
)
def get_analyst_reference(
    reference_id: UUID,
    session: SessionDependency,
) -> AnalystReferenceRead:
    repository = AnalystReferenceRepository(session)
    record = repository.get(str(reference_id))

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analyst reference was not found.",
        )

    return analyst_reference_read(
        repository,
        record,
    )
