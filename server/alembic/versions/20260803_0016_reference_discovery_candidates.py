"""Add reference discovery candidate staging.

Revision ID: 20260803_0016
Revises: 20260802_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_0016"
down_revision: str | None = "20260802_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_discovery_candidates",
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
            "subscription_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "provider_item_id",
            sa.String(300),
            nullable=False,
        ),
        sa.Column(
            "publisher_name",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(500),
            nullable=False,
        ),
        sa.Column(
            "analyst_name",
            sa.String(200),
            nullable=True,
        ),
        sa.Column(
            "canonical_url",
            sa.String(1000),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "verification_status",
            sa.Enum(
                "DATE_UNVERIFIED",
                "DATE_VERIFIED",
                "PROMOTED",
                "DISMISSED",
                name=("reference_discovery_candidate_status"),
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "seen_count",
            sa.Integer(),
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
        sa.CheckConstraint(
            "length(title) > 0",
            name=("ck_reference_discovery_candidate_title_not_empty"),
        ),
        sa.CheckConstraint(
            "seen_count >= 1",
            name=("ck_reference_discovery_candidate_seen_count_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["reference_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "provider_item_id",
            name=("uq_reference_discovery_candidate_source_provider_item"),
        ),
    )

    op.create_index(
        "ix_reference_discovery_candidates_status_last_seen",
        "reference_discovery_candidates",
        [
            "verification_status",
            "last_seen_at",
        ],
    )

    op.create_index(
        "ix_reference_discovery_candidates_subscription_last_seen",
        "reference_discovery_candidates",
        [
            "subscription_id",
            "last_seen_at",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reference_discovery_candidates_subscription_last_seen",
        table_name=("reference_discovery_candidates"),
    )

    op.drop_index(
        "ix_reference_discovery_candidates_status_last_seen",
        table_name=("reference_discovery_candidates"),
    )

    op.drop_table("reference_discovery_candidates")
