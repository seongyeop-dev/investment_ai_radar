from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.sales import calculate_sale_values

SOLD_AT = "2026-07-25T12:00:00Z"


def portfolio_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "assetType": "EQUITY",
        "symbol": "SALE",
        "name": "매도 테스트",
        "market": "NASDAQ",
        "currency": "USD",
        "holdingStatus": "HOLDING",
        "quantity": "3",
        "averagePrice": "100",
        "investmentHorizon": "UNSET",
        "strategy": "",
        "targetAllocation": None,
        "maxLossPercent": None,
        "notes": None,
    }
    values.update(overrides)
    return values


def create_portfolio(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post("/api/v1/portfolio", json=portfolio_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def sale_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "soldAt": SOLD_AT,
        "quantity": "1",
        "salePrice": "130",
        "feeAmount": "2",
        "taxAmount": "3",
        "notes": "사용자 입력",
    }
    values.update(overrides)
    return values


def create_sale(
    client: TestClient,
    portfolio_id: str,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/portfolio/{portfolio_id}/sales",
        json=sale_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("sale_price", "fee", "tax", "expected_pnl", "expected_return"),
    [
        ("130", "2", "3", Decimal("25"), Decimal("25")),
        ("90", "1", "2", Decimal("-13"), Decimal("-13")),
    ],
)
def test_decimal_sale_calculation_positive_and_negative(
    sale_price: str,
    fee: str,
    tax: str,
    expected_pnl: Decimal,
    expected_return: Decimal,
) -> None:
    result = calculate_sale_values(
        quantity=Decimal("1"),
        sale_price=Decimal(sale_price),
        purchase_average_price=Decimal("100"),
        fee_amount=Decimal(fee),
        tax_amount=Decimal(tax),
    )
    assert result["gross_proceeds"] == Decimal(sale_price)
    assert result["cost_basis"] == Decimal("100")
    assert result["realized_pnl"] == expected_pnl
    assert result["realized_return_percent"] == expected_return


def test_zero_cost_basis_has_no_realized_return() -> None:
    result = calculate_sale_values(
        quantity=Decimal("1"),
        sale_price=Decimal("1"),
        purchase_average_price=Decimal("0"),
        fee_amount=Decimal("0"),
        tax_amount=Decimal("0"),
    )
    assert result["cost_basis"] == 0
    assert result["realized_return_percent"] is None


def test_partial_sale_reduces_quantity_and_preserves_average_price(
    api_client: TestClient,
) -> None:
    portfolio = create_portfolio(api_client)
    sale = create_sale(api_client, str(portfolio["id"]))
    updated = api_client.get(f"/api/v1/portfolio/{portfolio['id']}").json()

    assert sale["transactionType"] == "PARTIAL_SALE"
    assert sale["quantityBefore"] == "3"
    assert sale["quantityAfter"] == "2.000000000000000000"
    assert sale["purchaseAveragePriceSnapshot"] == "100"
    assert sale["grossProceeds"] == "130.000000000000000000"
    assert sale["realizedPnl"] == "25.000000000000000000"
    assert updated["quantity"] == "2.000000000000000000"
    assert updated["holdingStatus"] == "HOLDING"
    assert updated["averagePrice"] == "100"


def test_full_sale_sets_sold_and_summary(api_client: TestClient) -> None:
    portfolio = create_portfolio(api_client, quantity="1")
    sale = create_sale(api_client, str(portfolio["id"]))
    updated = api_client.get(f"/api/v1/portfolio/{portfolio['id']}").json()

    assert sale["transactionType"] == "FULL_SALE"
    assert updated["quantity"] == "0E-18" or updated["quantity"] == "0.000000000000000000"
    assert updated["holdingStatus"] == "SOLD"
    assert updated["activeSaleCount"] == 1
    assert updated["weightedAverageSalePrice"] == "130.000000000000000000"
    assert updated["totalRealizedPnl"] == "25.000000000000000000"


def test_multiple_sales_use_weighted_average_and_aggregate_costs(
    api_client: TestClient,
) -> None:
    portfolio = create_portfolio(api_client)
    create_sale(
        api_client,
        str(portfolio["id"]),
        quantity="1",
        salePrice="100",
        feeAmount="1",
        taxAmount="2",
    )
    create_sale(
        api_client,
        str(portfolio["id"]),
        quantity="2",
        salePrice="200",
        feeAmount="3",
        taxAmount="4",
    )
    summary = api_client.get(f"/api/v1/portfolio/{portfolio['id']}/sale-summary").json()
    assert summary["activeSaleCount"] == 2
    assert summary["totalSoldQuantity"] == "3.000000000000000000"
    assert summary["totalGrossProceeds"] == "500.000000000000000000"
    assert summary["weightedAverageSalePrice"] == "166.666666666666666667"
    assert summary["totalFeeAmount"] == "4.000000000000000000"
    assert summary["totalTaxAmount"] == "6.000000000000000000"
    assert summary["totalRealizedPnl"] == "190.000000000000000000"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity", "0"),
        ("quantity", "-1"),
        ("salePrice", "0"),
        ("feeAmount", "-1"),
        ("taxAmount", "-1"),
    ],
)
def test_invalid_sale_numbers_are_rejected(
    api_client: TestClient,
    field: str,
    value: str,
) -> None:
    portfolio = create_portfolio(api_client)
    response = api_client.post(
        f"/api/v1/portfolio/{portfolio['id']}/sales",
        json=sale_payload(**{field: value}),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SALE_VALIDATION_ERROR"


def test_sale_quantity_exceeding_holding_is_rejected(api_client: TestClient) -> None:
    portfolio = create_portfolio(api_client)
    response = api_client.post(
        f"/api/v1/portfolio/{portfolio['id']}/sales",
        json=sale_payload(quantity="4"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SALE_QUANTITY_EXCEEDS_HOLDING"


@pytest.mark.parametrize("status", ["WATCHLIST", "REENTRY_WATCH"])
def test_non_holding_portfolio_sale_is_rejected(
    api_client: TestClient,
    status: str,
) -> None:
    portfolio = create_portfolio(
        api_client,
        holdingStatus=status,
        quantity="0",
        averagePrice=None,
    )
    response = api_client.post(
        f"/api/v1/portfolio/{portfolio['id']}/sales",
        json=sale_payload(),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PORTFOLIO_NOT_HOLDING"


def test_sale_update_recalculates_and_quantity_is_immutable(
    api_client: TestClient,
) -> None:
    portfolio = create_portfolio(api_client)
    sale = create_sale(api_client, str(portfolio["id"]))
    response = api_client.patch(
        f"/api/v1/portfolio/{portfolio['id']}/sales/{sale['id']}",
        json={"salePrice": "150", "feeAmount": "5"},
    )
    assert response.status_code == 200
    assert response.json()["realizedPnl"] == "42.000000000000000000"

    immutable = api_client.patch(
        f"/api/v1/portfolio/{portfolio['id']}/sales/{sale['id']}",
        json={"quantity": "2"},
    )
    assert immutable.status_code == 409
    assert immutable.json()["error"]["code"] == "SALE_QUANTITY_IMMUTABLE"


def test_latest_sale_void_restores_quantity_and_sold_status(
    api_client: TestClient,
) -> None:
    portfolio = create_portfolio(api_client, quantity="1")
    sale = create_sale(api_client, str(portfolio["id"]))
    response = api_client.post(
        f"/api/v1/portfolio/{portfolio['id']}/sales/{sale['id']}/void",
        json={"reason": "입력 오류"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "VOIDED"
    restored = api_client.get(f"/api/v1/portfolio/{portfolio['id']}").json()
    assert restored["quantity"] == "1.000000000000000000"
    assert restored["holdingStatus"] == "HOLDING"
    assert restored["activeSaleCount"] == 0


def test_older_sale_cannot_be_voided_and_duplicate_void_is_rejected(
    api_client: TestClient,
) -> None:
    portfolio = create_portfolio(api_client)
    first = create_sale(api_client, str(portfolio["id"]))
    second = create_sale(api_client, str(portfolio["id"]))
    older = api_client.post(
        f"/api/v1/portfolio/{portfolio['id']}/sales/{first['id']}/void",
        json={"reason": "과거 건"},
    )
    assert older.status_code == 409
    assert older.json()["error"]["code"] == "SALE_VOID_NOT_LATEST"
    path = f"/api/v1/portfolio/{portfolio['id']}/sales/{second['id']}/void"
    assert api_client.post(path, json={"reason": "수정"}).status_code == 200
    duplicate = api_client.post(path, json={"reason": "다시"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "SALE_ALREADY_VOIDED"


def historical_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "assetType": "EQUITY",
        "symbol": f"H{uuid4().hex[:6]}",
        "name": "과거 매도",
        "market": "NYSE",
        "currency": "USD",
        "averagePrice": "100",
        "totalSoldQuantity": "3",
        "investmentHorizon": "UNSET",
        "strategy": "",
        "targetAllocation": None,
        "maxLossPercent": None,
        "notes": None,
        "sales": [
            {
                "soldAt": "2025-01-01T00:00:00Z",
                "quantity": "1",
                "salePrice": "120",
                "feeAmount": "1",
                "taxAmount": "0",
                "notes": "1차",
            },
            {
                "soldAt": "2025-02-01T00:00:00Z",
                "quantity": "2",
                "salePrice": "150",
                "feeAmount": "2",
                "taxAmount": "3",
                "notes": "2차",
            },
        ],
    }
    values.update(overrides)
    return values


def test_historical_multiple_sales_create_sold_portfolio(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/v1/portfolio/historical-sale",
        json=historical_payload(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["sales"]) == 2
    assert all(sale["historicalImport"] for sale in body["sales"])
    assert body["saleSummary"]["totalSoldQuantity"] == "3.000000000000000000"
    portfolio = api_client.get(f"/api/v1/portfolio/{body['portfolioId']}").json()
    assert portfolio["holdingStatus"] == "SOLD"
    assert Decimal(portfolio["quantity"]) == 0


def test_historical_quantity_mismatch_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/portfolio/historical-sale",
        json=historical_payload(totalSoldQuantity="4"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "HISTORICAL_SALE_QUANTITY_MISMATCH"


def test_historical_void_does_not_change_portfolio_quantity(
    api_client: TestClient,
) -> None:
    created = api_client.post(
        "/api/v1/portfolio/historical-sale",
        json=historical_payload(),
    ).json()
    sale = created["sales"][0]
    response = api_client.post(
        f"/api/v1/portfolio/{created['portfolioId']}/sales/{sale['id']}/void",
        json={"reason": "과거 기록 정정"},
    )
    assert response.status_code == 200
    portfolio = api_client.get(f"/api/v1/portfolio/{created['portfolioId']}").json()
    assert Decimal(portfolio["quantity"]) == 0
    assert portfolio["holdingStatus"] == "SOLD"


def test_historical_sale_can_supplement_existing_sold_portfolio(
    api_client: TestClient,
) -> None:
    created = api_client.post(
        "/api/v1/portfolio/historical-sale",
        json=historical_payload(
            totalSoldQuantity="1",
            sales=[
                {
                    "soldAt": "2025-01-01T00:00:00Z",
                    "quantity": "1",
                    "salePrice": "120",
                    "feeAmount": "0",
                    "taxAmount": "0",
                    "notes": None,
                }
            ],
        ),
    ).json()
    response = api_client.post(
        f"/api/v1/portfolio/{created['portfolioId']}/historical-sales",
        json=sale_payload(
            soldAt="2025-02-01T00:00:00Z",
            quantity="2",
            salePrice="130",
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["transactionType"] == "HISTORICAL_SALE"
    portfolio = api_client.get(f"/api/v1/portfolio/{created['portfolioId']}").json()
    assert portfolio["holdingStatus"] == "SOLD"
    assert Decimal(portfolio["quantity"]) == 0
    assert portfolio["activeSaleCount"] == 2
    assert portfolio["totalSoldQuantity"] == "3.000000000000000000"


def test_sale_list_detail_and_missing(api_client: TestClient) -> None:
    portfolio = create_portfolio(api_client)
    sale = create_sale(api_client, str(portfolio["id"]))
    listed = api_client.get(f"/api/v1/portfolio/{portfolio['id']}/sales").json()
    assert listed["total"] == 1
    assert (
        api_client.get(f"/api/v1/portfolio/{portfolio['id']}/sales/{sale['id']}").status_code
        == 200
    )
    missing = api_client.get(f"/api/v1/portfolio/{portfolio['id']}/sales/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SALE_NOT_FOUND"


def test_future_sale_is_rejected(api_client: TestClient) -> None:
    portfolio = create_portfolio(api_client)
    future = datetime(2099, 1, 1, tzinfo=UTC).isoformat()
    response = api_client.post(
        f"/api/v1/portfolio/{portfolio['id']}/sales",
        json=sale_payload(soldAt=future),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SALE_VALIDATION_ERROR"


def test_crypto_sale_precision_and_usdt_serialization(api_client: TestClient) -> None:
    portfolio = create_portfolio(
        api_client,
        assetType="CRYPTO",
        symbol="BTC",
        market="BINANCE",
        currency="USDT",
        quantity="0.12345678",
        averagePrice="100000.12345678",
    )
    sale = create_sale(
        api_client,
        str(portfolio["id"]),
        quantity="0.00000001",
        salePrice="110000.12345678",
        feeAmount="0.00000001",
        taxAmount="0",
    )
    assert sale["currency"] == "USDT"
    assert sale["quantity"] == "0.00000001"
    rejected = api_client.post(
        f"/api/v1/portfolio/{portfolio['id']}/sales",
        json=sale_payload(quantity="0.000000001"),
    )
    assert rejected.status_code == 422


def test_holding_cannot_be_manually_changed_to_sold(api_client: TestClient) -> None:
    portfolio = create_portfolio(api_client)
    response = api_client.patch(
        f"/api/v1/portfolio/{portfolio['id']}",
        json={"holdingStatus": "SOLD", "quantity": "0"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PORTFOLIO_VALIDATION_ERROR"
