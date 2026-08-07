from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient


def portfolio_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "assetType": "EQUITY",
        "symbol": f"T{uuid4().hex[:8]}",
        "name": "Ledger fixture",
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


def transaction_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tradedAt": datetime(2026, 7, 1, 9, 0, tzinfo=UTC).isoformat(),
        "quantity": "4",
        "unitPrice": "100",
        "feeAmount": "0",
        "taxAmount": "0",
        "notes": None,
    }
    payload.update(overrides)
    return payload


def create_portfolio(
    client: TestClient,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/portfolio",
        json=portfolio_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_buy(
    client: TestClient,
    portfolio_id: str,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/portfolio/{portfolio_id}/transactions/buys",
        json=transaction_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_sell(
    client: TestClient,
    portfolio_id: str,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/portfolio/{portfolio_id}/transactions/sells",
        json=transaction_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def summary(client: TestClient, portfolio_id: str) -> dict[str, object]:
    response = client.get(f"/api/v1/portfolio/{portfolio_id}/position-summary")
    assert response.status_code == 200, response.text
    return response.json()


def test_first_buy_creates_holding_position(api_client: TestClient) -> None:
    item = create_portfolio(api_client)
    buy = create_buy(api_client, str(item["id"]))
    result = summary(api_client, str(item["id"]))
    assert buy["transactionSide"] == "BUY"
    assert buy["quantityBefore"] == "0"
    assert buy["quantityAfter"] == "4.000000000000000000"
    assert result["positionStatus"] == "HOLDING"
    assert result["currentQuantity"] == "4.000000000000000000"
    assert result["currentAveragePrice"] == "100.000000000000000000"


def test_additional_buy_uses_weighted_average(api_client: TestClient) -> None:
    item = create_portfolio(api_client)
    create_buy(api_client, str(item["id"]))
    create_buy(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
        quantity="2",
        unitPrice="130",
    )
    result = summary(api_client, str(item["id"]))
    assert result["currentQuantity"] == "6.000000000000000000"
    assert result["currentAveragePrice"] == "110.000000000000000000"
    assert result["totalBoughtQuantity"] == "6.000000000000000000"


def test_partial_and_full_sell_derive_position_status(
    api_client: TestClient,
) -> None:
    item = create_portfolio(api_client)
    create_buy(api_client, str(item["id"]))
    partial = create_sell(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
        quantity="1",
        unitPrice="120",
        feeAmount="1",
        taxAmount="2",
    )
    assert partial["quantityAfter"] == "3.000000000000000000"
    assert partial["realizedPnl"] == "17.000000000000000000"
    assert summary(api_client, str(item["id"]))["positionStatus"] == "HOLDING"
    create_sell(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 3, 9, 0, tzinfo=UTC).isoformat(),
        quantity="3",
        unitPrice="110",
    )
    result = summary(api_client, str(item["id"]))
    assert result["positionStatus"] == "CLOSED"
    assert result["currentQuantity"] == "0.000000000000000000"
    assert result["sellCount"] == 2


def test_rebuy_after_full_sale_reuses_same_card(api_client: TestClient) -> None:
    item = create_portfolio(api_client)
    create_buy(api_client, str(item["id"]))
    create_sell(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
    )
    create_buy(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 3, 9, 0, tzinfo=UTC).isoformat(),
        quantity="1",
        unitPrice="150",
    )
    result = summary(api_client, str(item["id"]))
    assert result["portfolioItemId"] == item["id"]
    assert result["positionStatus"] == "HOLDING"
    assert result["currentQuantity"] == "1.000000000000000000"
    assert result["currentAveragePrice"] == "150.000000000000000000"


def test_closed_position_can_remain_reentry_watch(
    api_client: TestClient,
) -> None:
    item = create_portfolio(api_client)
    create_buy(api_client, str(item["id"]))
    create_sell(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
    )
    response = api_client.patch(
        f"/api/v1/portfolio/{item['id']}",
        json={"trackingStatus": "REENTRY_WATCH"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["positionStatus"] == "CLOSED"
    assert response.json()["trackingStatus"] == "REENTRY_WATCH"
    assert response.json()["holdingStatus"] == "SOLD"


def test_sell_more_than_position_rolls_back(api_client: TestClient) -> None:
    item = create_portfolio(api_client)
    create_buy(api_client, str(item["id"]), quantity="1")
    response = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/sells",
        json=transaction_payload(
            tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
            quantity="2",
        ),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_POSITION_QUANTITY"
    assert summary(api_client, str(item["id"]))["currentQuantity"] == ("1.000000000000000000")


def test_transaction_quantity_is_immutable(api_client: TestClient) -> None:
    item = create_portfolio(api_client)
    buy = create_buy(api_client, str(item["id"]))
    response = api_client.patch(
        f"/api/v1/portfolio/{item['id']}/transactions/{buy['id']}",
        json={"quantity": "2"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRANSACTION_QUANTITY_IMMUTABLE"


def test_portfolio_snapshot_cannot_bypass_active_ledger(
    api_client: TestClient,
) -> None:
    item = create_portfolio(api_client)
    create_buy(api_client, str(item["id"]), quantity="2")
    response = api_client.patch(
        f"/api/v1/portfolio/{item['id']}",
        json={
            "holdingStatus": "SOLD",
            "quantity": "0",
            "averagePrice": "100",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PORTFOLIO_VALIDATION_ERROR"
    assert summary(api_client, str(item["id"]))["currentQuantity"] == ("2.000000000000000000")


def test_update_old_buy_replays_later_sale(api_client: TestClient) -> None:
    item = create_portfolio(api_client)
    buy = create_buy(api_client, str(item["id"]))
    sell = create_sell(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
        quantity="1",
        unitPrice="120",
    )
    response = api_client.patch(
        f"/api/v1/portfolio/{item['id']}/transactions/{buy['id']}",
        json={"unitPrice": "110"},
    )
    assert response.status_code == 200, response.text
    refreshed = api_client.get(
        f"/api/v1/portfolio/{item['id']}/transactions/{sell['id']}"
    ).json()
    assert refreshed["averagePriceBefore"] == "110.000000000000000000"
    assert refreshed["realizedPnl"] == "10.000000000000000000"


def test_void_buy_that_breaks_later_sell_rolls_back(
    api_client: TestClient,
) -> None:
    item = create_portfolio(api_client)
    buy = create_buy(api_client, str(item["id"]), quantity="1")
    create_sell(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
        quantity="1",
    )
    response = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/{buy['id']}/void",
        json={"reason": "잘못 입력"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRANSACTION_VOID_BREAKS_LEDGER"
    detail = api_client.get(f"/api/v1/portfolio/{item['id']}/transactions/{buy['id']}").json()
    assert detail["status"] == "ACTIVE"


def test_historical_import_replays_by_trade_time(
    api_client: TestClient,
) -> None:
    item = create_portfolio(api_client)
    response = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/historical-import",
        json={
            "items": [
                transaction_payload(
                    transactionSide="SELL",
                    tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
                    quantity="2",
                    unitPrice="120",
                ),
                transaction_payload(
                    transactionSide="BUY",
                    tradedAt=datetime(2026, 7, 1, 9, 0, tzinfo=UTC).isoformat(),
                    quantity="2",
                    unitPrice="100",
                ),
            ]
        },
    )
    assert response.status_code == 201, response.text
    result = summary(api_client, str(item["id"]))
    assert result["positionStatus"] == "CLOSED"
    timeline = api_client.get(f"/api/v1/portfolio/{item['id']}/transactions").json()
    assert [entry["transactionSide"] for entry in timeline["items"]] == [
        "BUY",
        "SELL",
    ]


def test_historical_import_negative_intermediate_rolls_back(
    api_client: TestClient,
) -> None:
    item = create_portfolio(api_client)
    response = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/historical-import",
        json={
            "items": [
                transaction_payload(
                    transactionSide="SELL",
                    quantity="1",
                )
            ]
        },
    )
    assert response.status_code == 422
    assert summary(api_client, str(item["id"]))["activeTransactionCount"] == 0


def test_crypto_precision_and_usdt_are_preserved(
    api_client: TestClient,
) -> None:
    item = create_portfolio(
        api_client,
        assetType="CRYPTO",
        symbol="BTC",
        market="BINANCE",
        currency="USDT",
    )
    buy = create_buy(
        api_client,
        str(item["id"]),
        quantity="0.00224215",
        unitPrice="115000.50",
    )
    assert buy["quantity"] == "0.00224215"
    invalid = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/buys",
        json=transaction_payload(
            quantity="0.000000001",
            unitPrice="115000.50",
        ),
    )
    assert invalid.status_code == 422


def test_crypto_sell_precision_uses_sell_validation_error(
    api_client: TestClient,
) -> None:
    item = create_portfolio(
        api_client,
        assetType="CRYPTO",
        symbol="BTC",
        market="UPBIT",
        currency="KRW",
    )
    create_buy(api_client, str(item["id"]), quantity="0.00224215")
    invalid = api_client.post(
        f"/api/v1/portfolio/{item['id']}/transactions/sells",
        json=transaction_payload(quantity="0.000000001"),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "SELL_VALIDATION_ERROR"


def test_six_trade_cycles_keep_one_card_and_exact_totals(
    api_client: TestClient,
) -> None:
    item = create_portfolio(
        api_client,
        name="LG전자",
        symbol="066570",
        market="KRX",
        currency="KRW",
    )
    prices = [("44825", "46200"), ("44650", "45800"), ("45100", "47000")]
    for cycle, (buy_price, sell_price) in enumerate(prices, start=1):
        create_buy(
            api_client,
            str(item["id"]),
            tradedAt=datetime(2026, 7, cycle * 2 - 1, 9, 0, tzinfo=UTC).isoformat(),
            quantity="4",
            unitPrice=buy_price,
        )
        create_sell(
            api_client,
            str(item["id"]),
            tradedAt=datetime(2026, 7, cycle * 2, 9, 0, tzinfo=UTC).isoformat(),
            quantity="4",
            unitPrice=sell_price,
        )
    result = summary(api_client, str(item["id"]))
    assert result["positionStatus"] == "CLOSED"
    assert result["totalBoughtQuantity"] == "12.000000000000000000"
    assert result["totalSoldQuantity"] == "12.000000000000000000"
    assert result["activeTransactionCount"] == 6
    listing = api_client.get("/api/v1/portfolio?market=KRX&query=066570").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == item["id"]


def test_usd_sell_fee_and_tax_are_decimal_exact(
    api_client: TestClient,
) -> None:
    item = create_portfolio(api_client, currency="USD")
    create_buy(api_client, str(item["id"]), quantity="2", unitPrice="100.10")
    sale = create_sell(
        api_client,
        str(item["id"]),
        tradedAt=datetime(2026, 7, 2, 9, 0, tzinfo=UTC).isoformat(),
        quantity="1",
        unitPrice="120.35",
        feeAmount="0.25",
        taxAmount="0.10",
    )
    assert sale["realizedPnl"] == "19.900000000000000000"
    assert sale["realizedReturnPercent"] == "19.880119880119880120"


def test_idempotency_key_reuses_transaction(api_client: TestClient) -> None:
    item = create_portfolio(api_client)
    first = create_buy(
        api_client,
        str(item["id"]),
        idempotencyKey="buy-once",
    )
    second = create_buy(
        api_client,
        str(item["id"]),
        idempotencyKey="buy-once",
    )
    assert second["id"] == first["id"]
    assert summary(api_client, str(item["id"]))["buyCount"] == 1


def test_create_with_initial_buy_is_atomic(api_client: TestClient) -> None:
    buy = transaction_payload(quantity="2", unitPrice="125")
    item = create_portfolio(
        api_client,
        holdingStatus="HOLDING",
        trackingStatus="NONE",
        quantity="2",
        averagePrice="125",
        initialBuy=buy,
    )
    assert item["positionStatus"] == "HOLDING"
    assert item["quantity"] == "2.000000000000000000"
    assert item["positionSummary"]["buyCount"] == 1
    assert item["positionSummary"]["currentAveragePrice"] == ("125.000000000000000000")


def test_same_market_symbol_still_has_one_card(
    api_client: TestClient,
) -> None:
    payload = portfolio_payload(symbol="ONECARD", market="NASDAQ")
    first = api_client.post("/api/v1/portfolio", json=payload)
    assert first.status_code == 201
    duplicate = api_client.post("/api/v1/portfolio", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PORTFOLIO_DUPLICATE"
    assert duplicate.json()["error"]["details"] == {
        "existingPortfolioId": first.json()["id"],
        "archived": False,
    }


def test_openapi_contains_ledger_but_no_order_api(
    api_client: TestClient,
) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/portfolio/{item_id}/transactions",
        "/api/v1/portfolio/{item_id}/transactions/buys",
        "/api/v1/portfolio/{item_id}/transactions/sells",
        "/api/v1/portfolio/{item_id}/transactions/{transaction_id}",
        "/api/v1/portfolio/{item_id}/transactions/{transaction_id}/void",
        "/api/v1/portfolio/{item_id}/transactions/historical-import",
        "/api/v1/portfolio/{item_id}/position-summary",
    }
    assert expected <= set(paths)
    assert all("order" not in path and "trade" not in path for path in paths)
