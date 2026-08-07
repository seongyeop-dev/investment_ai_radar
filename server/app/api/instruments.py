from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.disclosures import AssetType
from app.repositories.instruments import MAX_INSTRUMENT_LIMIT, InstrumentRepository
from app.repositories.portfolio import PortfolioRepository
from app.schemas.instruments import (
    InstrumentMappingInput,
    InstrumentRead,
    InstrumentSearchResponse,
)
from app.services.instruments import InstrumentService

router = APIRouter(prefix="/api/v1", tags=["instruments"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _read(service: InstrumentService, record: object) -> InstrumentRead:
    values = InstrumentRead.model_validate(record)
    return values.model_copy(
        update={"available_providers": service.available_providers(str(values.id))}
    )


@router.get("/instruments/search", response_model=InstrumentSearchResponse)
def search_instruments(
    session: SessionDependency,
    query: str | None = None,
    market: str | None = None,
    country: str | None = None,
    asset_type: Annotated[AssetType | None, Query(alias="assetType")] = None,
    verified_only: Annotated[bool, Query(alias="verifiedOnly")] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_INSTRUMENT_LIMIT)] = 50,
) -> InstrumentSearchResponse:
    repository = InstrumentRepository(session)
    service = InstrumentService(repository)
    items, total = repository.search(
        query=query,
        market=market,
        country=country,
        asset_type=asset_type,
        verified_only=verified_only,
        limit=limit,
    )
    return InstrumentSearchResponse(
        items=[_read(service, item) for item in items], total=total, limit=limit
    )


@router.get("/instruments/{instrument_id}", response_model=InstrumentRead)
def get_instrument(instrument_id: UUID, session: SessionDependency) -> InstrumentRead:
    service = InstrumentService(InstrumentRepository(session))
    return _read(service, service.get(str(instrument_id)))


@router.post("/portfolio/{portfolio_id}/instrument", response_model=dict)
def map_instrument(
    portfolio_id: UUID,
    payload: InstrumentMappingInput,
    session: SessionDependency,
) -> dict[str, object]:
    service = InstrumentService(InstrumentRepository(session), PortfolioRepository(session))
    item = service.map_portfolio(str(portfolio_id), str(payload.instrument_id))
    instrument = service.get(str(payload.instrument_id))
    return {
        "portfolioId": item.id,
        "instrumentId": item.instrument_id,
        "instrumentVerificationStatus": instrument.verification_status,
    }


@router.delete(
    "/portfolio/{portfolio_id}/instrument",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unmap_instrument(portfolio_id: UUID, session: SessionDependency) -> Response:
    service = InstrumentService(InstrumentRepository(session), PortfolioRepository(session))
    service.unmap_portfolio(str(portfolio_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
