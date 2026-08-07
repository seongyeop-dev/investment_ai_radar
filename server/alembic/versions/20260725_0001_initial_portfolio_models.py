"""Create the portfolio, watch, source, and risk-profile tables.

Revision ID: 20260725_0001
Revises:
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260725_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
    )


def _decimal(precision: int, scale: int) -> sa.types.TypeEngine:
    return sa.Numeric(precision=precision, scale=scale).with_variant(
        sa.String(length=80),
        "sqlite",
    )


def upgrade() -> None:
    op.create_table(
        "portfolio_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("market", sa.String(length=50), nullable=False),
        sa.Column("currency", _enum("currency", "KRW", "USD", "OTHER"), nullable=False),
        sa.Column(
            "holding_status",
            _enum("holding_status", "HOLDING", "WATCHLIST", "SOLD", "REENTRY_WATCH"),
            nullable=False,
        ),
        sa.Column("quantity", _decimal(38, 18), nullable=False),
        sa.Column("average_price", _decimal(38, 18), nullable=True),
        sa.Column(
            "investment_horizon",
            _enum("investment_horizon", "SCALP", "SHORT", "MEDIUM", "LONG", "UNSET"),
            nullable=False,
        ),
        sa.Column("strategy", sa.String(length=500), nullable=False),
        sa.Column("target_allocation", _decimal(7, 4), nullable=True),
        sa.Column("max_loss_percent", _decimal(7, 4), nullable=True),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "CAST(quantity AS NUMERIC) >= 0",
            name="ck_portfolio_quantity_nonnegative",
        ),
        sa.CheckConstraint(
            "average_price IS NULL OR CAST(average_price AS NUMERIC) >= 0",
            name="ck_portfolio_average_price_nonnegative",
        ),
        sa.CheckConstraint(
            "holding_status != 'HOLDING' OR CAST(quantity AS NUMERIC) > 0",
            name="ck_portfolio_holding_positive_quantity",
        ),
        sa.CheckConstraint(
            "target_allocation IS NULL OR "
            "(CAST(target_allocation AS NUMERIC) >= 0 "
            "AND CAST(target_allocation AS NUMERIC) <= 100)",
            name="ck_portfolio_target_allocation_range",
        ),
        sa.CheckConstraint(
            "max_loss_percent IS NULL OR "
            "(CAST(max_loss_percent AS NUMERIC) >= 0 "
            "AND CAST(max_loss_percent AS NUMERIC) <= 100)",
            name="ck_portfolio_max_loss_range",
        ),
        sa.CheckConstraint(
            "notes IS NULL OR length(notes) <= 4000",
            name="ck_portfolio_notes_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_portfolio_items_active_market_symbol",
        "portfolio_items",
        ["market", "symbol"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
        sqlite_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "watch_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("related_companies", sa.JSON(), nullable=False),
        sa.Column("competitors", sa.JSON(), nullable=False),
        sa.Column("customers", sa.JSON(), nullable=False),
        sa.Column("industries", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column(
            "source_grade",
            _enum("source_grade", "A", "B", "C", "D"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "risk_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("max_position_percent", _decimal(7, 4), nullable=True),
        sa.Column(
            "max_portfolio_loss_percent",
            _decimal(7, 4),
            nullable=True,
        ),
        sa.Column(
            "default_stop_loss_percent",
            _decimal(7, 4),
            nullable=True,
        ),
        sa.Column(
            "default_take_profit_percent",
            _decimal(7, 4),
            nullable=True,
        ),
        sa.Column("max_single_trade_amount", _decimal(38, 18), nullable=True),
        sa.Column("cash_reserve_percent", _decimal(7, 4), nullable=True),
        sa.Column("allow_averaging_down", sa.Boolean(), nullable=False),
        sa.Column(
            "recommendation_mode",
            _enum(
                "recommendation_mode",
                "CONSERVATIVE",
                "BALANCED",
                "AGGRESSIVE",
                "UNSET",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "max_position_percent IS NULL OR "
            "(CAST(max_position_percent AS NUMERIC) >= 0 "
            "AND CAST(max_position_percent AS NUMERIC) <= 100)",
            name="ck_risk_max_position_range",
        ),
        sa.CheckConstraint(
            "max_portfolio_loss_percent IS NULL OR "
            "(CAST(max_portfolio_loss_percent AS NUMERIC) >= 0 "
            "AND CAST(max_portfolio_loss_percent AS NUMERIC) <= 100)",
            name="ck_risk_max_portfolio_loss_range",
        ),
        sa.CheckConstraint(
            "default_stop_loss_percent IS NULL OR "
            "(CAST(default_stop_loss_percent AS NUMERIC) >= 0 "
            "AND CAST(default_stop_loss_percent AS NUMERIC) <= 100)",
            name="ck_risk_default_stop_loss_range",
        ),
        sa.CheckConstraint(
            "default_take_profit_percent IS NULL OR "
            "(CAST(default_take_profit_percent AS NUMERIC) >= 0 "
            "AND CAST(default_take_profit_percent AS NUMERIC) <= 100)",
            name="ck_risk_default_take_profit_range",
        ),
        sa.CheckConstraint(
            "max_single_trade_amount IS NULL OR CAST(max_single_trade_amount AS NUMERIC) >= 0",
            name="ck_risk_max_single_trade_nonnegative",
        ),
        sa.CheckConstraint(
            "cash_reserve_percent IS NULL OR "
            "(CAST(cash_reserve_percent AS NUMERIC) >= 0 "
            "AND CAST(cash_reserve_percent AS NUMERIC) <= 100)",
            name="ck_risk_cash_reserve_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("risk_profiles")
    op.drop_table("sources")
    op.drop_table("watch_entities")
    op.drop_index(
        "uq_portfolio_items_active_market_symbol",
        table_name="portfolio_items",
        postgresql_where=sa.text("archived_at IS NULL"),
        sqlite_where=sa.text("archived_at IS NULL"),
    )
    op.drop_table("portfolio_items")
