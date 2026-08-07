from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from alembic import command


def test_migration_graph_has_expected_candidate_review_head() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()

    assert len(heads) == 1
    assert heads[0] == "20260803_0017"

    candidate_review_revision = script.get_revision("20260803_0017")

    assert candidate_review_revision is not None
    assert candidate_review_revision.down_revision == "20260803_0016"


def test_upgrade_downgrade_and_reupgrade() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

        inspector = inspect(connection)
        assert {
            "portfolio_items",
            "watch_entities",
            "sources",
            "risk_profiles",
        }.issubset(inspector.get_table_names())
        indexes = inspector.get_indexes("portfolio_items")
        assert any(
            index["name"] == "uq_portfolio_items_active_market_symbol" and index["unique"]
            for index in indexes
        )

        command.downgrade(config, "base")
        assert "portfolio_items" not in inspect(connection).get_table_names()

        command.upgrade(config, "head")
        assert "portfolio_items" in inspect(connection).get_table_names()


def test_crypto_portfolio_migration_roundtrip_preserves_five_records() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260726_0004")
        for index in range(5):
            connection.execute(
                text(
                    """
                    INSERT INTO portfolio_items (
                        id, symbol, name, market, currency, holding_status,
                        quantity, average_price, investment_horizon, strategy,
                        target_allocation, max_loss_percent, notes, created_at,
                        updated_at, archived_at, instrument_id
                    ) VALUES (
                        :id, :symbol, :name, :market, :currency, :status,
                        :quantity, :average_price, 'UNSET', '', NULL, NULL,
                        :notes, :timestamp, :timestamp, NULL, NULL
                    )
                    """
                ),
                {
                    "id": f"portfolio-{index}",
                    "symbol": f"00000{index}",
                    "name": f"Fixture {index}",
                    "market": "KRX",
                    "currency": "KRW",
                    "status": "WATCHLIST",
                    "quantity": str(index),
                    "average_price": str(index * 1000),
                    "notes": f"preserve-{index}",
                    "timestamp": timestamp,
                },
            )
        connection.commit()
        columns = (
            "id, symbol, name, market, currency, holding_status, quantity, "
            "average_price, investment_horizon, strategy, target_allocation, "
            "max_loss_percent, notes, created_at, updated_at, archived_at, instrument_id"
        )
        before = connection.execute(
            text(f"SELECT {columns} FROM portfolio_items ORDER BY id")  # noqa: S608
        ).all()

        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT count(*) FROM portfolio_items")) == 5
        assert connection.execute(
            text("SELECT DISTINCT asset_type FROM portfolio_items")
        ).scalars().all() == ["EQUITY"]

        command.downgrade(config, "20260726_0004")
        after_downgrade = connection.execute(
            text(f"SELECT {columns} FROM portfolio_items ORDER BY id")  # noqa: S608
        ).all()
        assert after_downgrade == before

        command.upgrade(config, "head")
        after_reupgrade = connection.execute(
            text(f"SELECT {columns} FROM portfolio_items ORDER BY id")  # noqa: S608
        ).all()
        assert after_reupgrade == before
        assert connection.scalar(text("SELECT count(*) FROM portfolio_items")) == 5


def test_sale_migration_roundtrip_preserves_existing_portfolios() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260726_0005")
        for index in range(6):
            connection.execute(
                text(
                    """
                    INSERT INTO portfolio_items (
                        id, symbol, name, market, currency, asset_type,
                        holding_status, quantity, average_price,
                        investment_horizon, strategy, target_allocation,
                        max_loss_percent, notes, created_at, updated_at,
                        archived_at, instrument_id
                    ) VALUES (
                        :id, :symbol, :name, 'KRX', 'KRW', 'EQUITY',
                        'WATCHLIST', '0', NULL, 'UNSET', '', NULL, NULL,
                        :notes, :timestamp, :timestamp, NULL, NULL
                    )
                    """
                ),
                {
                    "id": f"sale-migration-{index}",
                    "symbol": f"10000{index}",
                    "name": f"Preserve {index}",
                    "notes": f"unchanged-{index}",
                    "timestamp": timestamp,
                },
            )
        connection.commit()
        columns = (
            "id, symbol, name, market, currency, asset_type, holding_status, "
            "quantity, average_price, investment_horizon, strategy, "
            "target_allocation, max_loss_percent, notes, created_at, updated_at, "
            "archived_at, instrument_id"
        )
        before = connection.execute(
            text(f"SELECT {columns} FROM portfolio_items ORDER BY id")  # noqa: S608
        ).all()

        command.upgrade(config, "head")
        assert "sale_transactions" in inspect(connection).get_table_names()
        command.downgrade(config, "20260726_0005")
        assert "sale_transactions" not in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text(f"SELECT {columns} FROM portfolio_items ORDER BY id")  # noqa: S608
            ).all()
            == before
        )

        command.upgrade(config, "head")
        assert "sale_transactions" in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text(f"SELECT {columns} FROM portfolio_items ORDER BY id")  # noqa: S608
            ).all()
            == before
        )


def test_market_briefing_migration_roundtrip_preserves_existing_data() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260726_0006")
        for index in range(7):
            connection.execute(
                text(
                    """
                    INSERT INTO portfolio_items (
                        id, symbol, name, market, currency, asset_type,
                        holding_status, quantity, average_price,
                        investment_horizon, strategy, target_allocation,
                        max_loss_percent, notes, created_at, updated_at,
                        archived_at, instrument_id
                    ) VALUES (
                        :id, :symbol, :name, 'KRX', 'KRW', 'EQUITY',
                        'WATCHLIST', '0', NULL, 'UNSET', '', NULL, NULL,
                        :notes, :timestamp, :timestamp, NULL, NULL
                    )
                    """
                ),
                {
                    "id": f"market-migration-{index}",
                    "symbol": f"20000{index}",
                    "name": f"Preserve {index}",
                    "notes": f"unchanged-{index}",
                    "timestamp": timestamp,
                },
            )
        connection.execute(
            text(
                """
                INSERT INTO notification_preferences (
                    id, enabled, hourly_change_briefing_enabled,
                    daily_digest_enabled, correction_notice_enabled,
                    provider_failure_notice_enabled, recipient_email,
                    timezone, daily_digest_hour, minimum_priority,
                    include_watchlist, include_sold, created_at, updated_at
                ) VALUES (
                    'default', 0, 0, 1, 1, 0, NULL, 'Asia/Seoul', 8, 50,
                    1, 0, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO risk_profiles (
                    id, max_position_percent, max_portfolio_loss_percent,
                    default_stop_loss_percent, default_take_profit_percent,
                    max_single_trade_amount, cash_reserve_percent,
                    allow_averaging_down, recommendation_mode,
                    created_at, updated_at
                ) VALUES (
                    'default', '20', '15', '8', '25', NULL, '10', 0,
                    'UNSET', :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO briefing_records (
                    id, briefing_type, status, period_start, period_end,
                    generated_at, title, compact_summary, item_count,
                    material_change_count, correction_count, denial_count,
                    official_confirmed_count, needs_verification_count,
                    related_instrument_ids, content_fingerprint,
                    idempotency_key, valid_until, created_at, updated_at
                ) VALUES (
                    'briefing-legacy', 'DAILY_DIGEST', 'READY', :timestamp,
                    :timestamp, :timestamp, 'Legacy', 'unchanged', 0, 0, 0,
                    0, 0, 0, '[]', 'content-fingerprint',
                    'legacy-idempotency', :timestamp, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.commit()
        portfolio_columns = (
            "id, symbol, name, market, currency, asset_type, holding_status, "
            "quantity, average_price, investment_horizon, strategy, "
            "target_allocation, max_loss_percent, notes, created_at, updated_at, "
            "archived_at, instrument_id"
        )
        legacy = {
            "portfolio": connection.execute(
                text(
                    f"SELECT {portfolio_columns} FROM portfolio_items ORDER BY id"  # noqa: S608
                )
            ).all(),
            "preference": connection.execute(
                text(
                    "SELECT id, enabled, hourly_change_briefing_enabled, "
                    "daily_digest_enabled, correction_notice_enabled, "
                    "provider_failure_notice_enabled, recipient_email, timezone, "
                    "daily_digest_hour, minimum_priority, include_watchlist, "
                    "include_sold, created_at, updated_at "
                    "FROM notification_preferences ORDER BY id"
                )
            ).all(),
            "risk": connection.execute(
                text(
                    "SELECT id, max_position_percent, "
                    "max_portfolio_loss_percent, default_stop_loss_percent, "
                    "default_take_profit_percent, max_single_trade_amount, "
                    "cash_reserve_percent, allow_averaging_down, "
                    "recommendation_mode, created_at, updated_at "
                    "FROM risk_profiles ORDER BY id"
                )
            ).all(),
            "briefing": connection.execute(
                text(
                    "SELECT id, briefing_type, status, title, compact_summary, "
                    "idempotency_key FROM briefing_records ORDER BY id"
                )
            ).all(),
        }
        for revision in ("head", "20260726_0006", "head"):
            if revision == "head":
                command.upgrade(config, revision)
            else:
                command.downgrade(config, revision)
            assert (
                connection.execute(
                    text(
                        f"SELECT {portfolio_columns} FROM portfolio_items ORDER BY id"  # noqa: S608
                    )
                ).all()
                == legacy["portfolio"]
            )
            assert (
                connection.execute(
                    text(
                        "SELECT id, enabled, hourly_change_briefing_enabled, "
                        "daily_digest_enabled, correction_notice_enabled, "
                        "provider_failure_notice_enabled, recipient_email, timezone, "
                        "daily_digest_hour, minimum_priority, include_watchlist, "
                        "include_sold, created_at, updated_at "
                        "FROM notification_preferences ORDER BY id"
                    )
                ).all()
                == legacy["preference"]
            )
            assert (
                connection.execute(
                    text(
                        "SELECT id, max_position_percent, "
                        "max_portfolio_loss_percent, default_stop_loss_percent, "
                        "default_take_profit_percent, max_single_trade_amount, "
                        "cash_reserve_percent, allow_averaging_down, "
                        "recommendation_mode, created_at, updated_at "
                        "FROM risk_profiles ORDER BY id"
                    )
                ).all()
                == legacy["risk"]
            )
            assert (
                connection.execute(
                    text(
                        "SELECT id, briefing_type, status, title, compact_summary, "
                        "idempotency_key FROM briefing_records ORDER BY id"
                    )
                ).all()
                == legacy["briefing"]
            )


def test_position_ledger_migration_converts_safe_snapshots_and_sales() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260726_0007")
        for values in (
            {
                "id": "ledger-holding",
                "symbol": "HOLD",
                "status": "HOLDING",
                "quantity": "2",
                "average": "100",
            },
            {
                "id": "ledger-sold",
                "symbol": "SOLD",
                "status": "SOLD",
                "quantity": "0",
                "average": "50",
            },
        ):
            connection.execute(
                text(
                    """
                    INSERT INTO portfolio_items (
                        id, symbol, name, market, currency, asset_type,
                        holding_status, quantity, average_price,
                        investment_horizon, strategy, target_allocation,
                        max_loss_percent, notes, created_at, updated_at,
                        archived_at, instrument_id
                    ) VALUES (
                        :id, :symbol, :symbol, 'NASDAQ', 'USD', 'EQUITY',
                        :status, :quantity, :average, 'UNSET', '', NULL, NULL,
                        NULL, :timestamp, :timestamp, NULL, NULL
                    )
                    """
                ),
                {**values, "timestamp": timestamp},
            )
        connection.execute(
            text(
                """
                INSERT INTO sale_transactions (
                    id, portfolio_item_id, transaction_type, sold_at,
                    quantity, sale_price, purchase_average_price_snapshot,
                    currency, fee_amount, tax_amount, gross_proceeds,
                    cost_basis, realized_pnl, realized_return_percent,
                    quantity_before, quantity_after, historical_import, notes,
                    status, voided_at, void_reason, created_at, updated_at
                ) VALUES (
                    'legacy-sale', 'ledger-sold', 'HISTORICAL_SALE',
                    :timestamp, '1', '60', '50', 'USD', '1', '0', '60',
                    '50', '9', '18', '1', '0', 1, NULL, 'ACTIVE', NULL,
                    NULL, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.commit()
        portfolio_columns = (
            "id, symbol, name, market, currency, asset_type, holding_status, "
            "quantity, average_price, investment_horizon, strategy, "
            "target_allocation, max_loss_percent, notes, created_at, updated_at, "
            "archived_at, instrument_id"
        )
        sale_columns = (
            "id, portfolio_item_id, transaction_type, sold_at, quantity, "
            "sale_price, purchase_average_price_snapshot, currency, fee_amount, "
            "tax_amount, gross_proceeds, cost_basis, realized_pnl, "
            "realized_return_percent, quantity_before, quantity_after, "
            "historical_import, notes, status, voided_at, void_reason, "
            "created_at, updated_at"
        )
        legacy_portfolio = connection.execute(
            text(f"SELECT {portfolio_columns} FROM portfolio_items ORDER BY id")  # noqa: S608
        ).all()
        legacy_sales = connection.execute(
            text(f"SELECT {sale_columns} FROM sale_transactions ORDER BY id")  # noqa: S608
        ).all()

        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT count(*) FROM position_transactions")) == 3
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM sale_transactions "
                    "WHERE ledger_transaction_id IS NOT NULL"
                )
            )
            == 1
        )
        assert connection.execute(
            text("SELECT id, position_status, tracking_status FROM portfolio_items ORDER BY id")
        ).all() == [
            ("ledger-holding", "HOLDING", "NONE"),
            ("ledger-sold", "CLOSED", "NONE"),
        ]

        command.downgrade(config, "20260726_0007")
        assert "position_transactions" not in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text(f"SELECT {portfolio_columns} FROM portfolio_items ORDER BY id")  # noqa: S608
            ).all()
            == legacy_portfolio
        )
        assert (
            connection.execute(
                text(f"SELECT {sale_columns} FROM sale_transactions ORDER BY id")  # noqa: S608
            ).all()
            == legacy_sales
        )

        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT count(*) FROM position_transactions")) == 3
        assert (
            connection.execute(
                text(f"SELECT {portfolio_columns} FROM portfolio_items ORDER BY id")  # noqa: S608
            ).all()
            == legacy_portfolio
        )
        assert (
            connection.execute(
                text(f"SELECT {sale_columns} FROM sale_transactions ORDER BY id")  # noqa: S608
            ).all()
            == legacy_sales
        )


def test_position_ledger_migration_blocks_inconsistent_sold_snapshot() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260726_0007")
        connection.execute(
            text(
                """
                INSERT INTO portfolio_items (
                    id, symbol, name, market, currency, asset_type,
                    holding_status, quantity, average_price,
                    investment_horizon, strategy, target_allocation,
                    max_loss_percent, notes, created_at, updated_at,
                    archived_at, instrument_id
                ) VALUES (
                    'blocked-position', 'BLOCK', 'Blocked', 'KRX', 'KRW',
                    'EQUITY', 'SOLD', '1', '100', 'UNSET', '', NULL, NULL,
                    NULL, :timestamp, :timestamp, NULL, NULL
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO sale_transactions (
                    id, portfolio_item_id, transaction_type, sold_at,
                    quantity, sale_price, purchase_average_price_snapshot,
                    currency, fee_amount, tax_amount, gross_proceeds,
                    cost_basis, realized_pnl, realized_return_percent,
                    quantity_before, quantity_after, historical_import, notes,
                    status, voided_at, void_reason, created_at, updated_at
                ) VALUES (
                    'blocked-sale', 'blocked-position', 'HISTORICAL_SALE',
                    :timestamp, '1', '110', '100', 'KRW', '0', '0', '110',
                    '100', '10', '10', '1', '0', 1, NULL, 'ACTIVE', NULL,
                    NULL, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.commit()

        with pytest.raises(
            RuntimeError,
            match="blocked-position:SOLD_WITH_POSITIVE_QUANTITY",
        ):
            command.upgrade(config, "head")
        assert "position_transactions" not in inspect(connection).get_table_names()
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "20260726_0007"
        )
        assert connection.scalar(text("SELECT count(*) FROM portfolio_items")) == 1
        assert connection.scalar(text("SELECT count(*) FROM sale_transactions")) == 1


def test_news_migration_preserves_existing_portfolio_instrument_and_disclosure() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260725_0002")
        connection.execute(
            text(
                """
                INSERT INTO instruments (
                    id, canonical_symbol, display_name, local_name, exchange,
                    market, country, currency, asset_type, active,
                    verification_status, verification_source, verified_at,
                    delisted_at, created_at, updated_at
                ) VALUES (
                    'instrument-1', '005930', 'Samsung Electronics', '삼성전자',
                    'KRX', 'KRX', 'KR', 'KRW', 'EQUITY', 1, 'VERIFIED',
                    'FIXTURE', :timestamp, NULL, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO portfolio_items (
                    id, symbol, name, market, currency, holding_status, quantity,
                    average_price, investment_horizon, strategy, target_allocation,
                    max_loss_percent, notes, created_at, updated_at, archived_at,
                    instrument_id
                ) VALUES (
                    'portfolio-1', '005930', 'Samsung Electronics', 'KRX', 'KRW',
                    'WATCHLIST', '0', NULL, 'UNSET', '', NULL, NULL, NULL,
                    :timestamp, :timestamp, NULL, 'instrument-1'
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO information_events (
                    id, event_key, instrument_id, event_type, normalized_claim,
                    claim_fingerprint, first_seen_at, last_seen_at,
                    latest_material_change_at, lifecycle_status,
                    verification_status, source_count, official_source_count,
                    current_summary, material_change, pinned, created_at, updated_at
                ) VALUES (
                    'event-1', 'event-key-1', 'instrument-1', 'OFFICIAL',
                    'fixture claim', 'fixture-hash', :timestamp, :timestamp, NULL,
                    'ACTIVE', 'OFFICIAL_CONFIRMED', 1, 1, 'fixture', 0, 0,
                    :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO disclosure_records (
                    id, instrument_id, event_id, provider, provider_document_id,
                    accession_number, receipt_number, form_type, report_type,
                    title, company_name, official_url, published_at,
                    source_updated_at, first_seen_at, fetched_at, verified_at,
                    verification_status, source_grade, content_fingerprint,
                    metadata_hash, summary, summary_status, key_facts,
                    material_change, correction_of_id, lifecycle_status, pinned,
                    created_at, updated_at
                ) VALUES (
                    'disclosure-1', 'instrument-1', 'event-1', 'OPENDART',
                    'fixture-document', NULL, 'fixture-receipt', NULL, 'FIXTURE',
                    'Fixture disclosure', 'Samsung Electronics',
                    'https://official.invalid/fixture', :timestamp, NULL,
                    :timestamp, :timestamp, :timestamp, 'OFFICIAL_CONFIRMED',
                    'A', 'content-hash', 'metadata-hash', 'fixture', 'STRUCTURED',
                    '[]', 0, NULL, 'ACTIVE', 0, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.commit()

        for revision in ("head", "20260725_0002", "head"):
            command.upgrade(config, revision) if revision == "head" else command.downgrade(
                config, revision
            )
            for table in (
                "portfolio_items",
                "instruments",
                "disclosure_records",
            ):
                assert (
                    connection.scalar(
                        text(f"SELECT count(*) FROM {table}")  # noqa: S608
                    )
                    == 1
                )


def test_briefing_migration_preserves_existing_news_and_event() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260726_0003")
        connection.execute(
            text(
                """
                INSERT INTO instruments (
                    id, canonical_symbol, display_name, local_name, exchange,
                    market, country, currency, asset_type, active,
                    verification_status, verification_source, verified_at,
                    delisted_at, created_at, updated_at
                ) VALUES (
                    'instrument-c', '000001', 'Fixture', NULL, 'KRX', 'KRX',
                    'KR', 'KRW', 'EQUITY', 1, 'VERIFIED', 'FIXTURE',
                    :timestamp, NULL, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO sources (
                    id, name, source_type, source_grade, domain, official,
                    enabled, created_at, updated_at
                ) VALUES (
                    'source-c', 'Fixture C', 'NEWS_FEED', 'B',
                    'fixture.invalid', 0, 1, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO information_events (
                    id, event_key, instrument_id, event_type, normalized_claim,
                    claim_fingerprint, first_seen_at, last_seen_at,
                    latest_material_change_at, lifecycle_status,
                    verification_status, source_count, official_source_count,
                    current_summary, material_change, pinned, created_at,
                    updated_at
                ) VALUES (
                    'event-c', 'event-key-c', 'instrument-c', 'NEWS',
                    'fixture claim', 'event-fingerprint', :timestamp, :timestamp,
                    :timestamp, 'UPDATED', 'NEEDS_VERIFICATION', 1, 0,
                    'fixture', 1, 0, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.execute(
            text(
                """
                INSERT INTO news_references (
                    id, instrument_id, portfolio_item_id, source_id, provider,
                    provider_item_id, title, normalized_title, source_name,
                    source_domain, canonical_url, canonical_url_hash,
                    original_url, published_at, source_updated_at, first_seen_at,
                    last_seen_at, fetched_at, verified_at, language, snippet,
                    short_summary, summary_status, primary_claim,
                    claim_fingerprint, content_fingerprint, verification_status,
                    source_grade, trust_score, certainty_level,
                    independent_origin, original_origin_key, duplicate_of_id,
                    information_event_id, material_change, stale_reused,
                    lifecycle_status, official_reference_ids, changed_facts,
                    pinned, created_at, updated_at
                ) VALUES (
                    'news-c', 'instrument-c', NULL, 'source-c', 'RSS', 'item-c',
                    'Fixture title', 'fixture title', 'Fixture C',
                    'fixture.invalid', 'https://fixture.invalid/c',
                    'canonical-hash-c', 'https://fixture.invalid/c', :timestamp,
                    NULL, :timestamp, :timestamp, :timestamp, NULL, 'ko',
                    'snippet', 'summary', 'RULE_BASED', 'fixture claim',
                    'claim-hash-c', 'content-hash-c', 'NEEDS_VERIFICATION', 'B',
                    65, 'ANNOUNCED', 1, 'fixture c', NULL, 'event-c', 1, 0,
                    'UPDATED', '[]', '[]', 0, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.commit()

        for revision in ("head", "20260726_0003", "head"):
            if revision == "head":
                command.upgrade(config, revision)
            else:
                command.downgrade(config, revision)
            assert connection.scalar(text("SELECT count(*) FROM information_events")) == 1
            assert connection.scalar(text("SELECT count(*) FROM news_references")) == 1


def test_risk_recommendation_metadata_migration_roundtrip() -> None:
    server_root = Path(__file__).resolve().parents[1]
    config = Config(server_root / "alembic.ini")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    timestamp = "2026-07-26 12:00:00+00:00"

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260726_0008")
        connection.execute(
            text(
                """
                INSERT INTO risk_profiles (
                    id, max_position_percent, allow_averaging_down,
                    recommendation_mode, risk_style,
                    max_single_position_percent, acknowledged_at,
                    created_at, updated_at
                ) VALUES (
                    'default', '20', 0, 'UNSET', 'BALANCED',
                    '20', :timestamp, :timestamp, :timestamp
                )
                """
            ),
            {"timestamp": timestamp},
        )
        connection.commit()

        command.upgrade(config, "head")
        row = connection.execute(
            text(
                """
                SELECT source, portfolio_fingerprint,
                       recommendation_version, max_position_percent,
                       max_single_position_percent
                FROM risk_profiles WHERE id = 'default'
                """
            )
        ).one()
        assert tuple(row) == ("CUSTOM", None, None, "20", "20")

        command.downgrade(config, "20260726_0008")
        columns = {
            column["name"] for column in inspect(connection).get_columns("risk_profiles")
        }
        assert "source" not in columns
        assert "portfolio_fingerprint" not in columns
        assert (
            connection.scalar(
                text(
                    "SELECT max_single_position_percent FROM risk_profiles WHERE id = 'default'"
                )
            )
            == "20"
        )

        command.upgrade(config, "head")
        assert (
            connection.scalar(text("SELECT source FROM risk_profiles WHERE id = 'default'"))
            == "CUSTOM"
        )
