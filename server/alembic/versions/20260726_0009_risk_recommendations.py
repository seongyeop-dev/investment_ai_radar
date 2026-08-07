"""Add data-assisted risk profile acknowledgement metadata.

Revision ID: 20260726_0009
Revises: 20260726_0008
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0009"
down_revision: str | None = "20260726_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("risk_profiles") as batch:
        batch.add_column(
            sa.Column(
                "source",
                sa.String(length=20),
                nullable=False,
                server_default="CUSTOM",
            )
        )
        batch.add_column(sa.Column("portfolio_fingerprint", sa.String(length=64)))
        batch.add_column(sa.Column("recommendation_version", sa.String(length=50)))
        batch.create_check_constraint(
            "risk_profile_source",
            "source IN ('CUSTOM', 'DATA_ASSISTED')",
        )


def downgrade() -> None:
    with op.batch_alter_table("risk_profiles") as batch:
        batch.drop_constraint("risk_profile_source", type_="check")
        batch.drop_column("recommendation_version")
        batch.drop_column("portfolio_fingerprint")
        batch.drop_column("source")
