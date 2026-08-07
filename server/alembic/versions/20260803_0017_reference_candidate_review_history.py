"""Add candidate review metadata and history.

Revision ID: 20260803_0017
Revises: 20260803_0016
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_0017"
down_revision: str | None = "20260803_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CANDIDATE_STATUS_VALUES = (
    "DATE_UNVERIFIED",
    "DATE_VERIFIED",
    "PROMOTED",
    "DISMISSED",
)

PUBLISHER_TYPE_VALUES = (
    "BROKER",
    "RESEARCH_HOUSE",
    "FINANCIAL_MEDIA",
    "INSTITUTION",
    "OTHER",
)

ACCESS_TYPE_VALUES = (
    "PUBLIC",
    "LOGIN_REQUIRED",
    "PAYWALLED",
    "UNKNOWN",
)

DOCUMENT_TYPE_VALUES = (
    "REPORT",
    "COMMENTARY",
    "INTERVIEW",
    "CONSENSUS",
    "OTHER",
)


def upgrade() -> None:
    with op.batch_alter_table("reference_discovery_candidates") as batch_op:
        batch_op.add_column(
            sa.Column(
                "public_abstract",
                sa.String(300),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "publisher_type",
                sa.Enum(
                    *PUBLISHER_TYPE_VALUES,
                    name=("reference_discovery_candidate_publisher_type"),
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=False,
                server_default="INSTITUTION",
            )
        )
        batch_op.add_column(
            sa.Column(
                "access_type",
                sa.Enum(
                    *ACCESS_TYPE_VALUES,
                    name=("reference_discovery_candidate_access_type"),
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=False,
                server_default="PUBLIC",
            )
        )
        batch_op.add_column(
            sa.Column(
                "document_type",
                sa.Enum(
                    *DOCUMENT_TYPE_VALUES,
                    name=("reference_discovery_candidate_document_type"),
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=False,
                server_default="OTHER",
            )
        )
        batch_op.add_column(
            sa.Column(
                "promoted_reference_id",
                sa.String(36),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "reviewed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_check_constraint(
            ("ck_reference_discovery_candidate_abstract_length"),
            ("public_abstract IS NULL OR length(public_abstract) <= 300"),
        )
        batch_op.create_foreign_key(
            ("fk_reference_discovery_candidate_promoted_reference"),
            "analyst_references",
            ["promoted_reference_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.create_index(
        ("ix_reference_discovery_candidates_promoted_reference"),
        "reference_discovery_candidates",
        ["promoted_reference_id"],
    )

    op.create_table(
        "reference_discovery_candidate_review_history",
        sa.Column(
            "id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "previous_status",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "new_status",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "verified_published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "promoted_reference_id",
            sa.String(36),
            nullable=True,
        ),
        sa.Column(
            "reason",
            sa.String(1000),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('VERIFY_DATE', 'PROMOTE', 'DISMISS')",
            name=("ck_reference_candidate_review_action"),
        ),
        sa.CheckConstraint(
            "previous_status IN ('DATE_UNVERIFIED', 'DATE_VERIFIED', 'PROMOTED', 'DISMISSED')",
            name=("ck_reference_candidate_review_previous_status"),
        ),
        sa.CheckConstraint(
            "new_status IN ('DATE_UNVERIFIED', 'DATE_VERIFIED', 'PROMOTED', 'DISMISSED')",
            name=("ck_reference_candidate_review_new_status"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR length(reason) <= 1000",
            name=("ck_reference_candidate_review_reason_length"),
        ),
        sa.CheckConstraint(
            "("
            "action = 'VERIFY_DATE' "
            "AND verified_published_at IS NOT NULL "
            "AND promoted_reference_id IS NULL "
            "AND new_status = 'DATE_VERIFIED'"
            ") OR ("
            "action = 'PROMOTE' "
            "AND verified_published_at IS NOT NULL "
            "AND promoted_reference_id IS NOT NULL "
            "AND new_status = 'PROMOTED'"
            ") OR ("
            "action = 'DISMISS' "
            "AND promoted_reference_id IS NULL "
            "AND new_status = 'DISMISSED'"
            ")",
            name=("ck_reference_candidate_review_action_payload"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["reference_discovery_candidates.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["promoted_reference_id"],
            ["analyst_references.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_reference_candidate_review_candidate_created",
        "reference_discovery_candidate_review_history",
        ["candidate_id", "created_at"],
    )
    op.create_index(
        "ix_reference_candidate_review_action_created",
        "reference_discovery_candidate_review_history",
        ["action", "created_at"],
    )
    op.create_index(
        "ix_reference_candidate_review_promoted_reference",
        "reference_discovery_candidate_review_history",
        ["promoted_reference_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reference_candidate_review_promoted_reference",
        table_name=("reference_discovery_candidate_review_history"),
    )
    op.drop_index(
        "ix_reference_candidate_review_action_created",
        table_name=("reference_discovery_candidate_review_history"),
    )
    op.drop_index(
        "ix_reference_candidate_review_candidate_created",
        table_name=("reference_discovery_candidate_review_history"),
    )
    op.drop_table("reference_discovery_candidate_review_history")

    op.drop_index(
        ("ix_reference_discovery_candidates_promoted_reference"),
        table_name="reference_discovery_candidates",
    )

    with op.batch_alter_table("reference_discovery_candidates") as batch_op:
        batch_op.drop_constraint(
            ("fk_reference_discovery_candidate_promoted_reference"),
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            ("ck_reference_discovery_candidate_abstract_length"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("reference_discovery_candidate_document_type"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("reference_discovery_candidate_access_type"),
            type_="check",
        )
        batch_op.drop_constraint(
            ("reference_discovery_candidate_publisher_type"),
            type_="check",
        )
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("promoted_reference_id")
        batch_op.drop_column("document_type")
        batch_op.drop_column("access_type")
        batch_op.drop_column("publisher_type")
        batch_op.drop_column("public_abstract")
