"""Add the unified position transaction ledger.

Revision ID: 20260726_0008
Revises: 20260726_0007
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260726_0008"
down_revision: str | None = "20260726_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _decimal() -> sa.types.TypeEngine:
    return sa.Numeric(precision=38, scale=18).with_variant(
        sa.String(length=80),
        "sqlite",
    )


def _identifier(prefix: str, value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"investment-ai-radar:{prefix}:{value}"))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _audit_existing_data(
    portfolios: list[Mapping[str, object]],
    sales: list[Mapping[str, object]],
) -> None:
    active_keys: dict[tuple[str, str], list[str]] = {}
    sales_by_portfolio: dict[str, list[Mapping[str, object]]] = {}
    for sale in sales:
        if sale["status"] == "ACTIVE":
            sales_by_portfolio.setdefault(str(sale["portfolio_item_id"]), []).append(sale)
    blocked: list[str] = []
    for item in portfolios:
        item_id = str(item["id"])
        if item["archived_at"] is None:
            key = (str(item["market"]), str(item["symbol"]))
            active_keys.setdefault(key, []).append(item_id)
        quantity = Decimal(str(item["quantity"]))
        status = str(item["holding_status"])
        active_sales = sales_by_portfolio.get(item_id, [])
        if status == "HOLDING" and quantity <= 0:
            blocked.append(f"{item_id}:HOLDING_WITHOUT_POSITIVE_QUANTITY")
        if status == "HOLDING" and (
            item["average_price"] is None or Decimal(str(item["average_price"])) <= 0
        ):
            blocked.append(f"{item_id}:HOLDING_WITHOUT_POSITIVE_AVERAGE")
        if status == "SOLD" and quantity > 0:
            blocked.append(f"{item_id}:SOLD_WITH_POSITIVE_QUANTITY")
        if status == "SOLD" and not active_sales:
            blocked.append(f"{item_id}:SOLD_WITHOUT_ACTIVE_SALE")
        if active_sales:
            snapshots = {
                Decimal(str(sale["purchase_average_price_snapshot"])) for sale in active_sales
            }
            if len(snapshots) != 1:
                blocked.append(f"{item_id}:INCONSISTENT_PURCHASE_SNAPSHOTS")
            opening_quantity = quantity + sum(
                (Decimal(str(sale["quantity"])) for sale in active_sales),
                Decimal(0),
            )
            running_quantity = opening_quantity
            for sale in active_sales:
                sale_id = str(sale["id"])
                sold_quantity = Decimal(str(sale["quantity"]))
                quantity_before = Decimal(str(sale["quantity_before"]))
                quantity_after = Decimal(str(sale["quantity_after"]))
                expected_after = running_quantity - sold_quantity
                if str(sale["currency"]) != str(item["currency"]):
                    blocked.append(f"{item_id}:{sale_id}:CURRENCY_MISMATCH")
                if quantity_before != running_quantity:
                    blocked.append(f"{item_id}:{sale_id}:QUANTITY_BEFORE_MISMATCH")
                if quantity_after != expected_after or expected_after < 0:
                    blocked.append(f"{item_id}:{sale_id}:QUANTITY_AFTER_MISMATCH")
                unit_price = Decimal(str(sale["sale_price"]))
                average = Decimal(str(sale["purchase_average_price_snapshot"]))
                fee = Decimal(str(sale["fee_amount"]))
                tax = Decimal(str(sale["tax_amount"]))
                expected_gross = sold_quantity * unit_price
                expected_cost = sold_quantity * average
                expected_pnl = expected_gross - expected_cost - fee - tax
                if Decimal(str(sale["gross_proceeds"])) != expected_gross:
                    blocked.append(f"{item_id}:{sale_id}:GROSS_MISMATCH")
                if Decimal(str(sale["cost_basis"])) != expected_cost:
                    blocked.append(f"{item_id}:{sale_id}:COST_BASIS_MISMATCH")
                if Decimal(str(sale["realized_pnl"])) != expected_pnl:
                    blocked.append(f"{item_id}:{sale_id}:REALIZED_PNL_MISMATCH")
                running_quantity = expected_after
            if running_quantity != quantity:
                blocked.append(f"{item_id}:FINAL_QUANTITY_MISMATCH")
            if (
                quantity > 0
                and item["average_price"] is not None
                and len(snapshots) == 1
                and Decimal(str(item["average_price"])) not in snapshots
            ):
                blocked.append(f"{item_id}:CURRENT_AVERAGE_MISMATCH")
            final_status = "HOLDING" if quantity > 0 else "SOLD"
            if status != final_status:
                blocked.append(f"{item_id}:SNAPSHOT_STATUS_MISMATCH:{status}:{final_status}")
    for (market, symbol), identifiers in active_keys.items():
        if len(identifiers) > 1:
            blocked.append(
                f"{market}:{symbol}:DUPLICATE_ACTIVE:" + ",".join(sorted(identifiers))
            )
    if blocked:
        raise RuntimeError(
            "POSITION_LEDGER_MIGRATION_BLOCKED|" + "|".join(sorted(set(blocked)))
        )


def _load_existing_data() -> tuple[
    list[Mapping[str, object]],
    list[Mapping[str, object]],
]:
    connection = op.get_bind()
    portfolios = list(
        connection.execute(
            sa.text(
                """
                SELECT id, market, symbol, currency, holding_status, quantity,
                       average_price, created_at, updated_at, archived_at
                FROM portfolio_items
                ORDER BY id
                """
            )
        ).mappings()
    )
    sales = list(
        connection.execute(
            sa.text(
                """
                SELECT id, portfolio_item_id, transaction_type, sold_at,
                       quantity, sale_price, purchase_average_price_snapshot,
                       currency, fee_amount, tax_amount, gross_proceeds,
                       cost_basis, realized_pnl, realized_return_percent,
                       quantity_before, quantity_after, historical_import,
                       notes, status, voided_at, void_reason, created_at,
                       updated_at
                FROM sale_transactions
                ORDER BY portfolio_item_id, sold_at, created_at, id
                """
            )
        ).mappings()
    )
    return portfolios, sales


def _create_schema() -> None:
    op.create_table(
        "position_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_item_id", sa.String(length=36), nullable=False),
        sa.Column(
            "transaction_side",
            _enum("position_transaction_side", "BUY", "SELL"),
            nullable=False,
        ),
        sa.Column(
            "transaction_type",
            _enum(
                "position_transaction_type",
                "OPENING_BALANCE",
                "NORMAL",
                "HISTORICAL_IMPORT",
            ),
            nullable=False,
        ),
        sa.Column("traded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", _decimal(), nullable=False),
        sa.Column("unit_price", _decimal(), nullable=False),
        sa.Column(
            "currency",
            _enum(
                "position_transaction_currency",
                "KRW",
                "USD",
                "USDT",
                "OTHER",
            ),
            nullable=False,
        ),
        sa.Column("fee_amount", _decimal(), nullable=False),
        sa.Column("tax_amount", _decimal(), nullable=False),
        sa.Column("gross_amount", _decimal(), nullable=False),
        sa.Column("quantity_before", _decimal(), nullable=False),
        sa.Column("quantity_after", _decimal(), nullable=False),
        sa.Column("average_price_before", _decimal(), nullable=True),
        sa.Column("average_price_after", _decimal(), nullable=True),
        sa.Column("realized_pnl", _decimal(), nullable=True),
        sa.Column("realized_return_percent", _decimal(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column(
            "source_type",
            _enum(
                "position_transaction_source",
                "USER_ENTRY",
                "MIGRATED_SNAPSHOT",
                "MIGRATED_SALE",
                "HISTORICAL_IMPORT",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum("position_transaction_status", "ACTIVE", "VOIDED"),
            nullable=False,
        ),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.String(length=1000), nullable=True),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "CAST(quantity AS NUMERIC) > 0",
            name="ck_position_transaction_quantity_positive",
        ),
        sa.CheckConstraint(
            "CAST(unit_price AS NUMERIC) > 0",
            name="ck_position_transaction_price_positive",
        ),
        sa.CheckConstraint(
            "CAST(fee_amount AS NUMERIC) >= 0 AND CAST(tax_amount AS NUMERIC) >= 0",
            name="ck_position_transaction_costs_nonnegative",
        ),
        sa.CheckConstraint(
            "CAST(quantity_before AS NUMERIC) >= 0 AND CAST(quantity_after AS NUMERIC) >= 0",
            name="ck_position_transaction_snapshots_nonnegative",
        ),
        sa.CheckConstraint(
            "sequence_number > 0",
            name="ck_position_transaction_sequence_positive",
        ),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND voided_at IS NULL AND void_reason IS NULL) "
            "OR (status = 'VOIDED' AND voided_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(void_reason) > 0)",
            name="ck_position_transaction_void_state",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"],
            ["portfolio_items.id"],
            name="fk_position_transactions_portfolio_item_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_item_id",
            "idempotency_key",
            name="uq_position_transaction_portfolio_idempotency",
        ),
    )
    op.create_index(
        "ix_position_transactions_portfolio_traded",
        "position_transactions",
        ["portfolio_item_id", "traded_at", "created_at", "id"],
    )
    op.create_index(
        "ix_position_transactions_portfolio_status",
        "position_transactions",
        ["portfolio_item_id", "status", "sequence_number"],
    )
    with op.batch_alter_table("portfolio_items") as batch:
        batch.add_column(
            sa.Column(
                "position_status",
                sa.String(length=20),
                nullable=False,
                server_default="EMPTY",
            )
        )
        batch.add_column(
            sa.Column(
                "tracking_status",
                sa.String(length=20),
                nullable=False,
                server_default="NONE",
            )
        )
        batch.create_check_constraint(
            "position_status",
            "position_status IN ('EMPTY', 'HOLDING', 'CLOSED', 'NEEDS_REVIEW')",
        )
        batch.create_check_constraint(
            "tracking_status",
            "tracking_status IN ('NONE', 'WATCHLIST', 'REENTRY_WATCH')",
        )
    with op.batch_alter_table("sale_transactions") as batch:
        batch.add_column(sa.Column("ledger_transaction_id", sa.String(length=36)))
        batch.create_foreign_key(
            "fk_sale_transactions_ledger_transaction_id",
            "position_transactions",
            ["ledger_transaction_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_sale_transactions_ledger_transaction_id",
            ["ledger_transaction_id"],
        )


def _tracking_status(holding_status: str) -> str:
    if holding_status == "WATCHLIST":
        return "WATCHLIST"
    if holding_status == "REENTRY_WATCH":
        return "REENTRY_WATCH"
    return "NONE"


def _migrate_online(
    portfolios: list[Mapping[str, object]],
    sales: list[Mapping[str, object]],
) -> None:
    connection = op.get_bind()
    sales_by_portfolio: dict[str, list[Mapping[str, object]]] = {}
    for sale in sales:
        sales_by_portfolio.setdefault(str(sale["portfolio_item_id"]), []).append(sale)
    records: list[dict[str, object]] = []
    sale_links: list[tuple[str, str]] = []
    for item in portfolios:
        item_id = str(item["id"])
        item_sales = sales_by_portfolio.get(item_id, [])
        active_sales = [sale for sale in item_sales if sale["status"] == "ACTIVE"]
        current_quantity = Decimal(str(item["quantity"]))
        active_sold = sum(
            (Decimal(str(sale["quantity"])) for sale in active_sales),
            Decimal(0),
        )
        opening_quantity = current_quantity + active_sold
        opening_average = (
            Decimal(str(active_sales[0]["purchase_average_price_snapshot"]))
            if active_sales
            else Decimal(str(item["average_price"]))
            if item["average_price"] is not None
            else None
        )
        sequence = 0
        running_quantity = Decimal(0)
        if opening_quantity > 0:
            if opening_average is None or opening_average <= 0:
                raise RuntimeError(
                    f"POSITION_LEDGER_MIGRATION_BLOCKED|{item_id}:OPENING_AVERAGE_MISSING"
                )
            sequence += 1
            opening_time = (
                min(_datetime(sale["sold_at"]) for sale in active_sales)
                - timedelta(microseconds=1)
                if active_sales
                else _datetime(item["created_at"])
            )
            records.append(
                {
                    "id": _identifier("opening", item_id),
                    "portfolio_item_id": item_id,
                    "transaction_side": "BUY",
                    "transaction_type": "OPENING_BALANCE",
                    "traded_at": opening_time,
                    "quantity": opening_quantity,
                    "unit_price": opening_average,
                    "currency": str(item["currency"]),
                    "fee_amount": Decimal(0),
                    "tax_amount": Decimal(0),
                    "gross_amount": opening_quantity * opening_average,
                    "quantity_before": Decimal(0),
                    "quantity_after": opening_quantity,
                    "average_price_before": None,
                    "average_price_after": opening_average,
                    "realized_pnl": None,
                    "realized_return_percent": None,
                    "sequence_number": sequence,
                    "source_type": "MIGRATED_SNAPSHOT",
                    "status": "ACTIVE",
                    "voided_at": None,
                    "void_reason": None,
                    "notes": "기존 Portfolio 현재 수량·평단 보존용 Opening Balance",
                    "idempotency_key": f"MIGRATED_SNAPSHOT:{item_id}",
                    "created_at": _datetime(item["created_at"]),
                    "updated_at": _datetime(item["updated_at"]),
                }
            )
            running_quantity = opening_quantity
        average = opening_average
        for sale in item_sales:
            sequence += 1
            active = sale["status"] == "ACTIVE"
            quantity = Decimal(str(sale["quantity"]))
            before = running_quantity
            after = (
                running_quantity - quantity if active else Decimal(str(sale["quantity_after"]))
            )
            if active:
                running_quantity = after
            ledger_id = _identifier("sale", str(sale["id"]))
            records.append(
                {
                    "id": ledger_id,
                    "portfolio_item_id": item_id,
                    "transaction_side": "SELL",
                    "transaction_type": (
                        "HISTORICAL_IMPORT" if sale["historical_import"] else "NORMAL"
                    ),
                    "traded_at": _datetime(sale["sold_at"]),
                    "quantity": quantity,
                    "unit_price": Decimal(str(sale["sale_price"])),
                    "currency": str(sale["currency"]),
                    "fee_amount": Decimal(str(sale["fee_amount"])),
                    "tax_amount": Decimal(str(sale["tax_amount"])),
                    "gross_amount": Decimal(str(sale["gross_proceeds"])),
                    "quantity_before": before,
                    "quantity_after": after,
                    "average_price_before": average,
                    "average_price_after": average,
                    "realized_pnl": Decimal(str(sale["realized_pnl"])),
                    "realized_return_percent": (
                        Decimal(str(sale["realized_return_percent"]))
                        if sale["realized_return_percent"] is not None
                        else None
                    ),
                    "sequence_number": sequence,
                    "source_type": "MIGRATED_SALE",
                    "status": str(sale["status"]),
                    "voided_at": (
                        _datetime(sale["voided_at"]) if sale["voided_at"] is not None else None
                    ),
                    "void_reason": sale["void_reason"],
                    "notes": sale["notes"],
                    "idempotency_key": f"MIGRATED_SALE:{sale['id']}",
                    "created_at": _datetime(sale["created_at"]),
                    "updated_at": _datetime(sale["updated_at"]),
                }
            )
            sale_links.append((str(sale["id"]), ledger_id))
        position_status = (
            "HOLDING" if current_quantity > 0 else "CLOSED" if active_sales else "EMPTY"
        )
        connection.execute(
            sa.text(
                """
                UPDATE portfolio_items
                SET position_status = :position_status,
                    tracking_status = :tracking_status
                WHERE id = :id
                """
            ),
            {
                "id": item_id,
                "position_status": position_status,
                "tracking_status": _tracking_status(str(item["holding_status"])),
            },
        )
    if records:
        if connection.dialect.name == "sqlite":
            decimal_fields = {
                "quantity",
                "unit_price",
                "fee_amount",
                "tax_amount",
                "gross_amount",
                "quantity_before",
                "quantity_after",
                "average_price_before",
                "average_price_after",
                "realized_pnl",
                "realized_return_percent",
            }
            records = [
                {
                    key: (
                        format(value, "f")
                        if key in decimal_fields and isinstance(value, Decimal)
                        else value
                    )
                    for key, value in record.items()
                }
                for record in records
            ]
        table = sa.table(
            "position_transactions",
            *[
                sa.column(name)
                for name in (
                    "id",
                    "portfolio_item_id",
                    "transaction_side",
                    "transaction_type",
                    "traded_at",
                    "quantity",
                    "unit_price",
                    "currency",
                    "fee_amount",
                    "tax_amount",
                    "gross_amount",
                    "quantity_before",
                    "quantity_after",
                    "average_price_before",
                    "average_price_after",
                    "realized_pnl",
                    "realized_return_percent",
                    "sequence_number",
                    "source_type",
                    "status",
                    "voided_at",
                    "void_reason",
                    "notes",
                    "idempotency_key",
                    "created_at",
                    "updated_at",
                )
            ],
        )
        connection.execute(table.insert(), records)
    for sale_id, ledger_id in sale_links:
        connection.execute(
            sa.text(
                """
                UPDATE sale_transactions
                SET ledger_transaction_id = :ledger_id
                WHERE id = :sale_id
                """
            ),
            {"sale_id": sale_id, "ledger_id": ledger_id},
        )


def _offline_postgresql_preflight() -> None:
    op.execute(
        """
        DO $$
        DECLARE blocked_reason text;
        BEGIN
          WITH active_sales AS (
            SELECT s.*,
                   SUM(CAST(s.quantity AS NUMERIC)) OVER (
                     PARTITION BY s.portfolio_item_id
                   ) AS total_sold,
                   COALESCE(
                     SUM(CAST(s.quantity AS NUMERIC)) OVER (
                       PARTITION BY s.portfolio_item_id
                       ORDER BY s.sold_at, s.created_at, s.id
                       ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                     ),
                     0
                   ) AS prior_sold
            FROM sale_transactions s
            WHERE s.status = 'ACTIVE'
          ),
          blocked AS (
            SELECT p.id || ':INVALID_PORTFOLIO_SNAPSHOT' AS reason
            FROM portfolio_items p
            WHERE (p.holding_status = 'SOLD'
                   AND CAST(p.quantity AS NUMERIC) > 0)
               OR (p.holding_status = 'HOLDING'
                   AND CAST(p.quantity AS NUMERIC) <= 0)
               OR (p.holding_status = 'SOLD' AND NOT EXISTS (
                     SELECT 1 FROM active_sales s
                     WHERE s.portfolio_item_id = p.id
                   ))
            UNION ALL
            SELECT p.id || ':' || s.id || ':SALE_REPLAY_MISMATCH'
            FROM portfolio_items p
            JOIN active_sales s ON s.portfolio_item_id = p.id
            WHERE CAST(s.quantity_before AS NUMERIC) !=
                    CAST(p.quantity AS NUMERIC)
                    + s.total_sold - s.prior_sold
               OR CAST(s.quantity_after AS NUMERIC) !=
                    CAST(p.quantity AS NUMERIC)
                    + s.total_sold - s.prior_sold
                    - CAST(s.quantity AS NUMERIC)
            UNION ALL
            SELECT market || ':' || symbol || ':DUPLICATE_ACTIVE'
            FROM portfolio_items
            WHERE archived_at IS NULL
            GROUP BY market, symbol
            HAVING COUNT(*) > 1
          )
          SELECT reason INTO blocked_reason
          FROM blocked
          LIMIT 1;
          IF blocked_reason IS NOT NULL THEN
            RAISE EXCEPTION
              'POSITION_LEDGER_MIGRATION_BLOCKED:%', blocked_reason;
          END IF;
        END $$;
        """
    )


def _offline_postgresql_conversion() -> None:
    op.execute(
        """
        UPDATE portfolio_items
        SET tracking_status = CASE
              WHEN holding_status = 'WATCHLIST' THEN 'WATCHLIST'
              WHEN holding_status = 'REENTRY_WATCH' THEN 'REENTRY_WATCH'
              ELSE 'NONE'
            END,
            position_status = CASE
              WHEN CAST(quantity AS NUMERIC) > 0 THEN 'HOLDING'
              WHEN EXISTS (
                SELECT 1 FROM sale_transactions s
                WHERE s.portfolio_item_id = portfolio_items.id
                  AND s.status = 'ACTIVE'
              ) THEN 'CLOSED'
              ELSE 'EMPTY'
            END;
        """
    )
    op.execute(
        "-- Existing rows are converted by the online migration after its "
        "pre-DDL consistency audit."
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _offline_postgresql_preflight()
        _create_schema()
        _offline_postgresql_conversion()
        return
    portfolios, sales = _load_existing_data()
    _audit_existing_data(portfolios, sales)
    _create_schema()
    _migrate_online(portfolios, sales)


def downgrade() -> None:
    with op.batch_alter_table("sale_transactions") as batch:
        batch.drop_constraint(
            "uq_sale_transactions_ledger_transaction_id",
            type_="unique",
        )
        batch.drop_constraint(
            "fk_sale_transactions_ledger_transaction_id",
            type_="foreignkey",
        )
        batch.drop_column("ledger_transaction_id")
    with op.batch_alter_table("portfolio_items") as batch:
        batch.drop_constraint("tracking_status", type_="check")
        batch.drop_constraint("position_status", type_="check")
        batch.drop_column("tracking_status")
        batch.drop_column("position_status")
    op.drop_index(
        "ix_position_transactions_portfolio_status",
        table_name="position_transactions",
    )
    op.drop_index(
        "ix_position_transactions_portfolio_traded",
        table_name="position_transactions",
    )
    op.drop_table("position_transactions")
