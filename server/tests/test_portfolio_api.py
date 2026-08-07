from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_session
from app.database import Database
from app.models.database import AssetType, HoldingStatus
from app.repositories.portfolio import PortfolioRepository


def _payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "assetType": "EQUITY",
        "symbol": "005930",
        "name": "사용자 입력 종목",
        "market": "KRX",
        "currency": "KRW",
        "holdingStatus": "WATCHLIST",
        "quantity": "0",
        "averagePrice": "0",
        "investmentHorizon": "UNSET",
        "strategy": "",
        "targetAllocation": None,
        "maxLossPercent": None,
        "notes": None,
    }
    values.update(overrides)
    return values


def _create(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post("/api/v1/portfolio", json=_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_portfolio_list_is_empty(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/portfolio")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_portfolio_create_returns_201(api_client: TestClient) -> None:
    created = _create(api_client)
    assert created["assetType"] == "EQUITY"
    assert created["currentPriceAvailability"] == "NOT_CONFIGURED"
    assert created["archivedAt"] is None


def test_portfolio_decimal_precision_is_serialized_as_string(
    api_client: TestClient,
) -> None:
    created = _create(
        api_client,
        holdingStatus="HOLDING",
        quantity="1.000000000000000001",
        averagePrice="123456789012345678.123456789012345678",
    )
    assert created["quantity"] == "1.000000000000000001"
    assert created["averagePrice"] == "123456789012345678.123456789012345678"
    assert Decimal(created["averagePrice"]) == Decimal("123456789012345678.123456789012345678")


def test_portfolio_symbol_and_market_are_normalized(api_client: TestClient) -> None:
    created = _create(api_client, symbol="  aapl  ", market=" nasdaq ")
    assert created["symbol"] == "AAPL"
    assert created["market"] == "NASDAQ"


def test_korean_symbol_keeps_leading_zero(api_client: TestClient) -> None:
    created = _create(api_client, symbol="005930")
    assert created["symbol"] == "005930"


def test_holding_with_positive_quantity_and_price_is_allowed(
    api_client: TestClient,
) -> None:
    created = _create(
        api_client,
        holdingStatus="HOLDING",
        quantity="2",
        averagePrice="71000.25",
    )
    assert created["holdingStatus"] == "HOLDING"


@pytest.mark.parametrize("holding_status", ["WATCHLIST", "REENTRY_WATCH", "SOLD"])
def test_non_holding_status_allows_zero_quantity(
    api_client: TestClient,
    holding_status: str,
) -> None:
    created = _create(api_client, holdingStatus=holding_status, quantity="0")
    assert created["quantity"] == "0"


def test_holding_zero_quantity_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/portfolio",
        json=_payload(holdingStatus="HOLDING", quantity="0", averagePrice="1"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PORTFOLIO_VALIDATION_ERROR"


def test_holding_zero_average_price_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/portfolio",
        json=_payload(holdingStatus="HOLDING", quantity="1", averagePrice="0"),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [("quantity", "-0.1"), ("averagePrice", "-0.1")],
)
def test_negative_portfolio_numbers_are_rejected(
    api_client: TestClient,
    field: str,
    value: str,
) -> None:
    response = api_client.post("/api/v1/portfolio", json=_payload(**{field: value}))
    assert response.status_code == 422


def test_invalid_portfolio_enum_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/portfolio",
        json=_payload(holdingStatus="INVALID"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PORTFOLIO_VALIDATION_ERROR"


def test_duplicate_active_market_symbol_returns_409(api_client: TestClient) -> None:
    _create(api_client, symbol="aapl", market="nasdaq")
    response = api_client.post(
        "/api/v1/portfolio",
        json=_payload(symbol=" AAPL ", market=" NASDAQ "),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PORTFOLIO_DUPLICATE"


def test_same_symbol_in_different_market_is_allowed(api_client: TestClient) -> None:
    _create(api_client, symbol="ABC", market="NYSE")
    created = _create(api_client, symbol="ABC", market="NASDAQ")
    assert created["market"] == "NASDAQ"


def test_crypto_same_symbol_on_upbit_and_binance_is_allowed(
    api_client: TestClient,
) -> None:
    upbit = _create(
        api_client,
        assetType="CRYPTO",
        name="비트코인",
        symbol="BTC",
        market="UPBIT",
        currency="KRW",
        quantity="0.12345678",
    )
    binance = _create(
        api_client,
        assetType="CRYPTO",
        name="비트코인",
        symbol="BTC",
        market="BINANCE",
        currency="USDT",
        quantity="0.00000001",
    )
    assert (upbit["market"], upbit["currency"]) == ("UPBIT", "KRW")
    assert (binance["market"], binance["currency"]) == ("BINANCE", "USDT")
    assert binance["quantity"] == "0.00000001"


@pytest.mark.parametrize(
    ("market", "currency"),
    [("UPBIT", "KRW"), ("BINANCE", "USDT")],
)
def test_crypto_duplicate_on_same_exchange_returns_409(
    api_client: TestClient,
    market: str,
    currency: str,
) -> None:
    crypto = {
        "assetType": "CRYPTO",
        "name": "비트코인",
        "symbol": "BTC",
        "market": market,
        "currency": currency,
    }
    _create(api_client, **crypto)
    response = api_client.post("/api/v1/portfolio", json=_payload(**crypto))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PORTFOLIO_DUPLICATE"


def test_crypto_quantity_rejects_more_than_eight_decimal_places(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/v1/portfolio",
        json=_payload(
            assetType="CRYPTO",
            symbol="BTC",
            name="비트코인",
            market="UPBIT",
            currency="KRW",
            quantity="0.123456789",
        ),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PORTFOLIO_VALIDATION_ERROR"


def test_portfolio_rejects_non_portfolio_asset_type(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/portfolio",
        json=_payload(assetType="INDEX"),
    )
    assert response.status_code == 422


def test_portfolio_get_by_id(api_client: TestClient) -> None:
    created = _create(api_client)
    response = api_client.get(f"/api/v1/portfolio/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_portfolio_missing_id_returns_404(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/portfolio/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"


def test_portfolio_update_succeeds(api_client: TestClient) -> None:
    created = _create(api_client)
    response = api_client.patch(
        f"/api/v1/portfolio/{created['id']}",
        json={
            "name": "수정된 이름",
            "holdingStatus": "HOLDING",
            "quantity": "3",
            "averagePrice": "70000.125",
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "수정된 이름"
    assert response.json()["averagePrice"] == "70000.125"


def test_portfolio_update_normalizes_symbol(api_client: TestClient) -> None:
    created = _create(api_client, symbol="old")
    response = api_client.patch(
        f"/api/v1/portfolio/{created['id']}",
        json={"symbol": " new "},
    )
    assert response.status_code == 200
    assert response.json()["symbol"] == "NEW"


def test_update_revalidates_combined_holding_state(api_client: TestClient) -> None:
    created = _create(api_client)
    response = api_client.patch(
        f"/api/v1/portfolio/{created['id']}",
        json={"holdingStatus": "HOLDING", "quantity": "0", "averagePrice": "1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PORTFOLIO_VALIDATION_ERROR"


def test_delete_archives_and_is_idempotent(api_client: TestClient) -> None:
    created = _create(api_client)
    url = f"/api/v1/portfolio/{created['id']}"
    assert api_client.delete(url).status_code == 204
    assert api_client.delete(url).status_code == 204


def test_archived_item_is_excluded_by_default(api_client: TestClient) -> None:
    created = _create(api_client)
    api_client.delete(f"/api/v1/portfolio/{created['id']}")
    assert api_client.get("/api/v1/portfolio").json()["total"] == 0


def test_include_archived_returns_archived_item(api_client: TestClient) -> None:
    created = _create(api_client)
    api_client.delete(f"/api/v1/portfolio/{created['id']}")
    body = api_client.get(
        "/api/v1/portfolio",
        params={"includeArchived": "true"},
    ).json()
    assert body["total"] == 1
    archived_at = body["items"][0]["archivedAt"]
    assert archived_at is not None
    parsed = datetime.fromisoformat(archived_at.replace("Z", "+00:00"))
    assert parsed.utcoffset().total_seconds() == 0


def test_restore_archived_item(api_client: TestClient) -> None:
    created = _create(api_client)
    api_client.delete(f"/api/v1/portfolio/{created['id']}")
    response = api_client.post(f"/api/v1/portfolio/{created['id']}/restore")
    assert response.status_code == 200
    assert response.json()["archivedAt"] is None


def test_restore_active_item_is_idempotent(api_client: TestClient) -> None:
    created = _create(api_client)
    response = api_client.post(f"/api/v1/portfolio/{created['id']}/restore")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["archivedAt"] is None


def test_restore_conflict_returns_409(api_client: TestClient) -> None:
    archived = _create(api_client, symbol="AAPL", market="NASDAQ")
    api_client.delete(f"/api/v1/portfolio/{archived['id']}")
    _create(api_client, symbol="AAPL", market="NASDAQ", name="새 활성 항목")
    response = api_client.post(f"/api/v1/portfolio/{archived['id']}/restore")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PORTFOLIO_RESTORE_CONFLICT"


def test_portfolio_holding_status_filter(api_client: TestClient) -> None:
    _create(api_client, symbol="AAA", holdingStatus="WATCHLIST")
    _create(
        api_client,
        symbol="BBB",
        holdingStatus="HOLDING",
        quantity="1",
        averagePrice="1",
    )
    body = api_client.get(
        "/api/v1/portfolio",
        params={"holdingStatus": "HOLDING"},
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["symbol"] == "BBB"


def test_portfolio_market_filter(api_client: TestClient) -> None:
    _create(api_client, symbol="AAA", market="NYSE")
    _create(api_client, symbol="BBB", market="NASDAQ")
    body = api_client.get("/api/v1/portfolio", params={"market": " nasdaq "}).json()
    assert body["total"] == 1
    assert body["items"][0]["market"] == "NASDAQ"


def test_portfolio_symbol_query(api_client: TestClient) -> None:
    _create(api_client, symbol="005930")
    _create(api_client, symbol="000660")
    body = api_client.get("/api/v1/portfolio", params={"query": "593"}).json()
    assert body["total"] == 1
    assert body["items"][0]["symbol"] == "005930"


def test_portfolio_limit_has_safe_maximum(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/portfolio", params={"limit": 101})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PORTFOLIO_VALIDATION_ERROR"


def test_portfolio_timestamps_are_utc(api_client: TestClient) -> None:
    created = _create(api_client)
    created_at = datetime.fromisoformat(created["createdAt"].replace("Z", "+00:00"))
    updated_at = datetime.fromisoformat(created["updatedAt"].replace("Z", "+00:00"))
    assert created_at.utcoffset().total_seconds() == 0
    assert updated_at.utcoffset().total_seconds() == 0


def test_repository_counts_active_holding_status(api_database: Database) -> None:
    with api_database.session_scope() as session:
        repository = PortfolioRepository(session)
        repository.create(
            {
                "asset_type": AssetType.EQUITY,
                "symbol": "AAA",
                "name": "사용자 입력 종목",
                "market": "NYSE",
                "currency": "USD",
                "holding_status": HoldingStatus.HOLDING,
                "quantity": Decimal(1),
                "average_price": Decimal(1),
                "investment_horizon": "UNSET",
                "strategy": "",
            }
        )
        assert repository.count_active_by_holding_status(HoldingStatus.HOLDING) == 1


def test_database_error_response_hides_internal_details(
    api_app: FastAPI,
) -> None:
    def broken_session() -> None:
        raise OperationalError(
            "SELECT * FROM secret_table at sqlite:///private/path.db",
            {},
            RuntimeError("password=real-secret"),
        )

    api_app.dependency_overrides[get_session] = broken_session
    with TestClient(api_app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/portfolio")
    assert response.status_code == 503
    encoded = response.text.lower()
    assert response.json()["error"]["code"] == "DATABASE_ERROR"
    assert "select" not in encoded
    assert "private" not in encoded
    assert "password" not in encoded
