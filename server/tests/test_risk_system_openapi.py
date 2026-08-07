from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.core.config import Settings
from app.database import Database
from app.main import create_app


def _risk_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "maxPositionPercent": "20.1250",
        "maxPortfolioLossPercent": "10.5000",
        "defaultStopLossPercent": "5.2500",
        "defaultTakeProfitPercent": "15.7500",
        "maxSingleTradeAmount": "123456789012345678.123456789012345678",
        "cashReservePercent": "30.0000",
        "allowAveragingDown": False,
        "recommendationMode": "CONSERVATIVE",
    }
    values.update(overrides)
    return values


def test_risk_profile_is_unconfigured_without_fake_defaults(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/risk-profile")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "profile": None}


def test_risk_profile_create(api_client: TestClient) -> None:
    response = api_client.put("/api/v1/risk-profile", json=_risk_payload())
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["profile"]["recommendationMode"] == "CONSERVATIVE"


def test_risk_profile_replace(api_client: TestClient) -> None:
    api_client.put("/api/v1/risk-profile", json=_risk_payload())
    response = api_client.put(
        "/api/v1/risk-profile",
        json=_risk_payload(
            maxPositionPercent="25.0000",
            recommendationMode="BALANCED",
            allowAveragingDown=True,
        ),
    )
    profile = response.json()["profile"]
    assert profile["maxPositionPercent"] == "25.0000"
    assert profile["recommendationMode"] == "BALANCED"
    assert profile["allowAveragingDown"] is True


def test_risk_profile_decimal_precision(api_client: TestClient) -> None:
    response = api_client.put("/api/v1/risk-profile", json=_risk_payload())
    assert (
        response.json()["profile"]["maxSingleTradeAmount"]
        == "123456789012345678.123456789012345678"
    )


def test_risk_profile_negative_amount_is_rejected(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/risk-profile",
        json=_risk_payload(maxSingleTradeAmount="-1"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RISK_PROFILE_VALIDATION_ERROR"


def test_risk_profile_percent_range_is_rejected(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/risk-profile",
        json=_risk_payload(maxPositionPercent="100.0001"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RISK_PROFILE_VALIDATION_ERROR"


def test_risk_profile_invalid_mode_is_rejected(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/risk-profile",
        json=_risk_payload(recommendationMode="AUTOMATIC"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RISK_PROFILE_VALIDATION_ERROR"


def test_risk_profile_does_not_return_recommendations_or_orders(
    api_client: TestClient,
) -> None:
    profile = api_client.put("/api/v1/risk-profile", json=_risk_payload()).json()
    encoded = str(profile).lower()
    assert "recommendationtype" not in encoded
    assert "order" not in encoded


def test_system_info_reports_configured_and_reachable_database(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/system/info")
    body = response.json()
    assert body["databaseConfigured"] is True
    assert body["databaseReachable"] is True
    assert body["databaseType"] == "SQLITE"
    assert body["aiAutomationEnabled"] is False
    assert body["automaticTradingEnabled"] is False


def test_system_info_distinguishes_unreachable_database(
    api_database: Database,
) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    api_database.reachable = lambda: False  # type: ignore[method-assign]
    app = create_app(settings, database=api_database)
    with TestClient(app) as client:
        body = client.get("/api/v1/system/info").json()
    assert body["databaseConfigured"] is True
    assert body["databaseReachable"] is False


def test_openapi_schema_contains_phase_1b_routes(api_client: TestClient) -> None:
    response = api_client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    paths = document["paths"]
    assert "/api/v1/portfolio" in paths
    assert "/api/v1/portfolio/{item_id}" in paths
    assert "/api/v1/portfolio/{item_id}/restore" in paths
    assert "/api/v1/risk-profile" in paths
    assert not any("order" in path.lower() or "trade" in path.lower() for path in paths)
    schemas = document["components"]["schemas"]
    assert "assetType" in schemas["PortfolioCreate"]["required"]
    assert "USDT" in schemas["Currency"]["enum"]


def test_app_start_does_not_create_database_schema() -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    database = Database(settings.database_url)
    create_app(settings, database=database)
    assert inspect(database.engine).get_table_names() == []
