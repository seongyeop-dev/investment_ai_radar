from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
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


def _portfolio(
    *,
    symbol: str = "TEST",
) -> PortfolioItemRecord:
    return PortfolioItemRecord(
        symbol=symbol,
        name=f"{symbol} Company",
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
    url_suffix: str,
    fingerprint_character: str,
    active: bool = True,
) -> AnalystReferenceRecord:
    return AnalystReferenceRecord(
        publisher_name="Example Research",
        publisher_type=AnalystPublisherType.RESEARCH_HOUSE,
        title=f"Example research {url_suffix}",
        analyst_name="Example Analyst",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        canonical_url=(f"https://example.com/research/{url_suffix}"),
        access_type=AnalystAccessType.PUBLIC,
        document_type=AnalystDocumentType.REPORT,
        publisher_rating_raw="Public original rating",
        publisher_target_price_raw="Public original target",
        target_currency="KRW",
        public_abstract="Public metadata only.",
        source_retrieved_at=datetime(
            2026,
            7,
            29,
            tzinfo=UTC,
        ),
        source_fingerprint=fingerprint_character * 64,
        freshness_status=AnalystFreshnessStatus.CURRENT,
        is_active=active,
    )


def _import_payload(
    *,
    portfolio_item_ids: list[str],
    source_url: str = ("https://example.com/research/api-import-link"),
    confirm: bool = False,
) -> dict[str, object]:
    return {
        "sourceUrl": source_url,
        "publisherName": "API Import Fixture Publisher",
        "publisherType": "RESEARCH_HOUSE",
        "title": "API import-link public metadata",
        "analystName": "API Import Fixture Analyst",
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


def _record_count(
    database: Database,
    model: type[object],
) -> int:
    with database.session_scope() as session:
        value = session.scalar(select(func.count()).select_from(model))

    return int(value or 0)


def test_analyst_reference_list_is_empty(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/analyst-references")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }


def test_analyst_reference_list_detail_and_portfolio_filter(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        portfolio = _portfolio()
        other_portfolio = _portfolio(symbol="OTHER")
        session.add_all(
            [
                portfolio,
                other_portfolio,
            ]
        )
        session.flush()

        reference = _reference(
            url_suffix="primary",
            fingerprint_character="a",
        )
        other_reference = _reference(
            url_suffix="other",
            fingerprint_character="b",
        )
        session.add_all(
            [
                reference,
                other_reference,
            ]
        )
        session.flush()

        session.add_all(
            [
                AnalystReferenceCoverageRecord(
                    analyst_reference_id=reference.id,
                    portfolio_item_id=portfolio.id,
                    relation_type=AnalystRelationType.PRIMARY,
                    mapping_confidence=(AnalystMappingConfidence.VERIFIED),
                    human_review_required=False,
                ),
                AnalystReferenceCoverageRecord(
                    analyst_reference_id=other_reference.id,
                    portfolio_item_id=other_portfolio.id,
                    relation_type=AnalystRelationType.PRIMARY,
                    mapping_confidence=(AnalystMappingConfidence.VERIFIED),
                    human_review_required=False,
                ),
            ]
        )

        reference_id = reference.id
        portfolio_id = portfolio.id

    list_response = api_client.get("/api/v1/analyst-references")

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 2

    detail_response = api_client.get(f"/api/v1/analyst-references/{reference_id}")

    assert detail_response.status_code == 200

    detail = detail_response.json()

    assert detail["publisherName"] == "Example Research"
    assert detail["canonicalUrl"].startswith("https://")
    assert len(detail["coverages"]) == 1

    forbidden_fields = {
        "fullText",
        "articleBody",
        "pdfBinary",
        "documentBinary",
        "recommendation",
        "generatedTargetPrice",
        "decisionReview",
        "portfolioImpact",
    }

    assert forbidden_fields.isdisjoint(detail)

    portfolio_response = api_client.get(f"/api/v1/analyst-references/portfolio/{portfolio_id}")

    assert portfolio_response.status_code == 200
    assert portfolio_response.json()["total"] == 1
    assert portfolio_response.json()["items"][0]["id"] == reference_id


def test_inactive_references_are_hidden_by_default(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        session.add(
            _reference(
                url_suffix="inactive",
                fingerprint_character="c",
                active=False,
            )
        )

    default_response = api_client.get("/api/v1/analyst-references")
    include_response = api_client.get("/api/v1/analyst-references?includeInactive=true")

    assert default_response.status_code == 200
    assert default_response.json()["total"] == 0

    assert include_response.status_code == 200
    assert include_response.json()["total"] == 1


def test_unknown_reference_returns_404(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/analyst-references/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_import_link_preview_does_not_write(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        portfolio = _portfolio(symbol="API_PREVIEW")
        session.add(portfolio)
        session.flush()
        portfolio_id = portfolio.id

    reference_count_before = _record_count(
        api_database,
        AnalystReferenceRecord,
    )
    coverage_count_before = _record_count(
        api_database,
        AnalystReferenceCoverageRecord,
    )

    response = api_client.post(
        "/api/v1/analyst-references/import-link",
        json=_import_payload(
            portfolio_item_ids=[portfolio_id],
            source_url=("HTTPS://EXAMPLE.COM:443/research/api-preview#metadata"),
            confirm=False,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["confirmed"] is False
    assert body["wouldCreate"] is True
    assert body["normalizedUrl"] == ("https://example.com/research/api-preview")
    assert body["portfolioItems"][0]["id"] == portfolio_id
    assert "URL_FRAGMENT_REMOVED" in (body["validationWarnings"])

    assert (
        _record_count(
            api_database,
            AnalystReferenceRecord,
        )
        == reference_count_before
    )
    assert (
        _record_count(
            api_database,
            AnalystReferenceCoverageRecord,
        )
        == coverage_count_before
    )


def test_import_link_confirm_creates_reference(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        first = _portfolio(symbol="API_CONFIRM_FIRST")
        second = _portfolio(symbol="API_CONFIRM_SECOND")
        session.add_all([first, second])
        session.flush()

        first_id = first.id
        second_id = second.id

    response = api_client.post(
        "/api/v1/analyst-references/import-link",
        json=_import_payload(
            portfolio_item_ids=[
                second_id,
                first_id,
                second_id,
            ],
            source_url=("https://example.com/research/api-confirm"),
            confirm=True,
        ),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["confirmed"] is True
    assert body["reference"]["canonicalUrl"] == ("https://example.com/research/api-confirm")
    assert len(body["coverages"]) == 2
    assert [coverage["portfolioItemId"] for coverage in body["coverages"]] == [
        second_id,
        first_id,
    ]
    assert "DUPLICATE_PORTFOLIO_ITEM_IDS_REMOVED" in body["validationWarnings"]

    assert (
        _record_count(
            api_database,
            AnalystReferenceRecord,
        )
        == 1
    )
    assert (
        _record_count(
            api_database,
            AnalystReferenceCoverageRecord,
        )
        == 2
    )


def test_import_link_duplicate_returns_conflict(
    api_client: TestClient,
    api_database: Database,
) -> None:
    canonical_url = "https://example.com/research/api-duplicate"

    with api_database.session_scope() as session:
        portfolio = _portfolio(symbol="API_DUPLICATE")
        reference = _reference(
            url_suffix="api-duplicate-existing",
            fingerprint_character="e",
        )
        reference.canonical_url = canonical_url

        session.add_all([portfolio, reference])
        session.flush()

        portfolio_id = portfolio.id
        reference_id = reference.id

    response = api_client.post(
        "/api/v1/analyst-references/import-link",
        json=_import_payload(
            portfolio_item_ids=[portfolio_id],
            source_url=canonical_url,
            confirm=True,
        ),
    )

    assert response.status_code == 409

    detail = response.json()["detail"]

    assert detail["code"] == ("ANALYST_REFERENCE_IMPORT_BLOCKED")
    assert detail["preview"]["duplicate"]["canonicalUrlDuplicate"] is True
    assert detail["preview"]["duplicate"]["canonicalUrlReferenceId"] == reference_id
    assert detail["preview"]["wouldCreate"] is False

    assert (
        _record_count(
            api_database,
            AnalystReferenceRecord,
        )
        == 1
    )
    assert (
        _record_count(
            api_database,
            AnalystReferenceCoverageRecord,
        )
        == 0
    )


def test_import_link_missing_portfolio_returns_conflict(
    api_client: TestClient,
    api_database: Database,
) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"

    response = api_client.post(
        "/api/v1/analyst-references/import-link",
        json=_import_payload(
            portfolio_item_ids=[missing_id],
            source_url=("https://example.com/research/api-missing-portfolio"),
            confirm=True,
        ),
    )

    assert response.status_code == 409

    preview = response.json()["detail"]["preview"]

    assert preview["wouldCreate"] is False
    assert f"PORTFOLIO_ITEM_NOT_FOUND:{missing_id}" in preview["validationWarnings"]

    assert (
        _record_count(
            api_database,
            AnalystReferenceRecord,
        )
        == 0
    )
    assert (
        _record_count(
            api_database,
            AnalystReferenceCoverageRecord,
        )
        == 0
    )


def test_import_link_rejects_non_http_url(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/v1/analyst-references/import-link",
        json=_import_payload(
            portfolio_item_ids=["00000000-0000-0000-0000-000000000001"],
            source_url="file:///tmp/research.pdf",
            confirm=False,
        ),
    )

    assert response.status_code == 422
