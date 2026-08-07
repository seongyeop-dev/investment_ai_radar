"""Add analysis-first thesis, impact, decision review, and event records.

Revision ID: 20260726_0011
Revises: 20260726_0010
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0011"
down_revision: str | None = "20260726_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investment_theses",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("portfolio_item_id", sa.String(36), nullable=False),
        sa.Column("thesis_summary", sa.Text(), nullable=False),
        sa.Column("investment_purpose", sa.String(1000), nullable=False),
        sa.Column("investment_horizon", sa.String(30), nullable=False),
        sa.Column("original_reasons", sa.JSON(), nullable=False),
        sa.Column("expected_catalysts", sa.JSON(), nullable=False),
        sa.Column("key_risks", sa.JSON(), nullable=False),
        sa.Column("conditions_to_add", sa.JSON(), nullable=False),
        sa.Column("conditions_to_hold", sa.JSON(), nullable=False),
        sa.Column("conditions_to_reduce", sa.JSON(), nullable=False),
        sa.Column("conditions_to_exit", sa.JSON(), nullable=False),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False),
        sa.Column("questions_to_verify", sa.JSON(), nullable=False),
        sa.Column("user_conviction", sa.String(20), nullable=False),
        sa.Column("thesis_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"], ["portfolio_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_item_id", name="uq_investment_thesis_portfolio"),
    )
    op.create_table(
        "portfolio_impacts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("portfolio_item_id", sa.String(36), nullable=False),
        sa.Column("thesis_id", sa.String(36), nullable=True),
        sa.Column("relevance", sa.String(30), nullable=False),
        sa.Column("impact_direction", sa.String(20), nullable=False),
        sa.Column("impact_strength", sa.String(20), nullable=False),
        sa.Column("impact_horizon", sa.String(30), nullable=False),
        sa.Column("thesis_effect", sa.String(30), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("evidence_strength", sa.String(20), nullable=False),
        sa.Column("one_line_summary", sa.String(1000), nullable=False),
        sa.Column("impact_path", sa.JSON(), nullable=False),
        sa.Column("supporting_factors", sa.JSON(), nullable=False),
        sa.Column("opposing_factors", sa.JSON(), nullable=False),
        sa.Column("conditions_to_watch", sa.JSON(), nullable=False),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("source_links", sa.JSON(), nullable=False),
        sa.Column("verification_status", sa.String(40), nullable=False),
        sa.Column("generated_by", sa.String(20), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("human_decision_required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["information_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"], ["portfolio_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["thesis_id"], ["investment_theses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "portfolio_item_id",
            name="uq_portfolio_impact_event_portfolio",
        ),
    )
    op.create_index(
        "ix_portfolio_impacts_portfolio_generated",
        "portfolio_impacts",
        ["portfolio_item_id", "generated_at"],
    )
    op.create_index("ix_portfolio_impacts_event", "portfolio_impacts", ["event_id"])
    op.create_table(
        "decision_reviews",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("portfolio_item_id", sa.String(36), nullable=False),
        sa.Column("thesis_id", sa.String(36), nullable=True),
        sa.Column("direction", sa.String(30), nullable=False),
        sa.Column("thesis_status", sa.String(30), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("evidence_strength", sa.String(20), nullable=False),
        sa.Column("why_now", sa.String(2000), nullable=False),
        sa.Column("supporting_evidence", sa.JSON(), nullable=False),
        sa.Column("contrary_evidence", sa.JSON(), nullable=False),
        sa.Column("positive_factors", sa.JSON(), nullable=False),
        sa.Column("negative_factors", sa.JSON(), nullable=False),
        sa.Column("conditions_to_add", sa.JSON(), nullable=False),
        sa.Column("conditions_to_hold", sa.JSON(), nullable=False),
        sa.Column("conditions_to_reduce", sa.JSON(), nullable=False),
        sa.Column("conditions_to_exit", sa.JSON(), nullable=False),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("manual_reference_price", sa.Numeric(38, 18), nullable=True),
        sa.Column("average_cost_snapshot", sa.Numeric(38, 18), nullable=True),
        sa.Column("quantity_snapshot", sa.Numeric(38, 18), nullable=False),
        sa.Column("risk_profile_snapshot", sa.JSON(), nullable=False),
        sa.Column("based_on_event_ids", sa.JSON(), nullable=False),
        sa.Column("generated_by", sa.String(20), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_decision", sa.String(1000), nullable=True),
        sa.Column("human_decision_required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"], ["portfolio_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["thesis_id"], ["investment_theses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_decision_reviews_portfolio_generated",
        "decision_reviews",
        ["portfolio_item_id", "generated_at"],
    )
    op.create_table(
        "economic_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("official_source_name", sa.String(300), nullable=False),
        sa.Column("official_source_url", sa.String(1000), nullable=False),
        sa.Column("related_portfolio_item_ids", sa.JSON(), nullable=False),
        sa.Column("expected_impact_path", sa.JSON(), nullable=False),
        sa.Column("pre_release_checks", sa.JSON(), nullable=False),
        sa.Column("actual_result", sa.String(2000), nullable=True),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economic_events_scheduled", "economic_events", ["scheduled_at"])


def downgrade() -> None:
    op.drop_index("ix_economic_events_scheduled", table_name="economic_events")
    op.drop_table("economic_events")
    op.drop_index("ix_decision_reviews_portfolio_generated", table_name="decision_reviews")
    op.drop_table("decision_reviews")
    op.drop_index("ix_portfolio_impacts_event", table_name="portfolio_impacts")
    op.drop_index("ix_portfolio_impacts_portfolio_generated", table_name="portfolio_impacts")
    op.drop_table("portfolio_impacts")
    op.drop_table("investment_theses")
