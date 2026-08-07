"""Add automatic reference subscriptions and origin metadata.

Revision ID: 20260730_0013
Revises: 20260729_0012
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0013"
down_revision: str | None = "20260729_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_subscriptions",
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
            "subject_type",
            sa.Enum(
                "EXPERT",
                "INSTITUTION",
                "PUBLISHER",
                name="reference_subject_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "display_name",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "match_mode",
            sa.Enum(
                "ALL_SOURCE",
                "AUTHOR",
                "KEYWORD",
                name="reference_match_mode",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "match_terms",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_reference_subscription_source",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "subject_type",
            "display_name",
            name="uq_reference_subscription_source_subject",
        ),
    )

    op.create_index(
        "ix_reference_subscriptions_enabled_source",
        "reference_subscriptions",
        ["enabled", "source_id"],
    )

    ingest_mode_enum = sa.Enum(
        "MANUAL",
        "AUTOMATIC",
        name="analyst_ingest_mode",
        native_enum=False,
        create_constraint=True,
    )
    user_state_enum = sa.Enum(
        "NEW",
        "READ",
        "ARCHIVED",
        "HIDDEN",
        name="analyst_user_state",
        native_enum=False,
        create_constraint=True,
    )

    with op.batch_alter_table(
        "analyst_references",
        recreate="always",
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_id",
                sa.String(36),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "subscription_id",
                sa.String(36),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "provider_item_id",
                sa.String(300),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "ingest_mode",
                ingest_mode_enum,
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "user_state",
                user_state_enum,
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "discovered_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE analyst_references
            SET
                ingest_mode = 'MANUAL',
                user_state = 'NEW',
                discovered_at = COALESCE(
                    source_retrieved_at,
                    created_at,
                    CURRENT_TIMESTAMP
                )
            WHERE
                ingest_mode IS NULL
                OR user_state IS NULL
                OR discovered_at IS NULL
            """
        )
    )

    with op.batch_alter_table(
        "analyst_references",
        recreate="always",
    ) as batch_op:
        batch_op.alter_column(
            "ingest_mode",
            existing_type=ingest_mode_enum,
            nullable=False,
        )
        batch_op.alter_column(
            "user_state",
            existing_type=user_state_enum,
            nullable=False,
        )
        batch_op.alter_column(
            "discovered_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )

        batch_op.create_foreign_key(
            "fk_analyst_reference_source",
            "sources",
            ["source_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_analyst_reference_subscription",
            "reference_subscriptions",
            ["subscription_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_analyst_reference_source_provider_item",
            ["source_id", "provider_item_id"],
        )
        batch_op.create_check_constraint(
            "ck_analyst_reference_ingest_origin",
            "("
            "ingest_mode = 'MANUAL' "
            "AND source_id IS NULL "
            "AND subscription_id IS NULL "
            "AND provider_item_id IS NULL"
            ") OR ("
            "ingest_mode = 'AUTOMATIC' "
            "AND source_id IS NOT NULL "
            "AND subscription_id IS NOT NULL "
            "AND provider_item_id IS NOT NULL"
            ")",
        )

    op.create_index(
        "ix_analyst_references_subscription_published",
        "analyst_references",
        ["subscription_id", "published_at"],
    )
    op.create_index(
        "ix_analyst_references_state_published",
        "analyst_references",
        ["user_state", "published_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analyst_references_state_published",
        table_name="analyst_references",
    )
    op.drop_index(
        "ix_analyst_references_subscription_published",
        table_name="analyst_references",
    )

    with op.batch_alter_table(
        "analyst_references",
        recreate="always",
    ) as batch_op:
        batch_op.drop_constraint(
            "ck_analyst_reference_ingest_origin",
            type_="check",
        )
        batch_op.drop_constraint(
            "uq_analyst_reference_source_provider_item",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_analyst_reference_subscription",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_analyst_reference_source",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "analyst_user_state",
            type_="check",
        )
        batch_op.drop_constraint(
            "analyst_ingest_mode",
            type_="check",
        )

        batch_op.drop_column("discovered_at")
        batch_op.drop_column("user_state")
        batch_op.drop_column("ingest_mode")
        batch_op.drop_column("provider_item_id")
        batch_op.drop_column("subscription_id")
        batch_op.drop_column("source_id")

    op.drop_index(
        "ix_reference_subscriptions_enabled_source",
        table_name="reference_subscriptions",
    )
    op.drop_table("reference_subscriptions")
