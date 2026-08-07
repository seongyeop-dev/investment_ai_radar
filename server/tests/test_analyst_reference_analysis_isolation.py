from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import Database
from app.models.analysis import (
    DecisionReviewRecord,
    PortfolioImpactRecord,
)
from app.models.analyst_references import (
    AnalystReferenceCoverageRecord,
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
from app.models.operations import BriefingRecord
from app.services.analysis import AnalysisService
from app.services.briefings import BriefingService

NOW = datetime(2026, 7, 29, 7, 0, tzinfo=UTC)


def _portfolio() -> PortfolioItemRecord:
    return PortfolioItemRecord(
        symbol="ISOLATION",
        name="Analysis Isolation Test Item",
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
    )


def _import_payload(
    *,
    portfolio_item_id: str,
    confirm: bool,
) -> dict[str, object]:
    return {
        "sourceUrl": ("https://example.com/test-only/analyst-reference-isolation"),
        "publisherName": "Test-only metadata fixture",
        "publisherType": "OTHER",
        "title": ("Analyst reference automatic-analysis isolation metadata"),
        "analystName": None,
        "publishedAt": "2026-07-29T16:00:00+09:00",
        "accessType": "PUBLIC",
        "documentType": "OTHER",
        "publisherRatingRaw": None,
        "publisherTargetPriceRaw": None,
        "targetCurrency": None,
        "publicAbstract": ("Temporary metadata used only by the isolated test database."),
        "portfolioItemIds": [portfolio_item_id],
        "confirm": confirm,
    }


def _table_counts(
    database: Database,
) -> dict[str, int]:
    models: dict[str, type[object]] = {
        "analystReferences": AnalystReferenceRecord,
        "analystCoverages": (AnalystReferenceCoverageRecord),
        "decisionReviews": DecisionReviewRecord,
        "portfolioImpacts": PortfolioImpactRecord,
        "briefings": BriefingRecord,
    }

    with database.session_scope() as session:
        return {
            name: int(session.scalar(select(func.count()).select_from(model)) or 0)
            for name, model in models.items()
        }


def _analysis_outputs(
    client: TestClient,
    *,
    portfolio_item_id: str,
    briefing_id: str,
) -> dict[str, object]:
    paths = {
        "decisionReview": (f"/api/v1/portfolio/{portfolio_item_id}/decision-review"),
        "portfolioImpacts": (f"/api/v1/portfolio/{portfolio_item_id}/impacts"),
        "analysisPacket": (f"/api/v1/portfolio/{portfolio_item_id}/analysis-packet"),
        "briefing": (f"/api/v1/briefings/{briefing_id}"),
    }

    output: dict[str, object] = {}

    for name, path in paths.items():
        response = client.get(path)

        assert response.status_code == 200, (
            name,
            response.status_code,
            response.text,
        )

        output[name] = response.json()

    return output


def test_analyst_reference_import_does_not_change_analysis(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        portfolio = _portfolio()
        session.add(portfolio)
        session.flush()

        portfolio_id = portfolio.id

        analysis_service = AnalysisService(session)
        review = analysis_service.refresh_review(
            portfolio_id,
            manual_reference_price=None,
        )

        briefing_result = BriefingService(session).generate(
            period_start=NOW - timedelta(hours=1),
            period_end=NOW,
            now=NOW,
            include_no_change=True,
            idempotency_key_override=("ANALYST_REFERENCE_ISOLATION_20260729"),
        )

        review_id = review.id
        briefing_id = briefing_result.briefing.id

    counts_before = _table_counts(api_database)
    outputs_before = _analysis_outputs(
        api_client,
        portfolio_item_id=portfolio_id,
        briefing_id=briefing_id,
    )

    assert counts_before == {
        "analystReferences": 0,
        "analystCoverages": 0,
        "decisionReviews": 1,
        "portfolioImpacts": 0,
        "briefings": 1,
    }
    assert outputs_before["decisionReview"]["id"] == review_id

    preview_response = api_client.post(
        "/api/v1/analyst-references/import-link",
        json=_import_payload(
            portfolio_item_id=portfolio_id,
            confirm=False,
        ),
    )

    assert preview_response.status_code == 200
    assert preview_response.json()["confirmed"] is False
    assert preview_response.json()["wouldCreate"] is True

    counts_after_preview = _table_counts(api_database)
    outputs_after_preview = _analysis_outputs(
        api_client,
        portfolio_item_id=portfolio_id,
        briefing_id=briefing_id,
    )

    assert counts_after_preview == counts_before
    assert outputs_after_preview == outputs_before

    confirm_response = api_client.post(
        "/api/v1/analyst-references/import-link",
        json=_import_payload(
            portfolio_item_id=portfolio_id,
            confirm=True,
        ),
    )

    assert confirm_response.status_code == 201
    assert confirm_response.json()["confirmed"] is True

    counts_after_confirm = _table_counts(api_database)
    outputs_after_confirm = _analysis_outputs(
        api_client,
        portfolio_item_id=portfolio_id,
        briefing_id=briefing_id,
    )

    assert counts_after_confirm == {
        "analystReferences": 1,
        "analystCoverages": 1,
        "decisionReviews": 1,
        "portfolioImpacts": 0,
        "briefings": 1,
    }

    assert outputs_after_confirm == outputs_before
    assert outputs_after_confirm["decisionReview"]["id"] == review_id
    assert outputs_after_confirm["briefing"]["id"] == briefing_id
