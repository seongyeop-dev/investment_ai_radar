from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.database import Database
from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystMappingConfidence,
    AnalystPublisherType,
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
    AnalystRelationType,
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


def _database() -> Database:
    database = Database("sqlite+pysqlite://")
    database.create_schema()
    return database


def _portfolio() -> PortfolioItemRecord:
    return PortfolioItemRecord(
        symbol="TEST",
        name="Test Company",
        market="KOSPI",
        currency=Currency.KRW,
        asset_type=AssetType.EQUITY,
        holding_status=HoldingStatus.WATCHLIST,
        position_status=PositionStatus.EMPTY,
        tracking_status=TrackingStatus.WATCHLIST,
        quantity=Decimal("0"),
        average_price=None,
        investment_horizon=InvestmentHorizon.UNSET,
        strategy="",
    )


def _reference(
    *,
    canonical_url: str = "https://example.com/research/test",
    fingerprint: str = "a" * 64,
) -> AnalystReferenceRecord:
    return AnalystReferenceRecord(
        publisher_name="Example Research",
        publisher_type=AnalystPublisherType.RESEARCH_HOUSE,
        title="Example public research metadata",
        analyst_name="Example Analyst",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        canonical_url=canonical_url,
        access_type=AnalystAccessType.PUBLIC,
        document_type=AnalystDocumentType.REPORT,
        publisher_rating_raw="Original rating text",
        publisher_target_price_raw="Original target text",
        target_currency="krw",
        public_abstract="Public metadata only.",
        source_retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
        source_fingerprint=fingerprint,
        freshness_status=AnalystFreshnessStatus.CURRENT,
        is_active=True,
    )


def test_analyst_reference_tables_are_registered() -> None:
    database = _database()
    inspector = inspect(database.engine)

    assert "analyst_references" in inspector.get_table_names()
    assert "analyst_reference_coverages" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("analyst_references")}
    assert "canonical_url" in columns
    assert "public_abstract" in columns
    assert "publisher_rating_raw" in columns
    assert "publisher_target_price_raw" in columns

    forbidden = {
        "full_text",
        "article_body",
        "pdf_binary",
        "document_binary",
        "recommendation",
        "generated_target_price",
    }
    assert columns.isdisjoint(forbidden)


def test_reference_can_link_to_existing_portfolio_only() -> None:
    database = _database()

    with database.session_scope() as session:
        portfolio = _portfolio()
        session.add(portfolio)
        session.flush()

        reference = _reference()
        session.add(reference)
        session.flush()

        coverage = AnalystReferenceCoverageRecord(
            analyst_reference_id=reference.id,
            portfolio_item_id=portfolio.id,
            relation_type=AnalystRelationType.PRIMARY,
            mapping_confidence=AnalystMappingConfidence.VERIFIED,
            human_review_required=False,
        )
        session.add(coverage)
        session.flush()

        assert coverage.analyst_reference_id == reference.id
        assert coverage.portfolio_item_id == portfolio.id
        assert reference.target_currency == "KRW"


def test_duplicate_canonical_url_is_rejected() -> None:
    database = _database()

    with database.session_scope() as session:
        session.add(_reference())
        session.flush()

    with pytest.raises(IntegrityError), database.session_scope() as session:
        session.add(
            _reference(
                fingerprint="b" * 64,
            )
        )
        session.flush()


def test_non_http_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        _reference(
            canonical_url="javascript:alert(1)",
        )


def test_public_abstract_is_limited_to_300_characters() -> None:
    with pytest.raises(ValueError):
        reference = _reference()
        reference.public_abstract = "x" * 301
