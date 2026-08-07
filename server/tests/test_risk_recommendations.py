from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient


def _portfolio_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "assetType": "EQUITY",
        "symbol": f"R{uuid4().hex[:8]}",
        "name": "Risk analysis fixture",
        "market": "NASDAQ",
        "currency": "USD",
        "holdingStatus": "WATCHLIST",
        "trackingStatus": "WATCHLIST",
        "quantity": "0",
        "averagePrice": None,
        "investmentHorizon": "LONG",
        "strategy": "",
        "targetAllocation": None,
        "maxLossPercent": None,
        "notes": None,
    }
    payload.update(overrides)
    return payload


def _create_portfolio(
    client: TestClient,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/portfolio",
        json=_portfolio_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _buy(
    client: TestClient,
    portfolio_id: str,
    *,
    quantity: str,
    unit_price: str,
    day: int = 1,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/portfolio/{portfolio_id}/transactions/buys",
        json={
            "tradedAt": datetime(
                2026,
                7,
                day,
                9,
                tzinfo=UTC,
            ).isoformat(),
            "quantity": quantity,
            "unitPrice": unit_price,
            "feeAmount": "0",
            "taxAmount": "0",
            "notes": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _answers() -> dict[str, str]:
    return {
        "fundsNeededWithinOneYear": "NO",
        "acceptableLossRange": "FROM_10_TO_20",
        "emergencyFund": "YES",
        "averagingDownPreference": "CONDITIONAL",
    }


def test_unconfirmed_recommendation_does_not_create_risk_profile(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/risk-profile/recommendation")
    assert response.status_code == 200
    recommendation = response.json()
    assert recommendation["confidence"] == "LOW"
    assert recommendation["dataCoverage"]["basis"] == ("PURCHASE_COST_BY_CURRENCY")
    assert recommendation["dataCoverage"]["marketPriceProviderConfigured"] is False
    assert recommendation["minimumCashPercent"] is None
    assert recommendation["requireOfficialEvidenceForAveragingDown"] is True
    assert "CURRENT_CASH_BALANCE" in recommendation["missingInputs"]
    assert "EMERGENCY_FUND" in recommendation["missingInputs"]
    assert api_client.get("/api/v1/risk-profile").json() == {
        "configured": False,
        "profile": None,
    }


def test_cost_concentration_and_crypto_are_analyzed_without_fake_market_data(
    api_client: TestClient,
) -> None:
    equity = _create_portfolio(api_client)
    crypto = _create_portfolio(
        api_client,
        assetType="CRYPTO",
        symbol="BTC",
        name="Bitcoin",
        market="BINANCE",
        currency="USDT",
    )
    _buy(api_client, str(equity["id"]), quantity="9", unit_price="100")
    _buy(api_client, str(crypto["id"]), quantity="1", unit_price="100")

    recommendation = api_client.get("/api/v1/risk-profile/recommendation").json()
    coverage = recommendation["dataCoverage"]
    assert coverage["maxCostConcentrationPercent"] == "100.0000"
    assert coverage["maxCryptoCostSharePercent"] == "100.0000"
    assert Decimal(coverage["costBasisByCurrency"]["USD"]) == Decimal(900)
    assert Decimal(coverage["costBasisByCurrency"]["USDT"]) == Decimal(100)
    assert recommendation["maxSinglePositionPercent"] == "15"
    assert coverage["cryptoPositionCount"] == 1
    assert coverage["structuralHighVolatilityCount"] == 1
    assert coverage["volatilityProviderConfigured"] is False
    assert coverage["assetTypeCounts"] == {"CRYPTO": 1, "EQUITY": 1}
    assert coverage["investmentHorizonCounts"] == {"LONG": 2}
    assert coverage["positionStatusCounts"] == {"HOLDING": 2}
    assert recommendation["confidence"] != "HIGH"


def test_transaction_counts_and_realized_pnl_are_covered(
    api_client: TestClient,
) -> None:
    item = _create_portfolio(api_client)
    _buy(api_client, str(item["id"]), quantity="4", unit_price="100")
    _buy(
        api_client,
        str(item["id"]),
        quantity="1",
        unit_price="120",
        day=2,
    )
    sell = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/sells",
        json={
            "tradedAt": datetime(
                2026,
                7,
                3,
                9,
                tzinfo=UTC,
            ).isoformat(),
            "quantity": "1",
            "unitPrice": "150",
            "feeAmount": "0",
            "taxAmount": "0",
            "notes": None,
        },
    )
    assert sell.status_code == 201, sell.text

    coverage = api_client.get("/api/v1/risk-profile/recommendation").json()["dataCoverage"]
    assert coverage["transactionCount"] == 3
    assert coverage["additionalBuyCount"] == 1
    assert coverage["totalRealizedPnlByCurrency"]["USD"] == ("46.000000000000000000")
    assert coverage["partialSellCount"] == 1
    assert coverage["fullSellCount"] == 0


def test_full_sale_and_tracking_status_are_covered(
    api_client: TestClient,
) -> None:
    item = _create_portfolio(api_client, trackingStatus="REENTRY_WATCH")
    _buy(api_client, str(item["id"]), quantity="1", unit_price="100")
    sell = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/sells",
        json={
            "tradedAt": datetime(
                2026,
                7,
                2,
                9,
                tzinfo=UTC,
            ).isoformat(),
            "quantity": "1",
            "unitPrice": "110",
            "feeAmount": "0",
            "taxAmount": "0",
            "notes": None,
        },
    )
    assert sell.status_code == 201, sell.text
    coverage = api_client.get("/api/v1/risk-profile/recommendation").json()["dataCoverage"]
    assert coverage["fullSellCount"] == 1
    assert coverage["positionStatusCounts"] == {"CLOSED": 1}
    assert coverage["trackingStatusCounts"] == {"REENTRY_WATCH": 1}


def test_answers_raise_confidence_only_to_medium_and_do_not_save(
    api_client: TestClient,
) -> None:
    item = _create_portfolio(api_client)
    _buy(api_client, str(item["id"]), quantity="1", unit_price="100")
    response = api_client.post(
        "/api/v1/risk-profile/recommendation/refresh",
        json={"answers": _answers()},
    )
    assert response.status_code == 200
    recommendation = response.json()
    assert recommendation["confidence"] == "MEDIUM"
    assert recommendation["minimumCashPercent"] == "10"
    assert recommendation["confidence"] != "HIGH"
    assert api_client.get("/api/v1/risk-profile").json()["configured"] is False


def test_partial_answers_keep_low_confidence_and_do_not_infer_income(
    api_client: TestClient,
) -> None:
    item = _create_portfolio(api_client)
    _buy(api_client, str(item["id"]), quantity="1", unit_price="100")
    response = api_client.post(
        "/api/v1/risk-profile/recommendation/refresh",
        json={
            "answers": {
                "fundsNeededWithinOneYear": "NO",
            }
        },
    )
    recommendation = response.json()
    assert recommendation["confidence"] == "LOW"
    assert "EMERGENCY_FUND" in recommendation["missingInputs"]
    encoded = str(recommendation).lower()
    assert "income" not in encoded
    assert "debt" not in encoded


def test_refresh_does_not_overwrite_existing_profile(
    api_client: TestClient,
) -> None:
    saved = api_client.put(
        "/api/v1/risk-profile",
        json={
            "maxPositionPercent": "27",
            "maxPortfolioLossPercent": "14",
            "allowAveragingDown": False,
            "recommendationMode": "UNSET",
        },
    ).json()["profile"]
    response = api_client.post(
        "/api/v1/risk-profile/recommendation/refresh",
        json={"answers": _answers()},
    )
    assert response.status_code == 200
    current = api_client.get("/api/v1/risk-profile").json()["profile"]
    assert current == saved


def test_apply_requires_explicit_current_fingerprint(
    api_client: TestClient,
) -> None:
    item = _create_portfolio(api_client)
    _buy(api_client, str(item["id"]), quantity="1", unit_price="100")
    recommendation = api_client.post(
        "/api/v1/risk-profile/recommendation/refresh",
        json={"answers": _answers()},
    ).json()
    response = api_client.post(
        "/api/v1/risk-profile/recommendation/apply",
        json={
            "answers": _answers(),
            "expectedPortfolioFingerprint": recommendation["portfolioFingerprint"],
            "recommendationVersion": recommendation["recommendationVersion"],
            "mode": "ALL",
        },
    )
    assert response.status_code == 200, response.text
    profile = response.json()["profile"]
    assert profile["source"] == "DATA_ASSISTED"
    assert profile["acknowledgedAt"] is not None
    assert profile["portfolioFingerprint"] == recommendation["portfolioFingerprint"]
    assert profile["recommendationVersion"] == recommendation["recommendationVersion"]


def test_portfolio_change_invalidates_old_apply_without_overwriting_profile(
    api_client: TestClient,
) -> None:
    recommendation = api_client.get("/api/v1/risk-profile/recommendation").json()
    _create_portfolio(api_client)
    response = api_client.post(
        "/api/v1/risk-profile/recommendation/apply",
        json={
            "answers": {},
            "expectedPortfolioFingerprint": recommendation["portfolioFingerprint"],
            "recommendationVersion": recommendation["recommendationVersion"],
            "mode": "ALL",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RISK_RECOMMENDATION_STALE"
    assert api_client.get("/api/v1/risk-profile").json()["configured"] is False


def test_custom_save_clears_data_assisted_acknowledgement(
    api_client: TestClient,
) -> None:
    recommendation = api_client.get("/api/v1/risk-profile/recommendation").json()
    applied = api_client.post(
        "/api/v1/risk-profile/recommendation/apply",
        json={
            "answers": {},
            "expectedPortfolioFingerprint": recommendation["portfolioFingerprint"],
            "recommendationVersion": recommendation["recommendationVersion"],
            "mode": "CHANGED_ONLY",
        },
    )
    assert applied.status_code == 200, applied.text
    response = api_client.put(
        "/api/v1/risk-profile",
        json={
            "maxPositionPercent": "25",
            "maxPortfolioLossPercent": "15",
            "allowAveragingDown": False,
            "recommendationMode": "UNSET",
        },
    )
    profile = response.json()["profile"]
    assert profile["source"] == "CUSTOM"
    assert profile["portfolioFingerprint"] is None
    assert profile["recommendationVersion"] is None


def test_questions_and_openapi_do_not_expose_order_api(
    api_client: TestClient,
) -> None:
    questions = api_client.get("/api/v1/risk-profile/recommendation/questions")
    assert questions.status_code == 200
    assert [item["id"] for item in questions.json()["items"]] == [
        "fundsNeededWithinOneYear",
        "acceptableLossRange",
        "emergencyFund",
        "averagingDownPreference",
    ]
    paths = api_client.get("/openapi.json").json()["paths"]
    assert "/api/v1/risk-profile/recommendation" in paths
    assert "/api/v1/risk-profile/recommendation/refresh" in paths
    assert "/api/v1/risk-profile/recommendation/apply" in paths
    assert "/api/v1/risk-profile/recommendation/questions" in paths
    assert not any("order" in path.lower() for path in paths)


def test_system_info_reports_recommendation_readiness(
    api_client: TestClient,
) -> None:
    system = api_client.get("/api/v1/system/info")
    assert system.status_code == 200
    body = system.json()
    assert body["riskProfileConfigured"] is False
    assert body["riskRecommendationAvailable"] is True
    assert body["riskRecommendationConfidence"] == "LOW"
    assert body["riskRecommendationStale"] is False
    assert body["portfolioFingerprintChanged"] is False


def test_system_info_marks_applied_profile_stale_after_portfolio_change(
    api_client: TestClient,
) -> None:
    recommendation = api_client.get("/api/v1/risk-profile/recommendation").json()
    applied = api_client.post(
        "/api/v1/risk-profile/recommendation/apply",
        json={
            "answers": {},
            "expectedPortfolioFingerprint": recommendation["portfolioFingerprint"],
            "recommendationVersion": recommendation["recommendationVersion"],
            "mode": "ALL",
        },
    )
    assert applied.status_code == 200, applied.text
    _create_portfolio(api_client)
    system = api_client.get("/api/v1/system/info").json()
    assert system["riskProfileConfigured"] is True
    assert system["riskRecommendationStale"] is True
    assert system["portfolioFingerprintChanged"] is True
