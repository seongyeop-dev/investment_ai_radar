from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.database import Database
from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystPublisherType,
    AnalystReferenceRecord,
)
from app.models.database import (
    AssetType,
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
    PositionStatus,
    TrackingStatus,
)
from app.repositories.analyst_references import (
    AnalystReferenceRepository,
)


def _portfolio(
    *,
    symbol: str,
    archived: bool = False,
) -> PortfolioItemRecord:
    return PortfolioItemRecord(
        symbol=symbol,
        name=f"{symbol} Repository Fixture",
        market="TEST",
        currency=Currency.KRW,
        asset_type=AssetType.EQUITY,
        holding_status=HoldingStatus.WATCHLIST,
        position_status=PositionStatus.EMPTY,
        tracking_status=TrackingStatus.WATCHLIST,
        quantity=Decimal("0"),
        average_price=None,
        investment_horizon=InvestmentHorizon.UNSET,
        strategy="",
        archived_at=(datetime(2026, 7, 29, tzinfo=UTC) if archived else None),
    )


def _reference() -> AnalystReferenceRecord:
    return AnalystReferenceRecord(
        publisher_name="Repository Fixture Publisher",
        publisher_type=AnalystPublisherType.RESEARCH_HOUSE,
        title="Repository lookup fixture",
        analyst_name=None,
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        canonical_url=("https://example.com/repository/analyst-reference-lookup"),
        access_type=AnalystAccessType.PUBLIC,
        document_type=AnalystDocumentType.REPORT,
        publisher_rating_raw=None,
        publisher_target_price_raw=None,
        target_currency=None,
        public_abstract=None,
        source_retrieved_at=None,
        source_fingerprint="d" * 64,
        freshness_status=AnalystFreshnessStatus.UNKNOWN,
        is_active=False,
    )


def test_repository_finds_reference_by_canonical_url(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        reference = _reference()
        session.add(reference)
        session.flush()

        repository = AnalystReferenceRepository(session)

        found = repository.by_canonical_url(reference.canonical_url)

        assert found is not None
        assert found.id == reference.id
        assert found.is_active is False


def test_repository_finds_reference_by_source_fingerprint(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        reference = _reference()
        session.add(reference)
        session.flush()

        repository = AnalystReferenceRepository(session)

        found = repository.by_source_fingerprint(reference.source_fingerprint)

        assert found is not None
        assert found.id == reference.id
        assert found.is_active is False


def test_repository_returns_only_existing_portfolio_items(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        active = _portfolio(symbol="ACTIVE")
        archived = _portfolio(
            symbol="ARCHIVED",
            archived=True,
        )

        session.add_all([active, archived])
        session.flush()

        repository = AnalystReferenceRepository(session)

        rows = repository.portfolio_items(
            [
                archived.id,
                "00000000-0000-0000-0000-000000000000",
                active.id,
            ]
        )

        returned_ids = {row.id for row in rows}

        assert returned_ids == {
            active.id,
            archived.id,
        }


def test_repository_portfolio_items_empty_input(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        repository = AnalystReferenceRepository(session)

        assert repository.portfolio_items([]) == []
