from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.core.errors import (
    portfolio_not_holding,
    sale_already_voided,
    sale_quantity_exceeds_holding,
    sale_quantity_immutable,
    sale_validation,
    sale_void_not_latest,
)
from app.core.time import SystemClock, require_aware_utc
from app.models.analysis import InvestmentThesisRecord, ThesisStatus
from app.models.database import (
    HoldingStatus,
    PortfolioItemRecord,
    PositionStatus,
    SaleTransactionType,
    TrackingStatus,
)
from app.models.disclosures import InstrumentVerificationStatus, ProviderName
from app.repositories.instruments import InstrumentRepository
from app.repositories.portfolio import MAX_LIST_LIMIT, PortfolioRepository
from app.repositories.sales import SaleRepository
from app.schemas.errors import ErrorResponse
from app.schemas.portfolio import (
    PortfolioContextUpdate,
    PortfolioCreate,
    PortfolioList,
    PortfolioRead,
    PortfolioSummary,
    PortfolioUpdate,
)
from app.schemas.sales import (
    HistoricalPortfolioCreate,
    HistoricalPortfolioRead,
    SaleCreate,
    SaleList,
    SaleRead,
    SaleSummary,
    SaleUpdate,
    SaleVoid,
)
from app.schemas.transactions import (
    BuyCreate,
    HistoricalTransactionImport,
    PositionSummary,
    PositionTransactionList,
    PositionTransactionRead,
    SellCreate,
    TransactionUpdate,
    TransactionVoid,
)
from app.services.portfolio import PortfolioService
from app.services.sales import SaleService
from app.services.transactions import PositionTransactionService

router = APIRouter(
    prefix="/api/v1/portfolio",
    tags=["portfolio"],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
SessionDependency = Annotated[Session, Depends(get_session)]


def _service(session: Session) -> PortfolioService:
    return PortfolioService(PortfolioRepository(session))


def _sale_service(session: Session) -> SaleService:
    return SaleService(PortfolioRepository(session), SaleRepository(session))


def _transaction_service(session: Session) -> PositionTransactionService:
    return PositionTransactionService(session)


def _read(
    session: Session,
    request: Request,
    item: object,
    sale_summary: SaleSummary | None = None,
    position_summary: PositionSummary | None = None,
) -> PortfolioRead:
    values = PortfolioRead.model_validate(item)
    if sale_summary is not None:
        values = values.model_copy(
            update={
                "sale_summary": sale_summary,
                "active_sale_count": sale_summary.active_sale_count,
                "total_sold_quantity": sale_summary.total_sold_quantity,
                "weighted_average_sale_price": (sale_summary.weighted_average_sale_price),
                "total_realized_pnl": sale_summary.total_realized_pnl,
                "total_realized_return_percent": (sale_summary.total_realized_return_percent),
                "first_sold_at": sale_summary.first_sold_at,
                "last_sold_at": sale_summary.last_sold_at,
            }
        )
    if position_summary is not None:
        values = values.model_copy(
            update={
                "position_summary": position_summary,
                "total_bought_quantity": (position_summary.total_bought_quantity),
                "active_transaction_count": (position_summary.active_transaction_count),
                "buy_transaction_count": position_summary.buy_count,
                "sell_transaction_count": position_summary.sell_count,
                "first_traded_at": position_summary.first_traded_at,
                "last_traded_at": position_summary.last_traded_at,
            }
        )
    repository = InstrumentRepository(session)
    instrument = (
        repository.get(str(values.instrument_id))
        if values.instrument_id is not None
        else repository.get_active(values.market, values.symbol)
    )
    if instrument is None:
        return (
            values.model_copy(update={"official_disclosure_availability": "ERROR"})
            if values.instrument_id is not None
            else values
        )
    mappings = repository.mappings(instrument.id)
    availability = "UNSUPPORTED"
    settings = request.app.state.settings
    if mappings:
        configured = any(
            mapping.provider is ProviderName.OPENDART
            and settings.open_dart_configured
            or mapping.provider is ProviderName.SEC_EDGAR
            and settings.sec_configured
            for mapping in mappings
        )
        availability = "AVAILABLE" if configured else "NOT_CONFIGURED"
    if instrument.verification_status is not InstrumentVerificationStatus.VERIFIED:
        availability = "UNSUPPORTED"
    return values.model_copy(
        update={
            "instrument_verification_status": instrument.verification_status,
            "official_disclosure_availability": availability,
        }
    )


@router.get("", response_model=PortfolioList)
def list_portfolio(
    request: Request,
    session: SessionDependency,
    holding_status: Annotated[HoldingStatus | None, Query(alias="holdingStatus")] = None,
    position_status: Annotated[PositionStatus | None, Query(alias="positionStatus")] = None,
    tracking_status: Annotated[TrackingStatus | None, Query(alias="trackingStatus")] = None,
    market: str | None = None,
    query: str | None = None,
    include_archived: Annotated[bool, Query(alias="includeArchived")] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PortfolioList:
    items, total = _service(session).list(
        holding_status=holding_status,
        position_status=position_status,
        tracking_status=tracking_status,
        market=market,
        query=query,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    summaries = _sale_service(session).summaries(item.id for item in items)
    position_service = _transaction_service(session)
    return PortfolioList(
        items=[
            _read(
                session,
                request,
                item,
                summaries[item.id],
                position_service.summary(item.id),
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=PortfolioSummary)
def portfolio_summary(session: SessionDependency) -> PortfolioSummary:
    repository = PortfolioRepository(session)
    thesis_not_set = int(
        session.scalar(
            select(func.count())
            .select_from(PortfolioItemRecord)
            .outerjoin(
                InvestmentThesisRecord,
                InvestmentThesisRecord.portfolio_item_id == PortfolioItemRecord.id,
            )
            .where(
                PortfolioItemRecord.archived_at.is_(None),
                (
                    InvestmentThesisRecord.id.is_(None)
                    | (InvestmentThesisRecord.thesis_status == ThesisStatus.NOT_SET.value)
                ),
            )
        )
        or 0
    )
    return PortfolioSummary(
        total=repository.count_active(),
        holding=repository.count_active_by_position_status(PositionStatus.HOLDING),
        watchlist=repository.count_active_by_tracking_status(TrackingStatus.WATCHLIST),
        reentry_watch=repository.count_active_by_tracking_status(TrackingStatus.REENTRY_WATCH),
        closed=repository.count_active_by_position_status(PositionStatus.CLOSED),
        needs_review=repository.count_active_by_position_status(PositionStatus.NEEDS_REVIEW),
        thesis_not_set=thesis_not_set,
    )


@router.post("", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    request: Request,
    payload: PortfolioCreate,
    session: SessionDependency,
) -> PortfolioRead:
    initial_buy = payload.initial_buy
    create_payload = payload
    if initial_buy is not None:
        create_payload = payload.model_copy(
            update={
                "holding_status": HoldingStatus.WATCHLIST,
                "tracking_status": payload.tracking_status,
                "quantity": Decimal(0),
                "average_price": None,
                "initial_buy": None,
            }
        )
    item = _service(session).create(create_payload)
    if initial_buy is not None:
        _transaction_service(session).create_buy(item.id, initial_buy)
    position = _transaction_service(session).summary(item.id)
    return _read(session, request, item, position_summary=position)


@router.post(
    "/historical-sale",
    response_model=HistoricalPortfolioRead,
    status_code=status.HTTP_201_CREATED,
)
def create_historical_sale(
    payload: HistoricalPortfolioCreate,
    session: SessionDependency,
) -> HistoricalPortfolioRead:
    portfolio, sales, summary = _sale_service(session).create_historical(payload)
    return HistoricalPortfolioRead(
        portfolio_id=portfolio.id,
        sales=[SaleRead.model_validate(sale) for sale in sales],
        sale_summary=summary,
    )


@router.get("/{item_id}/sales", response_model=SaleList)
def list_sales(item_id: UUID, session: SessionDependency) -> SaleList:
    items = _sale_service(session).list(str(item_id))
    return SaleList(
        items=[SaleRead.model_validate(item) for item in items],
        total=len(items),
    )


@router.post(
    "/{item_id}/sales",
    response_model=SaleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_sale(
    item_id: UUID,
    payload: SaleCreate,
    session: SessionDependency,
) -> SaleRead:
    item = PortfolioRepository(session).get_by_id(str(item_id))
    if (
        item is None
        or item.holding_status is not HoldingStatus.HOLDING
        or item.quantity <= 0
        or item.average_price is None
        or item.average_price <= 0
    ):
        if item is None:
            _service(session).get(str(item_id))
        raise portfolio_not_holding()
    if payload.quantity > item.quantity:
        raise sale_quantity_exceeds_holding()
    if payload.sold_at > require_aware_utc(SystemClock().now()):
        raise sale_validation("미래 시각의 매도 거래는 등록할 수 없습니다.")
    service = _transaction_service(session)
    transaction = service.create_sell(
        str(item_id),
        SellCreate(
            traded_at=payload.sold_at,
            quantity=payload.quantity,
            unit_price=payload.sale_price,
            fee_amount=payload.fee_amount,
            tax_amount=payload.tax_amount,
            notes=payload.notes,
        ),
    )
    sale = service.compatibility_sale(str(item_id), transaction.id)
    return SaleRead.model_validate(sale)


@router.post(
    "/{item_id}/historical-sales",
    response_model=SaleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_historical_sale_for_portfolio(
    item_id: UUID,
    payload: SaleCreate,
    session: SessionDependency,
) -> SaleRead:
    sale = _sale_service(session).create_historical_sale(str(item_id), payload)
    return SaleRead.model_validate(sale)


@router.get("/{item_id}/sales/{sale_id}", response_model=SaleRead)
def get_sale(
    item_id: UUID,
    sale_id: UUID,
    session: SessionDependency,
) -> SaleRead:
    sale = _sale_service(session).get(str(item_id), str(sale_id))
    return SaleRead.model_validate(sale)


@router.patch("/{item_id}/sales/{sale_id}", response_model=SaleRead)
def update_sale(
    item_id: UUID,
    sale_id: UUID,
    payload: SaleUpdate,
    session: SessionDependency,
) -> SaleRead:
    legacy = _sale_service(session)
    sale = legacy.get(str(item_id), str(sale_id))
    if "quantity" in payload.model_fields_set:
        raise sale_quantity_immutable()
    if sale.ledger_transaction_id is None:
        sale = legacy.update(str(item_id), str(sale_id), payload)
        return SaleRead.model_validate(sale)
    transaction_changes: dict[str, object] = {}
    if "sold_at" in payload.model_fields_set:
        transaction_changes["traded_at"] = payload.sold_at
    if "sale_price" in payload.model_fields_set:
        transaction_changes["unit_price"] = payload.sale_price
    if "fee_amount" in payload.model_fields_set:
        transaction_changes["fee_amount"] = payload.fee_amount
    if "tax_amount" in payload.model_fields_set:
        transaction_changes["tax_amount"] = payload.tax_amount
    if "notes" in payload.model_fields_set:
        transaction_changes["notes"] = payload.notes
    if "quantity" in payload.model_fields_set:
        transaction_changes["quantity"] = payload.quantity
    transaction = _transaction_service(session).update(
        str(item_id),
        sale.ledger_transaction_id,
        TransactionUpdate.model_validate(transaction_changes),
    )
    sale = _transaction_service(session).compatibility_sale(
        str(item_id),
        transaction.id,
    )
    return SaleRead.model_validate(sale)


@router.post("/{item_id}/sales/{sale_id}/void", response_model=SaleRead)
def void_sale(
    item_id: UUID,
    sale_id: UUID,
    payload: SaleVoid,
    session: SessionDependency,
) -> SaleRead:
    legacy = _sale_service(session)
    sale = legacy.get(str(item_id), str(sale_id))
    if sale.status.value == "VOIDED":
        raise sale_already_voided()
    if sale.ledger_transaction_id is None:
        sale = legacy.void(str(item_id), str(sale_id), payload)
        return SaleRead.model_validate(sale)
    if sale.transaction_type is not SaleTransactionType.HISTORICAL_SALE:
        latest = SaleRepository(session).latest_active_current_sale(str(item_id))
        if latest is None or latest.id != sale.id:
            raise sale_void_not_latest()
    transaction = _transaction_service(session).void(
        str(item_id),
        sale.ledger_transaction_id,
        TransactionVoid(reason=payload.reason),
    )
    sale = _transaction_service(session).compatibility_sale(
        str(item_id),
        transaction.id,
    )
    return SaleRead.model_validate(sale)


@router.get("/{item_id}/sale-summary", response_model=SaleSummary)
def get_sale_summary(
    item_id: UUID,
    session: SessionDependency,
) -> SaleSummary:
    return _sale_service(session).summary(str(item_id))


@router.get(
    "/{item_id}/transactions",
    response_model=PositionTransactionList,
)
def list_transactions(
    item_id: UUID,
    session: SessionDependency,
    include_voided: Annotated[bool, Query(alias="includeVoided")] = False,
) -> PositionTransactionList:
    records = _transaction_service(session).list(
        str(item_id),
        include_voided=include_voided,
    )
    return PositionTransactionList(
        items=[PositionTransactionRead.model_validate(record) for record in records],
        total=len(records),
    )


@router.post(
    "/{item_id}/transactions/buys",
    response_model=PositionTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_buy_transaction(
    item_id: UUID,
    payload: BuyCreate,
    session: SessionDependency,
) -> PositionTransactionRead:
    return PositionTransactionRead.model_validate(
        _transaction_service(session).create_buy(str(item_id), payload)
    )


@router.post(
    "/{item_id}/transactions/sells",
    response_model=PositionTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_sell_transaction(
    item_id: UUID,
    payload: SellCreate,
    session: SessionDependency,
) -> PositionTransactionRead:
    return PositionTransactionRead.model_validate(
        _transaction_service(session).create_sell(str(item_id), payload)
    )


@router.get(
    "/{item_id}/transactions/{transaction_id}",
    response_model=PositionTransactionRead,
)
def get_transaction(
    item_id: UUID,
    transaction_id: UUID,
    session: SessionDependency,
) -> PositionTransactionRead:
    return PositionTransactionRead.model_validate(
        _transaction_service(session).get(
            str(item_id),
            str(transaction_id),
        )
    )


@router.patch(
    "/{item_id}/transactions/{transaction_id}",
    response_model=PositionTransactionRead,
)
def update_transaction(
    item_id: UUID,
    transaction_id: UUID,
    payload: TransactionUpdate,
    session: SessionDependency,
) -> PositionTransactionRead:
    return PositionTransactionRead.model_validate(
        _transaction_service(session).update(
            str(item_id),
            str(transaction_id),
            payload,
        )
    )


@router.post(
    "/{item_id}/transactions/{transaction_id}/void",
    response_model=PositionTransactionRead,
)
def void_transaction(
    item_id: UUID,
    transaction_id: UUID,
    payload: TransactionVoid,
    session: SessionDependency,
) -> PositionTransactionRead:
    return PositionTransactionRead.model_validate(
        _transaction_service(session).void(
            str(item_id),
            str(transaction_id),
            payload,
        )
    )


@router.post(
    "/{item_id}/transactions/historical-import",
    response_model=PositionTransactionList,
    status_code=status.HTTP_201_CREATED,
)
def import_historical_transactions(
    item_id: UUID,
    payload: HistoricalTransactionImport,
    session: SessionDependency,
) -> PositionTransactionList:
    records = _transaction_service(session).historical_import(
        str(item_id),
        payload,
    )
    return PositionTransactionList(
        items=[PositionTransactionRead.model_validate(record) for record in records],
        total=len(records),
    )


@router.get(
    "/{item_id}/position-summary",
    response_model=PositionSummary,
)
def get_position_summary(
    item_id: UUID,
    session: SessionDependency,
) -> PositionSummary:
    return _transaction_service(session).summary(str(item_id))


@router.get("/{item_id}", response_model=PortfolioRead)
def get_portfolio(item_id: UUID, request: Request, session: SessionDependency) -> PortfolioRead:
    item = _service(session).get(str(item_id))
    summary = _sale_service(session).summary(str(item_id))
    position = _transaction_service(session).summary(str(item_id))
    return _read(session, request, item, summary, position)


@router.patch("/{item_id}/context", response_model=PortfolioRead)
def update_portfolio_context(
    item_id: UUID,
    request: Request,
    payload: PortfolioContextUpdate,
    session: SessionDependency,
) -> PortfolioRead:
    item = _service(session).update_context(str(item_id), payload)
    summary = _sale_service(session).summary(str(item_id))
    position = _transaction_service(session).summary(str(item_id))
    return _read(session, request, item, summary, position)


@router.patch("/{item_id}", response_model=PortfolioRead)
def update_portfolio(
    item_id: UUID,
    request: Request,
    payload: PortfolioUpdate,
    session: SessionDependency,
) -> PortfolioRead:
    item = _service(session).update(str(item_id), payload)
    summary = _sale_service(session).summary(str(item_id))
    position = _transaction_service(session).summary(str(item_id))
    return _read(session, request, item, summary, position)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_portfolio(item_id: UUID, session: SessionDependency) -> Response:
    _service(session).archive(str(item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{item_id}/restore", response_model=PortfolioRead)
def restore_portfolio(
    item_id: UUID, request: Request, session: SessionDependency
) -> PortfolioRead:
    item = _service(session).restore(str(item_id))
    summary = _sale_service(session).summary(str(item_id))
    position = _transaction_service(session).summary(str(item_id))
    return _read(session, request, item, summary, position)
