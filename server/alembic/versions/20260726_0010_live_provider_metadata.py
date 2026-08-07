"""Add verified provider mapping metadata, public quotes, and market sessions.

Revision ID: 20260726_0010
Revises: 20260726_0009
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0010"
down_revision: str | None = "20260726_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_provider_mappings") as batch:
        batch.drop_constraint("instrument_provider", type_="check")
        batch.create_check_constraint(
            "instrument_provider",
            "provider IN ('OPENDART','SEC_EDGAR','UPBIT','BINANCE','MANUAL','SYSTEM_BASELINE')",
        )
        batch.alter_column(
            "verified_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
        batch.add_column(sa.Column("official_name", sa.String(300), nullable=True))
        batch.add_column(
            sa.Column(
                "mapping_status",
                sa.String(20),
                nullable=False,
                server_default="VERIFIED",
            )
        )
        batch.add_column(
            sa.Column(
                "match_method",
                sa.String(30),
                nullable=False,
                server_default="NONE",
            )
        )
        batch.add_column(
            sa.Column("confidence", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("conflict_reason", sa.String(500), nullable=True))
        batch.create_check_constraint(
            "instrument_mapping_status",
            "mapping_status IN "
            "('VERIFIED','CANDIDATE','UNRESOLVED','CONFLICTING','UNSUPPORTED','STALE')",
        )
        batch.create_check_constraint(
            "instrument_mapping_match_method",
            "match_method IN "
            "('EXACT_STOCK_CODE','EXACT_TICKER_EXCHANGE','EXACT_PROVIDER_SYMBOL',"
            "'MANUAL_CONFIRMED','NAME_CANDIDATE','NONE')",
        )
        batch.create_check_constraint(
            "ck_instrument_mapping_confidence",
            "confidence >= 0 AND confidence <= 100",
        )

    op.create_table(
        "provider_sync_states",
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("capability", sa.String(40), nullable=False),
        sa.Column("configured", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(100), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider", "capability"),
    )
    op.create_table(
        "quote_snapshots",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("instrument_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_symbol", sa.String(32), nullable=False),
        sa.Column("price", sa.Numeric(38, 18), nullable=False),
        sa.Column("quote_currency", sa.String(10), nullable=False),
        sa.Column("provider_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_status", sa.String(20), nullable=False),
        sa.Column("source_status", sa.String(30), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price > 0", name="ck_quote_snapshot_positive_price"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_quote_snapshot_fingerprint"),
    )
    op.create_index(
        "ix_quote_snapshots_instrument_id",
        "quote_snapshots",
        ["instrument_id"],
    )
    op.create_index(
        "ix_quote_latest_provider_instrument",
        "quote_snapshots",
        ["provider", "instrument_id", "fetched_at"],
    )
    op.create_table(
        "market_session_cache",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("market", sa.String(20), nullable=False),
        sa.Column("session_date", sa.String(10), nullable=False),
        sa.Column("market_timezone", sa.String(64), nullable=False),
        sa.Column("open_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("holiday", sa.Boolean(), nullable=False),
        sa.Column("early_close", sa.Boolean(), nullable=False),
        sa.Column("schedule_status", sa.String(30), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("library_version", sa.String(30), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market", "session_date", name="uq_market_session_cache"),
    )


def downgrade() -> None:
    op.drop_table("market_session_cache")
    op.drop_index(
        "ix_quote_latest_provider_instrument",
        table_name="quote_snapshots",
    )
    op.drop_index("ix_quote_snapshots_instrument_id", table_name="quote_snapshots")
    op.drop_table("quote_snapshots")
    op.drop_table("provider_sync_states")
    with op.batch_alter_table("instrument_provider_mappings") as batch:
        batch.drop_constraint("ck_instrument_mapping_confidence", type_="check")
        batch.drop_constraint("instrument_mapping_match_method", type_="check")
        batch.drop_constraint("instrument_mapping_status", type_="check")
        batch.drop_column("conflict_reason")
        batch.drop_column("last_checked_at")
        batch.drop_column("confidence")
        batch.drop_column("match_method")
        batch.drop_column("mapping_status")
        batch.drop_column("official_name")
        batch.alter_column(
            "verified_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch.drop_constraint("instrument_provider", type_="check")
        batch.create_check_constraint(
            "instrument_provider",
            "provider IN ('OPENDART','SEC_EDGAR','MANUAL','SYSTEM_BASELINE')",
        )
