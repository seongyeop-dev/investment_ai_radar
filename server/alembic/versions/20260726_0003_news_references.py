"""Add news references, claims, source feeds, and event news counters.

Revision ID: 20260726_0003
Revises: 20260725_0002
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0003"
down_revision: str | None = "20260725_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


VERIFICATION = (
    "OFFICIAL_CONFIRMED",
    "MULTI_SOURCE_CONFIRMED",
    "NEEDS_VERIFICATION",
    "UNVERIFIED",
    "CONFLICTING",
    "OFFICIALLY_DENIED",
    "CORRECTED",
    "STALE_REUSED",
)
LIFECYCLE = ("ACTIVE", "UPDATED", "CORRECTED", "DENIED", "STALE", "ARCHIVED")
CERTAINTY = (
    "CONFIRMED",
    "ANNOUNCED",
    "PLANNED",
    "UNDER_REVIEW",
    "PROPOSED",
    "POSSIBLE",
    "SPECULATIVE",
    "UNSUPPORTED",
)


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("feed_url", sa.String(1000), nullable=True))
        batch.add_column(sa.Column("provider_type", sa.String(50), nullable=True))
        batch.add_column(
            sa.Column("language", sa.String(12), server_default="und", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "request_interval_seconds",
                sa.Integer(),
                server_default="60",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("timeout_seconds", sa.Integer(), server_default="10", nullable=False)
        )
        batch.add_column(
            sa.Column("max_items", sa.Integer(), server_default="50", nullable=False)
        )
        batch.add_column(sa.Column("original_source_name", sa.String(200), nullable=True))

    with op.batch_alter_table("information_events") as batch:
        batch.add_column(
            sa.Column(
                "news_reference_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "independent_origin_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "stale_reuse_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("latest_news_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("latest_official_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("changed_facts", sa.JSON(), server_default="[]", nullable=False)
        )
        batch.add_column(sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("denied_at", sa.DateTime(timezone=True), nullable=True))

    old_run_type = _enum(
        "collection_run_type",
        "INSTRUMENT_SYNC",
        "DISCLOSURE_SYNC",
        "RETENTION_CLEANUP",
    )
    new_run_type = _enum(
        "collection_run_type",
        "INSTRUMENT_SYNC",
        "DISCLOSURE_SYNC",
        "RETENTION_CLEANUP",
        "NEWS_SYNC",
    )
    with op.batch_alter_table("collection_runs") as batch:
        batch.alter_column(
            "run_type",
            existing_type=old_run_type,
            type_=new_run_type,
            existing_nullable=False,
        )

    op.create_table(
        "news_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.String(36),
            sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "portfolio_item_id",
            sa.String(36),
            sa.ForeignKey("portfolio_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            sa.String(36),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            _enum(
                "news_provider_type",
                "RSS",
                "ATOM",
                "OFFICIAL_IR_FEED",
                "MANUAL_REFERENCE",
                "DISABLED_DISCOVERY_PROVIDER",
            ),
            nullable=False,
        ),
        sa.Column("provider_item_id", sa.String(500), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("normalized_title", sa.String(500), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_domain", sa.String(253), nullable=False),
        sa.Column("canonical_url", sa.String(1000), nullable=False),
        sa.Column("canonical_url_hash", sa.String(64), nullable=False),
        sa.Column("original_url", sa.String(1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("snippet", sa.String(1000), nullable=True),
        sa.Column("short_summary", sa.String(1000), nullable=True),
        sa.Column(
            "summary_status",
            _enum(
                "news_summary_status",
                "NOT_GENERATED",
                "METADATA_ONLY",
                "RULE_BASED",
                "OFFICIAL_REFERENCE_BASED",
                "MANUAL_REVIEW_REQUIRED",
            ),
            nullable=False,
        ),
        sa.Column("primary_claim", sa.String(2000), nullable=False),
        sa.Column("claim_fingerprint", sa.String(64), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "verification_status",
            _enum("news_verification_status", *VERIFICATION),
            nullable=False,
        ),
        sa.Column(
            "source_grade",
            _enum("news_source_grade", "A", "B", "C", "D"),
            nullable=False,
        ),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column(
            "certainty_level",
            _enum("news_certainty_level", *CERTAINTY),
            nullable=False,
        ),
        sa.Column("independent_origin", sa.Boolean(), nullable=False),
        sa.Column("original_origin_key", sa.String(500), nullable=False),
        sa.Column(
            "duplicate_of_id",
            sa.String(36),
            sa.ForeignKey("news_references.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "information_event_id",
            sa.String(36),
            sa.ForeignKey("information_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("material_change", sa.Boolean(), nullable=False),
        sa.Column("stale_reused", sa.Boolean(), nullable=False),
        sa.Column(
            "lifecycle_status",
            _enum("news_lifecycle_status", *LIFECYCLE),
            nullable=False,
        ),
        sa.Column("official_reference_ids", sa.JSON(), nullable=False),
        sa.Column("changed_facts", sa.JSON(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "trust_score >= 0 AND trust_score <= 100",
            name="ck_news_trust_score_range",
        ),
        sa.UniqueConstraint("provider", "provider_item_id", name="uq_news_provider_item"),
        sa.UniqueConstraint("canonical_url_hash", name="uq_news_canonical_url_hash"),
    )
    op.create_index(
        "ix_news_instrument_published",
        "news_references",
        ["instrument_id", "published_at"],
    )
    op.create_index(
        "ix_news_claim_fingerprint",
        "news_references",
        ["claim_fingerprint"],
    )
    op.create_table(
        "news_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "news_reference_id",
            sa.String(36),
            sa.ForeignKey("news_references.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("information_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("claim_type", sa.String(80), nullable=False),
        sa.Column("claim_text", sa.String(2000), nullable=False),
        sa.Column("normalized_claim", sa.String(2000), nullable=False),
        sa.Column("claim_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "certainty_level",
            _enum("news_claim_certainty_level", *CERTAINTY),
            nullable=False,
        ),
        sa.Column(
            "supports_official_record_id",
            sa.String(36),
            sa.ForeignKey("disclosure_records.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "contradicts_official_record_id",
            sa.String(36),
            sa.ForeignKey("disclosure_records.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "verification_status",
            _enum("news_claim_verification_status", *VERIFICATION),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_news_claims_fingerprint", "news_claims", ["claim_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_news_claims_fingerprint", table_name="news_claims")
    op.drop_table("news_claims")
    op.drop_index("ix_news_claim_fingerprint", table_name="news_references")
    op.drop_index("ix_news_instrument_published", table_name="news_references")
    op.drop_table("news_references")
    new_run_type = _enum(
        "collection_run_type",
        "INSTRUMENT_SYNC",
        "DISCLOSURE_SYNC",
        "RETENTION_CLEANUP",
        "NEWS_SYNC",
    )
    old_run_type = _enum(
        "collection_run_type",
        "INSTRUMENT_SYNC",
        "DISCLOSURE_SYNC",
        "RETENTION_CLEANUP",
    )
    with op.batch_alter_table("collection_runs") as batch:
        batch.alter_column(
            "run_type",
            existing_type=new_run_type,
            type_=old_run_type,
            existing_nullable=False,
        )
    with op.batch_alter_table("information_events") as batch:
        batch.drop_column("denied_at")
        batch.drop_column("corrected_at")
        batch.drop_column("changed_facts")
        batch.drop_column("latest_official_at")
        batch.drop_column("latest_news_at")
        batch.drop_column("stale_reuse_count")
        batch.drop_column("independent_origin_count")
        batch.drop_column("news_reference_count")
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("original_source_name")
        batch.drop_column("max_items")
        batch.drop_column("timeout_seconds")
        batch.drop_column("request_interval_seconds")
        batch.drop_column("language")
        batch.drop_column("provider_type")
        batch.drop_column("feed_url")
