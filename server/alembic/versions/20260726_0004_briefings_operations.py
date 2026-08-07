"""Add change briefings, notification delivery, and operation usage records.

Revision ID: 20260726_0004
Revises: 20260726_0003
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0004"
down_revision: str | None = "20260726_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
OLD_RUN_TYPES = (
    "INSTRUMENT_SYNC",
    "DISCLOSURE_SYNC",
    "RETENTION_CLEANUP",
    "NEWS_SYNC",
)
NEW_RUN_TYPES = (
    *OLD_RUN_TYPES,
    "BRIEFING_GENERATION",
    "EMAIL_DELIVERY",
    "USAGE_SNAPSHOT",
    "RADAR_CYCLE",
)


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    with op.batch_alter_table("collection_runs") as batch:
        batch.alter_column(
            "run_type",
            existing_type=_enum("collection_run_type", *OLD_RUN_TYPES),
            type_=_enum("collection_run_type", *NEW_RUN_TYPES),
            existing_nullable=False,
        )
        batch.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("duration_milliseconds", sa.Integer()))
        batch.add_column(sa.Column("delay_milliseconds", sa.Integer()))
        batch.add_column(sa.Column("success", sa.Boolean()))
        batch.add_column(
            sa.Column("partial_success", sa.Boolean(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("material_change_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("email_attempt_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("email_sent_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "retention_deleted_count", sa.Integer(), server_default="0", nullable=False
            )
        )
        batch.add_column(sa.Column("estimated_compute_seconds", sa.Integer()))

    op.create_table(
        "briefing_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "briefing_type",
            _enum(
                "briefing_type",
                "CHANGE_BRIEFING",
                "DAILY_DIGEST",
                "CORRECTION_NOTICE",
                "PROVIDER_HEALTH_NOTICE",
                "MANUAL_PREVIEW",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum(
                "briefing_status",
                "DRAFT",
                "READY",
                "SKIPPED_NO_CHANGE",
                "SENT",
                "PARTIALLY_SENT",
                "FAILED",
                "EXPIRED",
            ),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("compact_summary", sa.String(2000), nullable=False),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("material_change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("correction_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("denial_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("official_confirmed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("needs_verification_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("related_instrument_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_briefing_idempotency_key"),
    )
    op.create_index(
        "ix_briefings_generated_status",
        "briefing_records",
        ["generated_at", "status"],
    )
    op.create_table(
        "briefing_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "briefing_id",
            sa.String(36),
            sa.ForeignKey("briefing_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "information_event_id",
            sa.String(36),
            sa.ForeignKey("information_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("short_summary", sa.String(1000), nullable=False),
        sa.Column(
            "verification_status",
            _enum("briefing_verification_status", *VERIFICATION),
            nullable=False,
        ),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("material_change", sa.Boolean(), nullable=False),
        sa.Column("changed_facts", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("source_links", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("official_reference_links", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "trust_score >= 0 AND trust_score <= 100",
            name="ck_briefing_item_trust_score",
        ),
        sa.UniqueConstraint("state_fingerprint", name="uq_briefing_item_state"),
    )
    op.create_index(
        "ix_briefing_items_briefing_priority",
        "briefing_items",
        ["briefing_id", "priority"],
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "briefing_id",
            sa.String(36),
            sa.ForeignKey("briefing_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            _enum("notification_provider", "DISABLED", "SMTP", "RESEND", "FAKE"),
            nullable=False,
        ),
        sa.Column("recipient_hash", sa.String(64), nullable=False),
        sa.Column("provider_message_id", sa.String(200)),
        sa.Column(
            "status",
            _enum(
                "delivery_status",
                "PENDING",
                "SENT",
                "FAILED",
                "NOT_CONFIGURED",
                "DUPLICATE_BLOCKED",
            ),
            nullable=False,
        ),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_summary", sa.String(500)),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_delivery_idempotency_key"),
    )
    op.create_index(
        "ix_delivery_status_attempted",
        "notification_deliveries",
        ["status", "attempted_at"],
    )
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enabled", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "hourly_change_briefing_enabled",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("daily_digest_enabled", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "correction_notice_enabled", sa.Boolean(), server_default="1", nullable=False
        ),
        sa.Column(
            "provider_failure_notice_enabled",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(320)),
        sa.Column("timezone", sa.String(64), server_default="Asia/Seoul", nullable=False),
        sa.Column("daily_digest_hour", sa.Integer(), server_default="8", nullable=False),
        sa.Column("minimum_priority", sa.Integer(), server_default="50", nullable=False),
        sa.Column("include_watchlist", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("include_sold", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "daily_digest_hour >= 0 AND daily_digest_hour <= 23",
            name="ck_notification_daily_hour",
        ),
        sa.CheckConstraint(
            "minimum_priority >= 0 AND minimum_priority <= 100",
            name="ck_notification_minimum_priority",
        ),
    )
    op.create_table(
        "usage_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "action_minutes_availability",
            _enum(
                "action_minutes_availability",
                "AVAILABLE",
                "ESTIMATED",
                "NOT_CONFIGURED",
                "NOT_AVAILABLE",
            ),
            nullable=False,
        ),
        sa.Column("provider_reported_action_minutes", sa.Integer()),
        sa.Column(
            "locally_estimated_compute_minutes",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "database_bytes_availability",
            _enum(
                "database_bytes_availability",
                "AVAILABLE",
                "ESTIMATED",
                "NOT_CONFIGURED",
                "NOT_AVAILABLE",
            ),
            nullable=False,
        ),
        sa.Column("database_bytes", sa.Integer()),
        sa.Column(
            "email_count_availability",
            _enum(
                "email_count_availability",
                "AVAILABLE",
                "ESTIMATED",
                "NOT_CONFIGURED",
                "NOT_AVAILABLE",
            ),
            nullable=False,
        ),
        sa.Column("email_sent_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("collection_success_rate", sa.Integer()),
        sa.Column("scheduled_run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delayed_run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("average_duration_seconds", sa.Integer()),
        sa.Column(
            "operating_mode",
            _enum(
                "operating_mode",
                "NORMAL",
                "WARNING",
                "SAVING",
                "MINIMAL",
                "PAUSED",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_period_collected", "usage_snapshots", ["period", "collected_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_period_collected", table_name="usage_snapshots")
    op.drop_table("usage_snapshots")
    op.drop_table("notification_preferences")
    op.drop_index("ix_delivery_status_attempted", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_briefing_items_briefing_priority", table_name="briefing_items")
    op.drop_table("briefing_items")
    op.drop_index("ix_briefings_generated_status", table_name="briefing_records")
    op.drop_table("briefing_records")
    with op.batch_alter_table("collection_runs") as batch:
        batch.drop_column("estimated_compute_seconds")
        batch.drop_column("retention_deleted_count")
        batch.drop_column("email_sent_count")
        batch.drop_column("email_attempt_count")
        batch.drop_column("material_change_count")
        batch.drop_column("partial_success")
        batch.drop_column("success")
        batch.drop_column("delay_milliseconds")
        batch.drop_column("duration_milliseconds")
        batch.drop_column("scheduled_for")
        batch.alter_column(
            "run_type",
            existing_type=_enum("collection_run_type", *NEW_RUN_TYPES),
            type_=_enum("collection_run_type", *OLD_RUN_TYPES),
            existing_nullable=False,
        )
