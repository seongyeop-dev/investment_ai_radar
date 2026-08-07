from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select

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
from app.schemas.analyst_references import (
    AnalystReferenceImportLinkRequest,
)
from app.services.analyst_references import (
    AnalystReferenceImportBlockedError,
    AnalystReferenceImportConfirmationRequiredError,
    AnalystReferenceImportService,
    analyst_reference_source_fingerprint,
)


def _portfolio(
    *,
    symbol: str,
    archived: bool = False,
) -> PortfolioItemRecord:
    return PortfolioItemRecord(
        symbol=symbol,
        name=f"{symbol} Preview Fixture",
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


def _request(
    *,
    source_url: str,
    portfolio_item_ids: list[str],
    title: str = "Preview service metadata",
    confirm: bool = False,
) -> AnalystReferenceImportLinkRequest:
    return AnalystReferenceImportLinkRequest.model_validate(
        {
            "sourceUrl": source_url,
            "publisherName": "Preview Fixture Publisher",
            "publisherType": "RESEARCH_HOUSE",
            "title": title,
            "analystName": "Preview Fixture Analyst",
            "publishedAt": "2026-07-29T09:00:00+09:00",
            "accessType": "PUBLIC",
            "documentType": "REPORT",
            "publisherRatingRaw": None,
            "publisherTargetPriceRaw": None,
            "targetCurrency": None,
            "publicAbstract": "Public metadata only.",
            "portfolioItemIds": portfolio_item_ids,
            "confirm": confirm,
        }
    )


def _reference(
    *,
    canonical_url: str,
    source_fingerprint: str,
) -> AnalystReferenceRecord:
    return AnalystReferenceRecord(
        publisher_name="Existing Fixture Publisher",
        publisher_type=AnalystPublisherType.RESEARCH_HOUSE,
        title="Existing fixture reference",
        analyst_name=None,
        published_at=datetime(2026, 7, 28, tzinfo=UTC),
        canonical_url=canonical_url,
        access_type=AnalystAccessType.PUBLIC,
        document_type=AnalystDocumentType.REPORT,
        publisher_rating_raw=None,
        publisher_target_price_raw=None,
        target_currency=None,
        public_abstract=None,
        source_retrieved_at=None,
        source_fingerprint=source_fingerprint,
        freshness_status=AnalystFreshnessStatus.UNKNOWN,
        is_active=False,
    )


def _count(
    session: object,
    model: type[object],
) -> int:
    value = session.scalar(select(func.count()).select_from(model))
    return int(value or 0)


def test_preview_normalizes_url_and_does_not_write(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        first = _portfolio(symbol="FIRST")
        second = _portfolio(symbol="SECOND")
        session.add_all([first, second])
        session.flush()

        payload = _request(
            source_url=("HTTPS://EXAMPLE.COM:443/research/service-preview#section"),
            portfolio_item_ids=[
                second.id,
                first.id,
                second.id,
            ],
        )

        reference_count_before = _count(
            session,
            AnalystReferenceRecord,
        )
        coverage_count_before = _count(
            session,
            AnalystReferenceCoverageRecord,
        )

        preview = AnalystReferenceImportService(session).preview(payload)

        reference_count_after = _count(
            session,
            AnalystReferenceRecord,
        )
        coverage_count_after = _count(
            session,
            AnalystReferenceCoverageRecord,
        )

        assert preview.normalized_url == ("https://example.com/research/service-preview")
        assert len(preview.source_fingerprint) == 64
        assert [item.id for item in preview.portfolio_items] == [
            UUID(second.id),
            UUID(first.id),
        ]
        assert "DUPLICATE_PORTFOLIO_ITEM_IDS_REMOVED" in preview.validation_warnings
        assert "URL_FRAGMENT_REMOVED" in preview.validation_warnings
        assert preview.would_create is True
        assert preview.confirmed is False
        assert reference_count_after == reference_count_before
        assert coverage_count_after == coverage_count_before


def test_preview_blocks_missing_portfolio_item(
    api_database: Database,
) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"

    with api_database.session_scope() as session:
        payload = _request(
            source_url=("https://example.com/research/missing-portfolio"),
            portfolio_item_ids=[missing_id],
        )

        preview = AnalystReferenceImportService(session).preview(payload)

        assert preview.portfolio_items == []
        assert preview.would_create is False
        assert f"PORTFOLIO_ITEM_NOT_FOUND:{missing_id}" in preview.validation_warnings


def test_preview_detects_canonical_url_duplicate(
    api_database: Database,
) -> None:
    canonical_url = "https://example.com/research/canonical-duplicate"

    with api_database.session_scope() as session:
        portfolio = _portfolio(symbol="DUPLICATE")
        existing = _reference(
            canonical_url=canonical_url,
            source_fingerprint="a" * 64,
        )
        session.add_all([portfolio, existing])
        session.flush()

        payload = _request(
            source_url=canonical_url,
            portfolio_item_ids=[portfolio.id],
        )

        preview = AnalystReferenceImportService(session).preview(payload)

        assert preview.duplicate.canonical_url_duplicate is True
        assert preview.duplicate.canonical_url_reference_id == UUID(existing.id)
        assert preview.would_create is False


def test_preview_detects_metadata_fingerprint_duplicate(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        portfolio = _portfolio(symbol="FINGERPRINT")
        session.add(portfolio)
        session.flush()

        payload = _request(
            source_url=("https://example.com/research/new-location"),
            portfolio_item_ids=[portfolio.id],
        )
        fingerprint = analyst_reference_source_fingerprint(payload)

        existing = _reference(
            canonical_url=("https://example.com/research/existing-location"),
            source_fingerprint=fingerprint,
        )
        session.add(existing)
        session.flush()

        preview = AnalystReferenceImportService(session).preview(payload)

        assert preview.duplicate.canonical_url_duplicate is False
        assert preview.duplicate.source_fingerprint_duplicate is True
        assert preview.duplicate.source_fingerprint_reference_id == UUID(existing.id)
        assert preview.would_create is False


def test_preview_warns_for_archived_portfolio(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        portfolio = _portfolio(
            symbol="ARCHIVED",
            archived=True,
        )
        session.add(portfolio)
        session.flush()

        payload = _request(
            source_url=("https://example.com/research/archived-portfolio"),
            portfolio_item_ids=[portfolio.id],
        )

        preview = AnalystReferenceImportService(session).preview(payload)

        assert preview.portfolio_items[0].is_archived is True
        assert f"ARCHIVED_PORTFOLIO_ITEM:{portfolio.id}" in preview.validation_warnings
        assert preview.would_create is True


def test_confirm_writes_reference_and_coverages(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        first = _portfolio(symbol="CONFIRM_FIRST")
        second = _portfolio(symbol="CONFIRM_SECOND")

        session.add_all([first, second])
        session.flush()

        payload = _request(
            source_url=("HTTPS://EXAMPLE.COM:443/research/confirm-service#metadata"),
            portfolio_item_ids=[
                second.id,
                first.id,
                second.id,
            ],
            confirm=True,
        )

        result = AnalystReferenceImportService(session).confirm(payload)

        references = list(session.scalars(select(AnalystReferenceRecord)))
        coverages = list(session.scalars(select(AnalystReferenceCoverageRecord)))

        assert result.confirmed is True
        assert result.normalized_url == ("https://example.com/research/confirm-service")
        assert len(references) == 1
        assert len(coverages) == 2

        reference = references[0]

        assert reference.id == str(result.reference.id)
        assert reference.canonical_url == (result.normalized_url)
        assert reference.source_fingerprint == (result.source_fingerprint)
        assert reference.source_retrieved_at is not None
        assert reference.is_active is True
        assert reference.freshness_status is AnalystFreshnessStatus.UNKNOWN

        assert [coverage.portfolio_item_id for coverage in result.coverages] == [
            UUID(second.id),
            UUID(first.id),
        ]

        assert all(
            coverage.relation_type is AnalystRelationType.PRIMARY
            for coverage in result.coverages
        )
        assert all(
            coverage.mapping_confidence is AnalystMappingConfidence.VERIFIED
            for coverage in result.coverages
        )
        assert all(coverage.human_review_required is False for coverage in result.coverages)
        assert result.reference.coverages == (result.coverages)
        assert "DUPLICATE_PORTFOLIO_ITEM_IDS_REMOVED" in result.validation_warnings
        assert "URL_FRAGMENT_REMOVED" in result.validation_warnings


def test_confirm_requires_explicit_true(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        portfolio = _portfolio(symbol="CONFIRM_REQUIRED")
        session.add(portfolio)
        session.flush()

        payload = _request(
            source_url=("https://example.com/research/confirmation-required"),
            portfolio_item_ids=[portfolio.id],
            confirm=False,
        )

        with pytest.raises(AnalystReferenceImportConfirmationRequiredError):
            AnalystReferenceImportService(session).confirm(payload)

        assert (
            _count(
                session,
                AnalystReferenceRecord,
            )
            == 0
        )
        assert (
            _count(
                session,
                AnalystReferenceCoverageRecord,
            )
            == 0
        )


def test_confirm_blocks_duplicate_without_writing(
    api_database: Database,
) -> None:
    canonical_url = "https://example.com/research/confirm-duplicate"

    with api_database.session_scope() as session:
        portfolio = _portfolio(symbol="CONFIRM_DUPLICATE")
        existing = _reference(
            canonical_url=canonical_url,
            source_fingerprint="f" * 64,
        )

        session.add_all([portfolio, existing])
        session.flush()

        payload = _request(
            source_url=canonical_url,
            portfolio_item_ids=[portfolio.id],
            confirm=True,
        )

        with pytest.raises(AnalystReferenceImportBlockedError) as exc_info:
            AnalystReferenceImportService(session).confirm(payload)

        assert exc_info.value.preview.duplicate.canonical_url_duplicate is True
        assert exc_info.value.preview.would_create is False
        assert (
            _count(
                session,
                AnalystReferenceRecord,
            )
            == 1
        )
        assert (
            _count(
                session,
                AnalystReferenceCoverageRecord,
            )
            == 0
        )


def test_confirm_blocks_missing_portfolio_without_writing(
    api_database: Database,
) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"

    with api_database.session_scope() as session:
        payload = _request(
            source_url=("https://example.com/research/confirm-missing-portfolio"),
            portfolio_item_ids=[missing_id],
            confirm=True,
        )

        with pytest.raises(AnalystReferenceImportBlockedError) as exc_info:
            AnalystReferenceImportService(session).confirm(payload)

        assert exc_info.value.preview.would_create is False
        assert (
            f"PORTFOLIO_ITEM_NOT_FOUND:{missing_id}"
            in exc_info.value.preview.validation_warnings
        )
        assert (
            _count(
                session,
                AnalystReferenceRecord,
            )
            == 0
        )
        assert (
            _count(
                session,
                AnalystReferenceCoverageRecord,
            )
            == 0
        )
