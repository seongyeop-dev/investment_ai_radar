"""Add sale transaction records and realized PnL snapshots.

Revision ID: 20260726_0006
Revises: 20260726_0005
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0006"
down_revision: str | None = "20260726_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _decimal() -> sa.types.TypeEngine:
    return sa.Numeric(precision=38, scale=18).with_variant(
        sa.String(length=80),
        "sqlite",
    )


def upgrade() -> None:
    op.create_table(
        "sale_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_item_id", sa.String(length=36), nullable=False),
        sa.Column(
            "transaction_type",
            _enum(
                "sale_transaction_type",
                "PARTIAL_SALE",
                "FULL_SALE",
                "HISTORICAL_SALE",
            ),
            nullable=False,
        ),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", _decimal(), nullable=False),
        sa.Column("sale_price", _decimal(), nullable=False),
        sa.Column("purchase_average_price_snapshot", _decimal(), nullable=False),
        sa.Column(
            "currency",
            _enum("sale_currency", "KRW", "USD", "USDT", "OTHER"),
            nullable=False,
        ),
        sa.Column("fee_amount", _decimal(), nullable=False),
        sa.Column("tax_amount", _decimal(), nullable=False),
        sa.Column("gross_proceeds", _decimal(), nullable=False),
        sa.Column("cost_basis", _decimal(), nullable=False),
        sa.Column("realized_pnl", _decimal(), nullable=False),
        sa.Column("realized_return_percent", _decimal(), nullable=True),
        sa.Column("quantity_before", _decimal(), nullable=False),
        sa.Column("quantity_after", _decimal(), nullable=False),
        sa.Column("historical_import", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column(
            "status",
            _enum("sale_transaction_status", "ACTIVE", "VOIDED"),
            nullable=False,
        ),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "CAST(quantity AS NUMERIC) > 0",
            name="ck_sale_quantity_positive",
        ),
        sa.CheckConstraint(
            "CAST(sale_price AS NUMERIC) > 0",
            name="ck_sale_price_positive",
        ),
        sa.CheckConstraint(
            "CAST(purchase_average_price_snapshot AS NUMERIC) > 0",
            name="ck_sale_purchase_average_positive",
        ),
        sa.CheckConstraint(
            "CAST(fee_amount AS NUMERIC) >= 0",
            name="ck_sale_fee_nonnegative",
        ),
        sa.CheckConstraint(
            "CAST(tax_amount AS NUMERIC) >= 0",
            name="ck_sale_tax_nonnegative",
        ),
        sa.CheckConstraint(
            "CAST(quantity_before AS NUMERIC) >= 0 AND CAST(quantity_after AS NUMERIC) >= 0",
            name="ck_sale_quantity_snapshots_nonnegative",
        ),
        sa.CheckConstraint(
            "(transaction_type = 'HISTORICAL_SALE' AND historical_import = true) "
            "OR (transaction_type != 'HISTORICAL_SALE' AND historical_import = false)",
            name="ck_sale_historical_type",
        ),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND voided_at IS NULL AND void_reason IS NULL) "
            "OR (status = 'VOIDED' AND voided_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(void_reason) > 0)",
            name="ck_sale_void_state",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"],
            ["portfolio_items.id"],
            name="fk_sale_transactions_portfolio_item_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sale_transactions_portfolio_sold_at",
        "sale_transactions",
        ["portfolio_item_id", "sold_at"],
    )
    op.create_index(
        "ix_sale_transactions_portfolio_status_created",
        "sale_transactions",
        ["portfolio_item_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sale_transactions_portfolio_status_created",
        table_name="sale_transactions",
    )
    op.drop_index(
        "ix_sale_transactions_portfolio_sold_at",
        table_name="sale_transactions",
    )
    op.drop_table("sale_transactions")
