"""Add verified instruments, official disclosures, events, and retention records.

Revision ID: 20260725_0002
Revises: 20260725_0001
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260725_0002"
down_revision: str | None = "20260725_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("canonical_symbol", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("local_name", sa.String(length=200), nullable=True),
        sa.Column("exchange", sa.String(length=50), nullable=True),
        sa.Column("market", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=3), nullable=False),
        sa.Column(
            "currency",
            _enum("instrument_currency", "KRW", "USD", "OTHER"),
            nullable=False,
        ),
        sa.Column(
            "asset_type",
            _enum(
                "asset_type",
                "EQUITY",
                "ETF",
                "ADR",
                "CRYPTO",
                "INDEX",
                "COMMODITY",
                "FX",
                "UNKNOWN",
            ),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "verification_status",
            _enum(
                "instrument_verification_status",
                "VERIFIED",
                "UNVERIFIED",
                "AMBIGUOUS",
                "UNSUPPORTED",
                "DELISTED",
            ),
            nullable=False,
        ),
        sa.Column("verification_source", sa.String(length=50), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delisted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_instruments_active_market_symbol",
        "instruments",
        ["market", "canonical_symbol"],
        unique=True,
        sqlite_where=sa.text("active = 1"),
        postgresql_where=sa.text("active = true"),
    )

    with op.batch_alter_table("portfolio_items") as batch_op:
        batch_op.add_column(sa.Column("instrument_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_portfolio_items_instrument_id",
            "instruments",
            ["instrument_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_portfolio_items_instrument_id",
            ["instrument_id"],
            unique=False,
        )

    op.create_table(
        "instrument_provider_mappings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "instrument_id",
            sa.String(length=36),
            sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            _enum(
                "instrument_provider",
                "OPENDART",
                "SEC_EDGAR",
                "MANUAL",
                "SYSTEM_BASELINE",
            ),
            nullable=False,
        ),
        sa.Column("provider_symbol", sa.String(length=32), nullable=True),
        sa.Column("provider_company_id", sa.String(length=80), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=True),
        sa.Column("corp_code", sa.String(length=8), nullable=True),
        sa.Column("stock_code", sa.String(length=6), nullable=True),
        sa.Column("accession_prefix", sa.String(length=40), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_company_id",
            name="uq_instrument_mapping_provider_company",
        ),
    )
    op.create_index(
        "ix_instrument_provider_mappings_instrument_id",
        "instrument_provider_mappings",
        ["instrument_id"],
        unique=False,
    )
    op.create_index(
        "ix_instrument_mapping_provider_symbol",
        "instrument_provider_mappings",
        ["provider", "provider_symbol"],
        unique=False,
    )

    verification_values = (
        "OFFICIAL_CONFIRMED",
        "MULTI_SOURCE_CONFIRMED",
        "NEEDS_VERIFICATION",
        "UNVERIFIED",
        "CONFLICTING",
        "OFFICIALLY_DENIED",
        "CORRECTED",
        "STALE_REUSED",
    )
    lifecycle_values = ("ACTIVE", "UPDATED", "CORRECTED", "DENIED", "STALE", "ARCHIVED")

    op.create_table(
        "information_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column(
            "instrument_id",
            sa.String(length=36),
            sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("normalized_claim", sa.Text(), nullable=False),
        sa.Column("claim_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_material_change_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "lifecycle_status",
            _enum("event_lifecycle_status", *lifecycle_values),
            nullable=False,
        ),
        sa.Column(
            "verification_status",
            _enum("event_verification_status", *verification_values),
            nullable=False,
        ),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("official_source_count", sa.Integer(), nullable=False),
        sa.Column("current_summary", sa.String(length=2000), nullable=True),
        sa.Column("material_change", sa.Boolean(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_information_event_key"),
    )
    op.create_index(
        "ix_information_events_instrument_last_seen",
        "information_events",
        ["instrument_id", "last_seen_at"],
        unique=False,
    )

    op.create_table(
        "disclosure_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "instrument_id",
            sa.String(length=36),
            sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.String(length=36),
            sa.ForeignKey("information_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            _enum(
                "disclosure_provider",
                "OPENDART",
                "SEC_EDGAR",
                "MANUAL",
                "SYSTEM_BASELINE",
            ),
            nullable=False,
        ),
        sa.Column("provider_document_id", sa.String(length=100), nullable=False),
        sa.Column("accession_number", sa.String(length=40), nullable=True),
        sa.Column("receipt_number", sa.String(length=40), nullable=True),
        sa.Column("form_type", sa.String(length=50), nullable=True),
        sa.Column("report_type", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company_name", sa.String(length=300), nullable=False),
        sa.Column("official_url", sa.String(length=1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verification_status",
            _enum("disclosure_verification_status", *verification_values),
            nullable=False,
        ),
        sa.Column(
            "source_grade",
            _enum("disclosure_source_grade", "A", "B", "C", "D"),
            nullable=False,
        ),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("metadata_hash", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=2000), nullable=True),
        sa.Column(
            "summary_status",
            _enum("summary_status", "NOT_GENERATED", "STRUCTURED"),
            nullable=False,
        ),
        sa.Column("key_facts", sa.JSON(), nullable=False),
        sa.Column("material_change", sa.Boolean(), nullable=False),
        sa.Column(
            "correction_of_id",
            sa.String(length=36),
            sa.ForeignKey("disclosure_records.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "lifecycle_status",
            _enum("disclosure_lifecycle_status", *lifecycle_values),
            nullable=False,
        ),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_document_id",
            name="uq_disclosure_provider_document",
        ),
        sa.UniqueConstraint("official_url", name="uq_disclosure_official_url"),
    )
    op.create_index(
        "ix_disclosures_instrument_published",
        "disclosure_records",
        ["instrument_id", "published_at"],
        unique=False,
    )
    op.create_index(
        "ix_disclosures_accession",
        "disclosure_records",
        ["provider", "accession_number"],
        unique=False,
    )
    op.create_index(
        "ix_disclosures_receipt",
        "disclosure_records",
        ["provider", "receipt_number"],
        unique=False,
    )

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "event_id",
            sa.String(length=36),
            sa.ForeignKey("information_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "disclosure_id",
            sa.String(length=36),
            sa.ForeignKey("disclosure_records.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_title", sa.String(length=500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("independent_origin", sa.Boolean(), nullable=False),
        sa.Column("supports_claim", sa.Boolean(), nullable=False),
        sa.Column("contradicts_claim", sa.Boolean(), nullable=False),
        sa.Column("duplicate", sa.Boolean(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_hash", name="uq_evidence_hash"),
    )
    op.create_index(
        "ix_evidence_event_created",
        "evidence_items",
        ["event_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "provider",
            _enum(
                "collection_provider",
                "OPENDART",
                "SEC_EDGAR",
                "MANUAL",
                "SYSTEM_BASELINE",
            ),
            nullable=False,
        ),
        sa.Column(
            "run_type",
            _enum(
                "collection_run_type",
                "INSTRUMENT_SYNC",
                "DISCLOSURE_SYNC",
                "RETENTION_CLEANUP",
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            _enum(
                "collection_status",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "NOT_CONFIGURED",
                "DRY_RUN",
            ),
            nullable=False,
        ),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("cursor_before", sa.String(length=500), nullable=True),
        sa.Column("cursor_after", sa.String(length=500), nullable=True),
        sa.Column("error_summary", sa.String(length=1000), nullable=True),
        sa.Column("result_details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_collection_runs_provider_started",
        "collection_runs",
        ["provider", "started_at"],
        unique=False,
    )

    op.create_table(
        "provider_cursors",
        sa.Column(
            "provider",
            _enum(
                "cursor_provider",
                "OPENDART",
                "SEC_EDGAR",
                "MANUAL",
                "SYSTEM_BASELINE",
            ),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("cursor_value", sa.String(length=500), nullable=True),
        sa.Column("last_successful_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overlap_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider", "scope"),
    )

    op.create_table(
        "temporary_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "provider",
            _enum(
                "temporary_document_provider",
                "OPENDART",
                "SEC_EDGAR",
                "MANUAL",
                "SYSTEM_BASELINE",
            ),
            nullable=False,
        ),
        sa.Column("provider_document_id", sa.String(length=100), nullable=False),
        sa.Column("storage_reference", sa.String(length=1000), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_document_id",
            name="uq_temporary_document_provider_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("temporary_documents")
    op.drop_table("provider_cursors")
    op.drop_index("ix_collection_runs_provider_started", table_name="collection_runs")
    op.drop_table("collection_runs")
    op.drop_index("ix_evidence_event_created", table_name="evidence_items")
    op.drop_table("evidence_items")
    op.drop_index("ix_disclosures_receipt", table_name="disclosure_records")
    op.drop_index("ix_disclosures_accession", table_name="disclosure_records")
    op.drop_index("ix_disclosures_instrument_published", table_name="disclosure_records")
    op.drop_table("disclosure_records")
    op.drop_index(
        "ix_information_events_instrument_last_seen",
        table_name="information_events",
    )
    op.drop_table("information_events")
    op.drop_index(
        "ix_instrument_mapping_provider_symbol",
        table_name="instrument_provider_mappings",
    )
    op.drop_index(
        "ix_instrument_provider_mappings_instrument_id",
        table_name="instrument_provider_mappings",
    )
    op.drop_table("instrument_provider_mappings")
    with op.batch_alter_table("portfolio_items") as batch_op:
        batch_op.drop_index("ix_portfolio_items_instrument_id")
        batch_op.drop_constraint(
            "fk_portfolio_items_instrument_id",
            type_="foreignkey",
        )
        batch_op.drop_column("instrument_id")
    op.drop_index("uq_instruments_active_market_symbol", table_name="instruments")
    op.drop_table("instruments")
