"""Add reference source change history.

Revision ID: 20260802_0015
Revises: 20260730_0014
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260802_0015"
down_revision: str | None = "20260730_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_source_change_history",
        sa.Column(
            "id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "operation",
            sa.String(10),
            nullable=False,
        ),
        sa.Column(
            "changed_fields",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "before_values",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "after_values",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "backup_path",
            sa.String(1000),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('CREATE', 'UPDATE')",
            name=("ck_reference_source_change_history_operation"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_reference_source_change_history_source_created",
        "reference_source_change_history",
        ["source_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reference_source_change_history_source_created",
        table_name=("reference_source_change_history"),
    )
    op.drop_table("reference_source_change_history")
