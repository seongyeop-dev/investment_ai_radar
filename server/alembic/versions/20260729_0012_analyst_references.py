"""Add analyst reference-only metadata tables.

Revision ID: 20260729_0012
Revises: 20260726_0011
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0012"
down_revision: str | None = "20260726_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyst_references",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("publisher_name", sa.String(200), nullable=False),
        sa.Column(
            "publisher_type",
            sa.Enum(
                "BROKER",
                "RESEARCH_HOUSE",
                "FINANCIAL_MEDIA",
                "INSTITUTION",
                "OTHER",
                name="analyst_publisher_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("analyst_name", sa.String(200), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("canonical_url", sa.String(1000), nullable=False),
        sa.Column(
            "access_type",
            sa.Enum(
                "PUBLIC",
                "LOGIN_REQUIRED",
                "PAYWALLED",
                "UNKNOWN",
                name="analyst_access_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "document_type",
            sa.Enum(
                "REPORT",
                "COMMENTARY",
                "INTERVIEW",
                "CONSENSUS",
                "OTHER",
                name="analyst_document_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("publisher_rating_raw", sa.String(200), nullable=True),
        sa.Column(
            "publisher_target_price_raw",
            sa.String(200),
            nullable=True,
        ),
        sa.Column("target_currency", sa.String(12), nullable=True),
        sa.Column("public_abstract", sa.String(300), nullable=True),
        sa.Column(
            "source_retrieved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "freshness_status",
            sa.Enum(
                "CURRENT",
                "AGING",
                "STALE",
                "UNKNOWN",
                name="analyst_freshness_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            name="ck_analyst_reference_title_not_empty",
        ),
        sa.CheckConstraint(
            "public_abstract IS NULL OR length(public_abstract) <= 300",
            name="ck_analyst_reference_abstract_length",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_url",
            name="uq_analyst_reference_canonical_url",
        ),
        sa.UniqueConstraint(
            "source_fingerprint",
            name="uq_analyst_reference_source_fingerprint",
        ),
    )

    op.create_index(
        "ix_analyst_references_published",
        "analyst_references",
        ["published_at"],
    )
    op.create_index(
        "ix_analyst_references_publisher_published",
        "analyst_references",
        ["publisher_name", "published_at"],
    )
    op.create_index(
        "ix_analyst_references_active_freshness",
        "analyst_references",
        ["is_active", "freshness_status"],
    )

    op.create_table(
        "analyst_reference_coverages",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "analyst_reference_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "portfolio_item_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "relation_type",
            sa.Enum(
                "PRIMARY",
                "MENTIONED",
                name="analyst_relation_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "mapping_confidence",
            sa.Enum(
                "VERIFIED",
                "NEEDS_REVIEW",
                name="analyst_mapping_confidence",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analyst_reference_id"],
            ["analyst_references.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"],
            ["portfolio_items.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analyst_reference_id",
            "portfolio_item_id",
            name="uq_analyst_reference_coverage_portfolio",
        ),
    )

    op.create_index(
        "ix_analyst_reference_coverages_portfolio_created",
        "analyst_reference_coverages",
        ["portfolio_item_id", "created_at"],
    )
    op.create_index(
        "ix_analyst_reference_coverages_reference",
        "analyst_reference_coverages",
        ["analyst_reference_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analyst_reference_coverages_reference",
        table_name="analyst_reference_coverages",
    )
    op.drop_index(
        "ix_analyst_reference_coverages_portfolio_created",
        table_name="analyst_reference_coverages",
    )
    op.drop_table("analyst_reference_coverages")

    op.drop_index(
        "ix_analyst_references_active_freshness",
        table_name="analyst_references",
    )
    op.drop_index(
        "ix_analyst_references_publisher_published",
        table_name="analyst_references",
    )
    op.drop_index(
        "ix_analyst_references_published",
        table_name="analyst_references",
    )
    op.drop_table("analyst_references")
