from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import Database
from app.models.analysis import (
    DecisionReviewRecord,
    EconomicEventRecord,
    InvestmentThesisRecord,
    PortfolioImpactRecord,
)
from app.models.contracts import VerificationStatus
from app.models.database import (
    Currency,
    PortfolioItemRecord,
    PositionTransactionRecord,
)
from app.models.disclosures import (
    AssetType,
    InformationEventRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    LifecycleStatus,
)

NOW = datetime(2026, 7, 26, 12, tzinfo=UTC)


def _portfolio(client: TestClient, symbol: str = "SKHY") -> dict[str, object]:
    response = client.post(
        "/api/v1/portfolio",
        json={
            "assetType": "ADR",
            "symbol": symbol,
            "name": "SK hynix ADR",
            "market": "NASDAQ",
            "currency": "USD",
            "holdingStatus": "REENTRY_WATCH",
            "trackingStatus": "REENTRY_WATCH",
            "quantity": "0",
            "averagePrice": "101.25",
            "investmentHorizon": "LONG",
            "strategy": "",
            "targetAllocation": None,
            "maxLossPercent": None,
            "notes": "analysis context",
        },
    )
    assert response.status_code == 201
    return response.json()


def _impact(
    database: Database,
    portfolio_item_id: str,
    *,
    direction: str,
    thesis_effect: str,
    verification: VerificationStatus = VerificationStatus.OFFICIAL_CONFIRMED,
    strength: str = "HIGH",
    summary: str = "verified event",
) -> None:
    with database.session_scope() as session:
        item = session.get(PortfolioItemRecord, portfolio_item_id)
        assert item is not None
        if item.instrument_id is None:
            instrument = InstrumentRecord(
                canonical_symbol=f"T{uuid4().hex[:8]}",
                display_name="Analysis fixture",
                market="NASDAQ",
                country="US",
                currency=Currency.USD,
                asset_type=AssetType.EQUITY,
                verification_status=InstrumentVerificationStatus.VERIFIED,
                verified_at=NOW,
            )
            session.add(instrument)
            session.flush()
            item.instrument_id = instrument.id
        event = InformationEventRecord(
            event_key=f"analysis-{uuid4()}",
            instrument_id=item.instrument_id,
            event_type="DISCLOSURE",
            normalized_claim=summary,
            claim_fingerprint=uuid4().hex,
            first_seen_at=NOW,
            last_seen_at=NOW,
            latest_material_change_at=NOW,
            lifecycle_status=(
                LifecycleStatus.STALE
                if verification is VerificationStatus.STALE_REUSED
                else LifecycleStatus.ACTIVE
            ),
            verification_status=verification,
            source_count=1,
            official_source_count=1,
            changed_facts=[{"field": "summary", "value": summary}],
            current_summary=summary,
            material_change=True,
        )
        session.add(event)
        session.flush()
        session.add(
            PortfolioImpactRecord(
                event_id=event.id,
                portfolio_item_id=portfolio_item_id,
                thesis_id=None,
                relevance="DIRECT",
                impact_direction=direction,
                impact_strength=strength,
                impact_horizon="SHORT_TERM",
                thesis_effect=thesis_effect,
                confidence="MEDIUM",
                evidence_strength=strength,
                one_line_summary=summary,
                impact_path=["official evidence", "portfolio impact"],
                supporting_factors=[summary] if direction == "POSITIVE" else [],
                opposing_factors=[summary] if direction != "POSITIVE" else [],
                conditions_to_watch=[f"watch {summary}"],
                invalidation_conditions=[f"invalidate {summary}"],
                missing_information=[],
                source_links=[
                    {
                        "title": f"Official {summary}",
                        "url": f"https://example.invalid/{event.id}",
                        "official": True,
                    }
                ],
                verification_status=verification.value,
                generated_by="RULE_BASED",
                generated_at=NOW,
                valid_until=None,
                human_decision_required=True,
            )
        )


def test_status_summary_and_filters_are_independent(api_client: TestClient) -> None:
    item = _portfolio(api_client)
    item_id = item["id"]
    closed = api_client.patch(
        f"/api/v1/portfolio/{item_id}/context",
        json={
            "positionStatus": "CLOSED",
            "trackingStatus": "REENTRY_WATCH",
            "currentQuantity": "0",
            "averageCost": "101.25",
        },
    )
    assert closed.status_code == 200
    assert closed.json()["positionStatus"] == "CLOSED"
    assert closed.json()["trackingStatus"] == "REENTRY_WATCH"

    summary = api_client.get("/api/v1/portfolio/summary")
    assert summary.status_code == 200
    assert summary.json()["closed"] == 1
    assert summary.json()["reentryWatch"] == 1
    assert summary.json()["holding"] == 0

    by_closed = api_client.get("/api/v1/portfolio", params={"positionStatus": "CLOSED"}).json()[
        "items"
    ]
    by_reentry = api_client.get(
        "/api/v1/portfolio", params={"trackingStatus": "REENTRY_WATCH"}
    ).json()["items"]
    all_items = api_client.get("/api/v1/portfolio").json()["items"]
    assert [entry["id"] for entry in by_closed] == [item_id]
    assert [entry["id"] for entry in by_reentry] == [item_id]
    assert [entry["id"] for entry in all_items].count(item_id) == 1


def test_context_update_does_not_create_or_change_ledger(
    api_client: TestClient, api_database: Database
) -> None:
    item = _portfolio(api_client, "CONTEXT")
    item_id = item["id"]
    with api_database.session_scope() as session:
        before = int(
            session.scalar(
                select(func.count())
                .select_from(PositionTransactionRecord)
                .where(PositionTransactionRecord.portfolio_item_id == item_id)
            )
            or 0
        )
    response = api_client.patch(
        f"/api/v1/portfolio/{item_id}/context",
        json={
            "positionStatus": "HOLDING",
            "trackingStatus": "NONE",
            "currentQuantity": "3.5",
            "averageCost": "88.125",
            "currency": "USD",
            "investmentHorizon": "MEDIUM",
            "memo": "broker app snapshot",
        },
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == "3.5"
    assert response.json()["averagePrice"] == "88.125"
    with api_database.session_scope() as session:
        after = int(
            session.scalar(
                select(func.count())
                .select_from(PositionTransactionRecord)
                .where(PositionTransactionRecord.portfolio_item_id == item_id)
            )
            or 0
        )
    assert before == after == 0


def test_context_holding_and_closed_validation(api_client: TestClient) -> None:
    item = _portfolio(api_client, "VALIDATE")
    item_id = item["id"]
    holding_zero = api_client.patch(
        f"/api/v1/portfolio/{item_id}/context",
        json={"positionStatus": "HOLDING", "currentQuantity": "0"},
    )
    assert holding_zero.status_code == 422
    closed_positive = api_client.patch(
        f"/api/v1/portfolio/{item_id}/context",
        json={"positionStatus": "CLOSED", "currentQuantity": "1"},
    )
    assert closed_positive.status_code == 422


def test_thesis_is_separate_user_owned_record(
    api_client: TestClient, api_database: Database
) -> None:
    item = _portfolio(api_client, "THESIS")
    item_id = item["id"]
    unset = api_client.get(f"/api/v1/portfolio/{item_id}/thesis")
    assert unset.status_code == 200
    assert unset.json()["id"] is None
    assert unset.json()["thesisStatus"] == "NOT_SET"

    payload = {
        "thesisSummary": "HBM demand and execution",
        "investmentPurpose": "long-term semiconductor exposure",
        "investmentHorizon": "LONG",
        "originalReasons": ["official capacity expansion"],
        "expectedCatalysts": ["earnings confirmation"],
        "keyRisks": ["customer concentration"],
        "conditionsToAdd": ["official guidance strengthens"],
        "conditionsToHold": ["thesis remains intact"],
        "conditionsToReduce": ["execution delay repeats"],
        "conditionsToExit": ["core guidance withdrawn"],
        "invalidationConditions": ["liquidity risk confirmed"],
        "questionsToVerify": ["next official filing"],
        "userConviction": "MEDIUM",
        "thesisStatus": "ACTIVE",
    }
    saved = api_client.put(f"/api/v1/portfolio/{item_id}/thesis", json=payload)
    assert saved.status_code == 200
    assert saved.json()["thesisSummary"] == payload["thesisSummary"]
    with api_database.session_scope() as session:
        assert session.scalar(select(func.count()).select_from(InvestmentThesisRecord)) == 1
        portfolio = session.get(PortfolioItemRecord, item_id)
        assert portfolio is not None
        assert portfolio.notes == "analysis context"


def test_rule_based_review_and_packet_have_human_guardrails(
    api_client: TestClient, api_database: Database
) -> None:
    item = _portfolio(api_client, "PACKET")
    item_id = item["id"]
    api_client.put(
        f"/api/v1/portfolio/{item_id}/thesis",
        json={
            "thesisSummary": "User-authored thesis",
            "investmentPurpose": "",
            "investmentHorizon": "LONG",
            "originalReasons": ["user reason"],
            "expectedCatalysts": [],
            "keyRisks": ["execution"],
            "conditionsToAdd": ["official evidence"],
            "conditionsToHold": [],
            "conditionsToReduce": [],
            "conditionsToExit": ["thesis invalidated"],
            "invalidationConditions": ["official denial"],
            "questionsToVerify": ["What changed?"],
            "userConviction": "MEDIUM",
            "thesisStatus": "ACTIVE",
        },
    )
    refreshed = api_client.post(f"/api/v1/portfolio/{item_id}/decision-review/refresh", json={})
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["direction"] == "INSUFFICIENT_DATA"
    assert body["thesisStatus"] == "NOT_SET"
    assert body["whyNow"] == "연결된 공식 공시와 검증 정보가 부족합니다."
    assert body["generatedBy"] == "RULE_BASED"
    assert body["humanDecisionRequired"] is True
    assert "targetPrice" not in body
    assert "probability" not in body
    repeated = api_client.post(f"/api/v1/portfolio/{item_id}/decision-review/refresh", json={})
    assert repeated.status_code == 200
    assert repeated.json()["id"] == body["id"]

    packet = api_client.get(f"/api/v1/portfolio/{item_id}/analysis-packet")
    assert packet.status_code == 200
    packet_body = packet.json()
    assert packet_body["articleFullTextIncluded"] is False
    assert packet_body["humanDecisionRequired"] is True
    assert "현재가와 주문은 제가 별도 금융 앱에서 확인합니다." in packet_body["copyText"]
    with api_database.session_scope() as session:
        review = session.scalar(select(DecisionReviewRecord))
        assert review is not None
        assert review.human_decision_required is True


@pytest.mark.parametrize(
    ("direction", "effect", "verification", "expected_direction", "status"),
    [
        (
            "POSITIVE",
            "STRENGTHENS",
            VerificationStatus.OFFICIAL_CONFIRMED,
            "HOLD",
            "ACTIVE",
        ),
        (
            "NEGATIVE",
            "WEAKENS",
            VerificationStatus.OFFICIAL_CONFIRMED,
            "REDUCE_REVIEW",
            "WEAKENED",
        ),
        (
            "MIXED",
            "NO_CHANGE",
            VerificationStatus.MULTI_SOURCE_CONFIRMED,
            "WAIT",
            "REVIEW_REQUIRED",
        ),
        (
            "UNCLEAR",
            "NO_CHANGE",
            VerificationStatus.CORRECTED,
            "WAIT",
            "REVIEW_REQUIRED",
        ),
        (
            "UNCLEAR",
            "NO_CHANGE",
            VerificationStatus.OFFICIALLY_DENIED,
            "WAIT",
            "REVIEW_REQUIRED",
        ),
        (
            "MIXED",
            "NO_CHANGE",
            VerificationStatus.CONFLICTING,
            "WAIT",
            "REVIEW_REQUIRED",
        ),
        (
            "POSITIVE",
            "STRENGTHENS",
            VerificationStatus.STALE_REUSED,
            "INSUFFICIENT_DATA",
            "NOT_SET",
        ),
    ],
)
def test_review_uses_only_current_verified_evidence(
    api_client: TestClient,
    api_database: Database,
    direction: str,
    effect: str,
    verification: VerificationStatus,
    expected_direction: str,
    status: str,
) -> None:
    item = _portfolio(api_client, f"E{uuid4().hex[:7]}")
    _impact(
        api_database,
        str(item["id"]),
        direction=direction,
        thesis_effect=effect,
        verification=verification,
    )
    body = api_client.get(f"/api/v1/portfolio/{item['id']}/decision-review").json()
    assert body["direction"] == expected_direction
    assert body["thesisStatus"] == status
    assert body["generatedBy"] == "RULE_BASED"
    assert body["humanDecisionRequired"] is True


def test_multiple_official_positive_events_strengthen_without_user_thesis(
    api_client: TestClient, api_database: Database
) -> None:
    item = _portfolio(api_client, "TWO-POS")
    for number in (1, 2):
        _impact(
            api_database,
            str(item["id"]),
            direction="POSITIVE",
            thesis_effect="STRENGTHENS",
            summary=f"positive event {number}",
        )
    body = api_client.get(f"/api/v1/portfolio/{item['id']}/decision-review").json()
    assert body["direction"] == "ADD_REVIEW"
    assert body["thesisStatus"] == "STRENGTHENED"
    assert len(body["positiveFactors"]) == 2


def test_refresh_is_idempotent_and_preserves_user_thesis(
    api_client: TestClient, api_database: Database
) -> None:
    item = _portfolio(api_client, "IDEMPOTENT")
    item_id = str(item["id"])
    thesis_payload = {
        "thesisSummary": "legacy user value",
        "investmentPurpose": "legacy purpose",
        "investmentHorizon": "LONG",
        "originalReasons": ["legacy reason"],
        "expectedCatalysts": [],
        "keyRisks": [],
        "conditionsToAdd": [],
        "conditionsToHold": [],
        "conditionsToReduce": [],
        "conditionsToExit": [],
        "invalidationConditions": [],
        "questionsToVerify": [],
        "userConviction": "HIGH",
        "thesisStatus": "ACTIVE",
    }
    assert (
        api_client.put(f"/api/v1/portfolio/{item_id}/thesis", json=thesis_payload).status_code
        == 200
    )
    first = api_client.post(
        f"/api/v1/portfolio/{item_id}/decision-review/refresh", json={}
    ).json()
    second = api_client.post(
        f"/api/v1/portfolio/{item_id}/decision-review/refresh", json={}
    ).json()
    assert second["id"] == first["id"]
    assert second["generatedAt"] == first["generatedAt"]
    assert second["direction"] == "INSUFFICIENT_DATA"
    with api_database.session_scope() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DecisionReviewRecord)
                .where(DecisionReviewRecord.portfolio_item_id == item_id)
            )
            == 1
        )
        thesis = session.scalar(
            select(InvestmentThesisRecord).where(
                InvestmentThesisRecord.portfolio_item_id == item_id
            )
        )
        assert thesis is not None
        assert thesis.thesis_summary == "legacy user value"
        assert thesis.user_conviction == "HIGH"
        assert thesis.thesis_status == "ACTIVE"


def test_economic_event_import_preview_confirm_duplicate_and_confirmation_guard(
    api_client: TestClient,
    api_database: Database,
) -> None:
    item = _portfolio(api_client, "ECONOMIC-EVENT")
    item_id = item["id"]
    payload = {
        "eventType": "COMPANY_EARNINGS",
        "title": "Microsoft FY2099 Q1 earnings release",
        "scheduledAt": "2099-10-28T21:30:00+09:00",
        "officialSourceName": "Microsoft Investor Relations",
        "officialSourceUrl": (
            "https://www.microsoft.com/en-us/Investor/events/"
            "fy-2099-q1-earnings?utm_source=recording#schedule"
        ),
        "portfolioItemIds": [item_id],
        "expectedImpactPath": [
            "실적 발표",
            "클라우드·AI 성장 확인",
            "등록 종목 관리 방향 재검토",
        ],
        "preReleaseChecks": [
            "공식 IR 일정 재확인",
            "발표 자료 공개 여부 확인",
        ],
        "officialSourceConfirmed": True,
        "confirm": False,
    }

    with api_database.session_scope() as session:
        before = int(session.scalar(select(func.count()).select_from(EconomicEventRecord)) or 0)

    preview_response = api_client.post(
        "/api/v1/economic-events/import-link",
        json=payload,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["confirmed"] is False
    assert preview["wouldCreate"] is True
    assert preview["canConfirm"] is True
    assert preview["duplicate"]["duplicate"] is False
    assert preview["sourceDomain"] == "www.microsoft.com"
    assert "utm_source" not in preview["normalizedUrl"]
    assert "#" not in preview["normalizedUrl"]
    assert preview["portfolioItems"][0]["id"] == item_id

    with api_database.session_scope() as session:
        after_preview = int(
            session.scalar(select(func.count()).select_from(EconomicEventRecord)) or 0
        )
    assert after_preview == before

    confirm_response = api_client.post(
        "/api/v1/economic-events/import-link",
        json={**payload, "confirm": True},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    confirmed = confirm_response.json()
    assert confirmed["confirmed"] is True
    assert confirmed["event"]["eventType"] == "COMPANY_EARNINGS"
    assert confirmed["event"]["relatedPortfolioItemIds"] == [item_id]
    assert confirmed["event"]["expectedImpactPath"] == payload["expectedImpactPath"]
    assert confirmed["event"]["preReleaseChecks"] == payload["preReleaseChecks"]

    listing = api_client.get("/api/v1/economic-events")
    upcoming = api_client.get("/api/v1/economic-events/upcoming")
    assert listing.status_code == 200
    assert upcoming.status_code == 200
    assert listing.json()["total"] == 1
    assert upcoming.json()["total"] == 1

    duplicate_response = api_client.post(
        "/api/v1/economic-events/import-link",
        json=payload,
    )
    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["confirmed"] is False
    assert duplicate["wouldCreate"] is False
    assert duplicate["canConfirm"] is False
    assert duplicate["duplicate"]["duplicate"] is True

    duplicate_confirm = api_client.post(
        "/api/v1/economic-events/import-link",
        json={**payload, "confirm": True},
    )
    assert duplicate_confirm.status_code == 409

    unconfirmed_payload = {
        **payload,
        "officialSourceUrl": "https://www.microsoft.com/en-us/Investor/events/other",
        "title": "Other official schedule",
        "officialSourceConfirmed": False,
        "confirm": True,
    }
    unconfirmed_response = api_client.post(
        "/api/v1/economic-events/import-link",
        json=unconfirmed_payload,
    )
    assert unconfirmed_response.status_code == 422


def test_analysis_read_apis_return_empty_structures(api_client: TestClient) -> None:
    item = _portfolio(api_client, "EMPTY")
    item_id = item["id"]
    for path in (
        f"/api/v1/portfolio/{item_id}/impacts",
        "/api/v1/impacts",
        "/api/v1/decision-reviews",
        "/api/v1/economic-events",
        "/api/v1/economic-events/upcoming",
    ):
        response = api_client.get(path)
        assert response.status_code == 200
        assert "items" in response.json()


def test_context_decimal_precision_is_string(api_client: TestClient) -> None:
    item = _portfolio(api_client, "DECIMAL")
    response = api_client.patch(
        f"/api/v1/portfolio/{item['id']}/context",
        json={
            "positionStatus": "HOLDING",
            "trackingStatus": "NONE",
            "currentQuantity": "0.00000001",
            "averageCost": "123456789.123456789123456789",
        },
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == "0.00000001"
    assert response.json()["averagePrice"] == "123456789.123456789123456789"


def test_openapi_exposes_analysis_only_and_deprecates_quotes(
    api_client: TestClient,
) -> None:
    document = api_client.get("/openapi.json").json()
    paths = document["paths"]
    required = {
        "/api/v1/portfolio/summary",
        "/api/v1/portfolio/{item_id}/context",
        "/api/v1/portfolio/{item_id}/thesis",
        "/api/v1/portfolio/{item_id}/impacts",
        "/api/v1/events/{event_id}/impacts",
        "/api/v1/impacts",
        "/api/v1/portfolio/{item_id}/decision-review",
        "/api/v1/decision-reviews",
        "/api/v1/portfolio/{item_id}/decision-review/refresh",
        "/api/v1/portfolio/{item_id}/decision-review/acknowledge",
        "/api/v1/portfolio/{item_id}/analysis-packet",
        "/api/v1/economic-events",
        "/api/v1/economic-events/upcoming",
        "/api/v1/economic-events/import-link",
    }
    assert required <= set(paths)
    assert paths["/api/v1/quotes/latest"]["get"]["deprecated"] is True
    assert paths["/api/v1/portfolio/{portfolio_id}/quote"]["get"]["deprecated"] is True
    assert not any(
        token in path.lower()
        for path in paths
        for token in ("/order", "/account", "/auto-buy", "/auto-sell")
    )
