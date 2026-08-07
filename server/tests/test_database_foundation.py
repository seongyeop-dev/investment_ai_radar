from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.database import Database
from app.models.database import (
    AssetType,
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
    RecommendationMode,
    RiskProfileRecord,
)


@pytest.fixture
def database() -> Database:
    resolved = Database("sqlite+pysqlite://")
    resolved.create_schema()
    return resolved


def _portfolio(**overrides: object) -> PortfolioItemRecord:
    values: dict[str, object] = {
        "symbol": "005930",
        "name": "사용자 입력 종목",
        "market": "KRX",
        "asset_type": AssetType.EQUITY,
        "currency": Currency.KRW,
        "holding_status": HoldingStatus.WATCHLIST,
        "quantity": Decimal(0),
        "average_price": Decimal(0),
        "investment_horizon": InvestmentHorizon.UNSET,
        "strategy": "",
    }
    values.update(overrides)
    return PortfolioItemRecord(**values)


def test_decimal_precision_and_utc_timestamps(database: Database) -> None:
    exact = Decimal("123456789012345678.123456789012345678")
    item = _portfolio(
        symbol=" exact ",
        market=" nasdaq ",
        quantity=Decimal("1.000000000000000001"),
        average_price=exact,
        holding_status=HoldingStatus.HOLDING,
    )
    with database.session_scope() as session:
        session.add(item)
        session.flush()
        item_id = item.id

    with database.session_scope() as session:
        stored = session.get(PortfolioItemRecord, item_id)
        assert stored is not None
        assert stored.average_price == exact
        assert stored.symbol == "EXACT"
        assert stored.market == "NASDAQ"
        assert stored.created_at.tzinfo is UTC
        assert stored.updated_at.tzinfo is UTC


@pytest.mark.parametrize(
    "overrides",
    [
        {"quantity": Decimal("-0.1")},
        {"average_price": Decimal("-0.1")},
        {"holding_status": HoldingStatus.HOLDING, "quantity": Decimal(0)},
    ],
)
def test_invalid_portfolio_values_are_rejected(
    database: Database,
    overrides: dict[str, object],
) -> None:
    with pytest.raises(IntegrityError), database.session_scope() as session:
        session.add(_portfolio(**overrides))


def test_watchlist_zero_quantity_is_allowed(database: Database) -> None:
    with database.session_scope() as session:
        session.add(_portfolio())

    with database.session_scope() as session:
        count = session.scalar(select(func.count()).select_from(PortfolioItemRecord))
        assert count == 1


def test_active_market_symbol_is_unique_but_archived_history_is_allowed(
    database: Database,
) -> None:
    with database.session_scope() as session:
        session.add(_portfolio())

    with pytest.raises(IntegrityError), database.session_scope() as session:
        session.add(_portfolio(name="중복 활성 항목"))

    with database.session_scope() as session:
        session.add(
            _portfolio(
                name="보관 이력",
                archived_at=datetime(2026, 7, 25, 3, tzinfo=UTC),
            )
        )


def test_risk_profile_range_is_enforced(database: Database) -> None:
    with pytest.raises(IntegrityError), database.session_scope() as session:
        session.add(
            RiskProfileRecord(
                max_position_percent=Decimal("100.0001"),
                recommendation_mode=RecommendationMode.UNSET,
            )
        )


def test_transaction_rolls_back_on_error(database: Database) -> None:
    with (
        pytest.raises(RuntimeError, match="abort"),
        database.session_scope() as session,
    ):
        session.add(_portfolio())
        raise RuntimeError("abort")

    with database.session_scope() as session:
        count = session.scalar(select(func.count()).select_from(PortfolioItemRecord))
        assert count == 0
