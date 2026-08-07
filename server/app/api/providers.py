from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.core.config import Settings
from app.models.database import PortfolioItemRecord
from app.models.disclosures import (
    DisclosureRecord,
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    MappingStatus,
)
from app.models.market_data import ProviderSyncStateRecord, QuoteSnapshotRecord
from app.schemas.providers import (
    InstrumentMappingRead,
    PortfolioQuoteRead,
    ProviderStatusList,
    ProviderStatusRead,
    QuoteList,
    QuoteRead,
)
from app.services.market_calendar import default_market_calendar

router = APIRouter(prefix="/api/v1", tags=["providers"])
SessionDependency = Annotated[Session, Depends(get_session)]


def _quote(record: QuoteSnapshotRecord) -> QuoteRead:
    return QuoteRead.model_validate(record)


def _latest_quotes(session: SessionDependency) -> list[QuoteSnapshotRecord]:
    latest = (
        select(
            QuoteSnapshotRecord.provider,
            QuoteSnapshotRecord.instrument_id,
            func.max(QuoteSnapshotRecord.fetched_at).label("latest"),
        )
        .group_by(QuoteSnapshotRecord.provider, QuoteSnapshotRecord.instrument_id)
        .subquery()
    )
    return list(
        session.scalars(
            select(QuoteSnapshotRecord)
            .join(
                latest,
                (QuoteSnapshotRecord.provider == latest.c.provider)
                & (QuoteSnapshotRecord.instrument_id == latest.c.instrument_id)
                & (QuoteSnapshotRecord.fetched_at == latest.c.latest),
            )
            .order_by(QuoteSnapshotRecord.provider)
        )
    )


def _configured(settings: Settings, provider: str, calendar_ready: bool) -> bool:
    return {
        "OPENDART": settings.open_dart_configured,
        "SEC_EDGAR": settings.sec_configured,
        "UPBIT": settings.upbit_public_market_enabled,
        "BINANCE": settings.binance_public_market_enabled,
        "KRX_CALENDAR": settings.market_calendar_enabled and calendar_ready,
        "NASDAQ_CALENDAR": settings.market_calendar_enabled and calendar_ready,
    }[provider]


def _current_provider_status(value: str) -> str:
    return "READY" if value == "SUCCEEDED" else value


def _mapping_read(
    item: InstrumentProviderMappingRecord,
    instrument: InstrumentRecord,
) -> InstrumentMappingRead:
    return InstrumentMappingRead(
        id=item.id,
        instrument_id=item.instrument_id,
        provider=item.provider.value,
        provider_instrument_id=item.provider_company_id,
        provider_symbol=item.provider_symbol,
        cik=item.cik,
        corp_code=item.corp_code,
        stock_code=item.stock_code,
        canonical_symbol=instrument.canonical_symbol,
        exchange=instrument.exchange,
        official_name=item.official_name,
        mapping_status=item.mapping_status.value,
        match_method=item.match_method.value,
        confidence=item.confidence,
        source_url=item.source_url,
        source_updated_at=item.source_updated_at,
        verified_at=item.verified_at,
        last_checked_at=item.last_checked_at,
        conflict_reason=item.conflict_reason,
    )


@router.get("/providers", response_model=ProviderStatusList)
@router.get("/providers/status", response_model=ProviderStatusList)
def provider_status(request: Request, session: SessionDependency) -> ProviderStatusList:
    settings: Settings = request.app.state.settings
    calendar_ready = default_market_calendar(
        enabled=settings.market_calendar_enabled
    ).configured
    definitions = [
        ("OPENDART", "OFFICIAL_DISCLOSURE"),
        ("SEC_EDGAR", "OFFICIAL_DISCLOSURE"),
        ("UPBIT", "PUBLIC_QUOTE"),
        ("BINANCE", "PUBLIC_QUOTE"),
        ("KRX_CALENDAR", "MARKET_CALENDAR"),
        ("NASDAQ_CALENDAR", "MARKET_CALENDAR"),
    ]
    items: list[ProviderStatusRead] = []
    for provider, capability in definitions:
        state = session.get(
            ProviderSyncStateRecord, {"provider": provider, "capability": capability}
        )
        configured = _configured(settings, provider, calendar_ready)
        items.append(
            ProviderStatusRead(
                provider=provider,
                capability=capability,
                configured=configured,
                status=(
                    _current_provider_status(state.status)
                    if configured and state
                    else ("CONFIGURED" if configured else "NOT_CONFIGURED")
                ),
                last_success_at=state.last_success_at if state else None,
                last_error_code=state.last_error_code if state else None,
                consecutive_failures=state.consecutive_failures if state else 0,
                request_count=state.request_count if state else 0,
                success_count=state.success_count if state else 0,
            )
        )
    verified = session.scalar(
        select(func.count())
        .select_from(InstrumentProviderMappingRecord)
        .where(InstrumentProviderMappingRecord.mapping_status == MappingStatus.VERIFIED)
    )
    unresolved = session.scalar(
        select(func.count())
        .select_from(InstrumentProviderMappingRecord)
        .where(InstrumentProviderMappingRecord.mapping_status == MappingStatus.UNRESOLVED)
    )
    conflicting = session.scalar(
        select(func.count())
        .select_from(InstrumentProviderMappingRecord)
        .where(InstrumentProviderMappingRecord.mapping_status == MappingStatus.CONFLICTING)
    )
    stale = session.scalar(
        select(func.count())
        .select_from(InstrumentProviderMappingRecord)
        .where(InstrumentProviderMappingRecord.mapping_status == MappingStatus.STALE)
    )
    return ProviderStatusList(
        items=items,
        verified_mapping_count=int(verified or 0),
        unresolved_mapping_count=int(unresolved or 0),
        conflicting_mapping_count=int(conflicting or 0),
        stale_mapping_count=int(stale or 0),
        recent_disclosure_count=int(
            session.scalar(
                select(func.count())
                .select_from(DisclosureRecord)
                .where(DisclosureRecord.published_at >= datetime.now(UTC) - timedelta(days=30))
            )
            or 0
        ),
        latest_quote_count=len(_latest_quotes(session)),
    )


@router.get(
    "/instruments/{instrument_id}/mappings",
    response_model=list[InstrumentMappingRead],
)
def instrument_mappings(
    instrument_id: UUID, session: SessionDependency
) -> list[InstrumentMappingRead]:
    instrument = session.get(InstrumentRecord, str(instrument_id))
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    mappings = session.scalars(
        select(InstrumentProviderMappingRecord).where(
            InstrumentProviderMappingRecord.instrument_id == instrument.id,
            InstrumentProviderMappingRecord.active.is_(True),
        )
    )
    return [_mapping_read(item, instrument) for item in mappings]


@router.get(
    "/portfolio/{portfolio_id}/mappings",
    response_model=list[InstrumentMappingRead],
)
def portfolio_mappings(
    portfolio_id: UUID, session: SessionDependency
) -> list[InstrumentMappingRead]:
    portfolio = session.get(PortfolioItemRecord, str(portfolio_id))
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    instruments = list(
        session.scalars(
            select(InstrumentRecord).where(
                InstrumentRecord.active.is_(True),
                (
                    InstrumentRecord.id == portfolio.instrument_id
                    if portfolio.instrument_id
                    else (
                        (InstrumentRecord.market == portfolio.market)
                        & (InstrumentRecord.canonical_symbol == portfolio.symbol)
                    )
                ),
            )
        )
    )
    if not instruments:
        return []
    instrument_by_id = {instrument.id: instrument for instrument in instruments}
    mappings = session.scalars(
        select(InstrumentProviderMappingRecord).where(
            InstrumentProviderMappingRecord.instrument_id.in_(instrument_by_id),
            InstrumentProviderMappingRecord.active.is_(True),
        )
    )
    return [_mapping_read(item, instrument_by_id[item.instrument_id]) for item in mappings]


@router.get("/quotes/latest", response_model=QuoteList, deprecated=True)
def latest_quotes(session: SessionDependency) -> QuoteList:
    items = _latest_quotes(session)
    return QuoteList(items=[_quote(item) for item in items], total=len(items))


@router.get(
    "/portfolio/{portfolio_id}/quote",
    response_model=PortfolioQuoteRead,
    deprecated=True,
)
def portfolio_quote(
    portfolio_id: UUID, request: Request, session: SessionDependency
) -> PortfolioQuoteRead:
    portfolio = session.get(PortfolioItemRecord, str(portfolio_id))
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    settings: Settings = request.app.state.settings
    configured = (
        settings.upbit_public_market_enabled
        if portfolio.market == "UPBIT"
        else settings.binance_public_market_enabled
        if portfolio.market == "BINANCE"
        else False
    )
    instrument = session.scalar(
        select(InstrumentRecord).where(
            InstrumentRecord.market == portfolio.market,
            InstrumentRecord.canonical_symbol == portfolio.symbol,
            InstrumentRecord.active.is_(True),
        )
    )
    record = (
        session.scalar(
            select(QuoteSnapshotRecord)
            .where(QuoteSnapshotRecord.instrument_id == instrument.id)
            .order_by(QuoteSnapshotRecord.fetched_at.desc())
            .limit(1)
        )
        if instrument
        else None
    )
    return PortfolioQuoteRead(
        portfolio_id=portfolio.id,
        quote_status=(
            record.freshness_status
            if record
            else "NOT_COLLECTED"
            if configured
            else "NOT_CONFIGURED"
        ),
        provider_configured=configured,
        quote=_quote(record) if record else None,
    )
