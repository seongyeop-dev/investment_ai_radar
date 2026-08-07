"""Add portfolio asset types and crypto settlement currency.

Revision ID: 20260726_0005
Revises: 20260726_0004
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0005"
down_revision: str | None = "20260726_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    with op.batch_alter_table("portfolio_items") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=_enum("currency", "KRW", "USD", "OTHER"),
            type_=_enum("currency", "KRW", "USD", "USDT", "OTHER"),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column(
                "asset_type",
                _enum(
                    "portfolio_asset_type",
                    "EQUITY",
                    "ETF",
                    "ADR",
                    "CRYPTO",
                    "OTHER",
                ),
                nullable=False,
                server_default="EQUITY",
            )
        )

    with op.batch_alter_table("portfolio_items") as batch_op:
        batch_op.alter_column(
            "asset_type",
            existing_type=_enum(
                "portfolio_asset_type",
                "EQUITY",
                "ETF",
                "ADR",
                "CRYPTO",
                "OTHER",
            ),
            existing_nullable=False,
            server_default=None,
        )

    with op.batch_alter_table("instruments") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=_enum("instrument_currency", "KRW", "USD", "OTHER"),
            type_=_enum("instrument_currency", "KRW", "USD", "USDT", "OTHER"),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "asset_type",
            existing_type=_enum(
                "asset_type",
                "EQUITY",
                "ETF",
                "ADR",
                "CRYPTO",
                "INDEX",
                "COMMODITY",
                "FX",
                "UNKNOWN",
            ),
            type_=_enum(
                "asset_type",
                "EQUITY",
                "ETF",
                "ADR",
                "CRYPTO",
                "INDEX",
                "COMMODITY",
                "FX",
                "OTHER",
                "UNKNOWN",
            ),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch_op:
        batch_op.alter_column(
            "asset_type",
            existing_type=_enum(
                "asset_type",
                "EQUITY",
                "ETF",
                "ADR",
                "CRYPTO",
                "INDEX",
                "COMMODITY",
                "FX",
                "OTHER",
                "UNKNOWN",
            ),
            type_=_enum(
                "asset_type",
                "EQUITY",
                "ETF",
                "ADR",
                "CRYPTO",
                "INDEX",
                "COMMODITY",
                "FX",
                "UNKNOWN",
            ),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "currency",
            existing_type=_enum("instrument_currency", "KRW", "USD", "USDT", "OTHER"),
            type_=_enum("instrument_currency", "KRW", "USD", "OTHER"),
            existing_nullable=False,
        )

    with op.batch_alter_table("portfolio_items") as batch_op:
        batch_op.drop_constraint("portfolio_asset_type", type_="check")
        batch_op.drop_column("asset_type")
        batch_op.alter_column(
            "currency",
            existing_type=_enum("currency", "KRW", "USD", "USDT", "OTHER"),
            type_=_enum("currency", "KRW", "USD", "OTHER"),
            existing_nullable=False,
        )
