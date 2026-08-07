"""Add analyst reference translation metadata.

Revision ID: 20260730_0014
Revises: 20260730_0013
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0014"
down_revision: str | None = "20260730_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table(
        "analyst_references",
        recreate="always",
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_language",
                sa.String(length=12),
                nullable=False,
                server_default="und",
            )
        )
        batch_op.add_column(
            sa.Column(
                "translated_title_ko",
                sa.String(length=500),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "translated_abstract_ko",
                sa.String(length=300),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "translation_status",
                sa.String(length=13),
                nullable=False,
                server_default="NOT_REQUESTED",
            )
        )
        batch_op.add_column(
            sa.Column(
                "translation_provider",
                sa.String(length=100),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "translation_error",
                sa.String(length=500),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "translated_at",
                sa.DateTime(),
                nullable=True,
            )
        )
        batch_op.create_check_constraint(
            "ck_analyst_reference_translated_title_length",
            "translated_title_ko IS NULL OR length(translated_title_ko) <= 500",
        )
        batch_op.create_check_constraint(
            "ck_analyst_reference_translated_abstract_length",
            "translated_abstract_ko IS NULL OR length(translated_abstract_ko) <= 300",
        )
        batch_op.create_index(
            "ix_analyst_references_translation_status",
            ["translation_status"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "analyst_references",
        recreate="always",
    ) as batch_op:
        batch_op.drop_index("ix_analyst_references_translation_status")
        batch_op.drop_constraint(
            "ck_analyst_reference_translated_abstract_length",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_analyst_reference_translated_title_length",
            type_="check",
        )
        batch_op.drop_column("translated_at")
        batch_op.drop_column("translation_error")
        batch_op.drop_column("translation_provider")
        batch_op.drop_column("translation_status")
        batch_op.drop_column("translated_abstract_ko")
        batch_op.drop_column("translated_title_ko")
        batch_op.drop_column("source_language")
