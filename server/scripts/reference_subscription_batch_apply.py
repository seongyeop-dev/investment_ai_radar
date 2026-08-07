from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from sqlalchemy import func, select

from app.database import Database
from app.models.analyst_references import (
    AnalystIngestMode,
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
    ReferenceDiscoveryCandidateRecord,
)
from app.models.database import SourceRecord
from app.models.disclosures import InformationEventRecord
from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)
from app.providers.reference_translation_nllb import (
    LocalNllbTranslationProvider,
)
from app.services.reference_batch_ingest import (
    ingest_reference_candidates,
)
from app.services.reference_discovery_staging import (
    partition_reference_candidates,
    stage_unverified_reference_candidates,
)
from app.services.reference_freshness_refresh import (
    refresh_automatic_reference_freshness,
)
from app.services.reference_index_dispatch import (
    fetch_reference_index_candidates,
)

EXPECTED_VALIDATION_DATABASE_NAME = "investment_ai_radar_0014_validation.db"
EXPECTED_DISPOSABLE_VALIDATION_DATABASE_NAME = "investment_ai_radar_0016_batch_validation.db"
EXPECTED_REAL_DATABASE_NAME = "investment_ai_radar.db"

DISPOSABLE_VALIDATION_ROOT = (
    Path(__file__).resolve().parents[2] / ".local" / "data" / "batch_apply_validation"
).resolve()
EXPECTED_REVISION = "20260803_0017"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database-path",
        required=True,
    )
    parser.add_argument(
        "--subscription-name",
        default="Howard Marks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--expect-created",
        type=int,
        default=None,
        help=(
            "Optional exact created-count assertion. "
            "Use for validation runs; omit for operational runs."
        ),
    )
    parser.add_argument(
        "--confirm-validation-write",
        action="store_true",
    )
    parser.add_argument(
        "--allow-real-database",
        action="store_true",
        help=(
            "Explicitly allow investment_ai_radar.db. The confirmation flag is still required."
        ),
    )

    parser.add_argument(
        "--allow-disposable-validation-database",
        action="store_true",
        help=(
            "Explicitly allow the fixed-name disposable "
            "validation database under "
            ".local/data/batch_apply_validation."
        ),
    )

    return parser.parse_args()


def verify_validation_database(
    path: Path,
    *,
    allow_real_database: bool,
    allow_disposable_validation_database: bool,
) -> str:
    path = path.resolve()

    if not path.is_file():
        raise RuntimeError(f"Database does not exist: {path}")

    if allow_real_database and allow_disposable_validation_database:
        raise RuntimeError(
            "--allow-real-database and "
            "--allow-disposable-validation-database "
            "cannot be used together"
        )

    if path.name == EXPECTED_VALIDATION_DATABASE_NAME:
        if allow_real_database:
            raise RuntimeError(
                "--allow-real-database may only be used with investment_ai_radar.db"
            )

        if allow_disposable_validation_database:
            raise RuntimeError(
                "--allow-disposable-validation-database "
                "may only be used with the disposable "
                "validation database"
            )

    elif path.name == EXPECTED_DISPOSABLE_VALIDATION_DATABASE_NAME:
        if not allow_disposable_validation_database:
            raise RuntimeError(
                "--allow-disposable-validation-database "
                "is required for the disposable "
                "validation database"
            )

        try:
            relative_path = path.relative_to(DISPOSABLE_VALIDATION_ROOT)
        except ValueError as exc:
            raise RuntimeError(
                f"Disposable validation database must be under {DISPOSABLE_VALIDATION_ROOT}"
            ) from exc

        if len(relative_path.parts) != 2:
            raise RuntimeError(
                "Disposable validation database must "
                "be located exactly one run directory "
                "below the disposable validation root"
            )

    elif path.name == EXPECTED_REAL_DATABASE_NAME:
        if allow_disposable_validation_database:
            raise RuntimeError(
                "--allow-disposable-validation-database "
                "may not be used with "
                "investment_ai_radar.db"
            )

        if not allow_real_database:
            raise RuntimeError("--allow-real-database is required for investment_ai_radar.db")

    else:
        raise RuntimeError(f"Unsupported database file. Received: {path.name}")

    connection = sqlite3.connect(path)

    try:
        revision_row = connection.execute(
            """
            SELECT version_num
            FROM alembic_version
            """
        ).fetchone()

        if revision_row is None:
            raise RuntimeError("Alembic revision was not found")

        revision = revision_row[0]

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]

        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

    finally:
        connection.close()

    if revision != EXPECTED_REVISION:
        raise RuntimeError(f"Expected revision {EXPECTED_REVISION}, found {revision}")

    if integrity != "ok":
        raise RuntimeError(f"Database integrity failed: {integrity}")

    if foreign_key_errors:
        raise RuntimeError(
            f"Database foreign key verification failed: {len(foreign_key_errors)} error(s)"
        )

    return revision


def count_rows(
    session,
    model: type,
) -> int:
    value = session.scalar(select(func.count()).select_from(model))

    return int(value or 0)


def main() -> int:
    args = parse_args()

    if not args.confirm_validation_write:
        raise RuntimeError("--confirm-validation-write is required")

    if args.limit < 1:
        raise RuntimeError("--limit must be at least 1")

    database_path = Path(args.database_path).resolve()

    revision = verify_validation_database(
        database_path,
        allow_real_database=(args.allow_real_database),
        allow_disposable_validation_database=(args.allow_disposable_validation_database),
    )

    database_url = "sqlite+pysqlite:///" + database_path.as_posix()

    database = Database(database_url)

    with database.session_scope() as session:
        subscriptions = list(
            session.scalars(
                select(ReferenceSubscriptionRecord).where(
                    ReferenceSubscriptionRecord.display_name == args.subscription_name,
                )
            )
        )

        if len(subscriptions) != 1:
            raise RuntimeError(f"Expected exactly one subscription, found {len(subscriptions)}")

        subscription = subscriptions[0]

        source = session.get(
            SourceRecord,
            subscription.source_id,
        )

        if source is None:
            raise RuntimeError("Subscription source was not found")

        if not source.official or not source.enabled:
            raise RuntimeError("Source must be official and enabled")

        before_references = count_rows(
            session,
            AnalystReferenceRecord,
        )
        before_coverages = count_rows(
            session,
            AnalystReferenceCoverageRecord,
        )
        before_events = count_rows(
            session,
            InformationEventRecord,
        )

        before_discovery_candidates = count_rows(
            session,
            ReferenceDiscoveryCandidateRecord,
        )

        before_subscription_candidates = int(
            session.scalar(
                select(func.count())
                .select_from(ReferenceDiscoveryCandidateRecord)
                .where(
                    ReferenceDiscoveryCandidateRecord.subscription_id == str(subscription.id),
                )
            )
            or 0
        )

        before_automatic = int(
            session.scalar(
                select(func.count())
                .select_from(AnalystReferenceRecord)
                .where(
                    AnalystReferenceRecord.subscription_id == str(subscription.id),
                    AnalystReferenceRecord.ingest_mode == AnalystIngestMode.AUTOMATIC,
                )
            )
            or 0
        )

        if not subscription.enabled:
            print("=" * 72)
            print("REFERENCE SUBSCRIPTION BATCH SKIPPED")
            print("=" * 72)
            print("Database:", database_path)
            print("Subscription:", subscription.display_name)
            print("Status: SKIPPED_DISABLED")
            print("External HTTP requests: 0")
            print("Database writes: 0")
            print("Result: REFERENCE_SUBSCRIPTION_SKIPPED_DISABLED")
            return 0
        dispatch_result = fetch_reference_index_candidates(source)

        candidates = dispatch_result.candidates

        partition = partition_reference_candidates(candidates)

        translation_provider = LocalNllbTranslationProvider(
            cache_dir=(
                Path(__file__).resolve().parents[2] / ".local" / "models" / "huggingface"
            ),
            local_files_only=True,
        )

        freshness_summary = refresh_automatic_reference_freshness(
            session,
            subscription_id=str(subscription.id),
        )

        staging_summary = stage_unverified_reference_candidates(
            session,
            source=source,
            subscription_id=str(subscription.id),
            candidates=(partition.date_unverified),
        )

        summary = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=(partition.date_verified),
            creation_limit=args.limit,
            dry_run=False,
            translation_provider=translation_provider,
        )

        session.flush()

        after_references = count_rows(
            session,
            AnalystReferenceRecord,
        )
        after_coverages = count_rows(
            session,
            AnalystReferenceCoverageRecord,
        )
        after_events = count_rows(
            session,
            InformationEventRecord,
        )

        after_discovery_candidates = count_rows(
            session,
            ReferenceDiscoveryCandidateRecord,
        )

        after_subscription_candidates = int(
            session.scalar(
                select(func.count())
                .select_from(ReferenceDiscoveryCandidateRecord)
                .where(
                    ReferenceDiscoveryCandidateRecord.subscription_id == str(subscription.id),
                )
            )
            or 0
        )

        after_automatic = int(
            session.scalar(
                select(func.count())
                .select_from(AnalystReferenceRecord)
                .where(
                    AnalystReferenceRecord.subscription_id == str(subscription.id),
                    AnalystReferenceRecord.ingest_mode == AnalystIngestMode.AUTOMATIC,
                )
            )
            or 0
        )

        if args.expect_created is not None and summary.created != args.expect_created:
            raise RuntimeError(
                "Unexpected created count. "
                f"Expected {args.expect_created}, "
                f"found {summary.created}. "
                "Transaction will be rolled back."
            )

        if before_coverages != after_coverages:
            raise RuntimeError(
                "Reference coverage count changed. Transaction will be rolled back."
            )

        if before_events != after_events:
            raise RuntimeError(
                "Information event count changed. Transaction will be rolled back."
            )

        created_ids = [
            result.reference_id
            for result in summary.results
            if (result.created and result.reference_id)
        ]

        created_rows = []

        if created_ids:
            created_rows = list(
                session.scalars(
                    select(AnalystReferenceRecord)
                    .where(AnalystReferenceRecord.id.in_(created_ids))
                    .order_by(AnalystReferenceRecord.published_at.desc())
                )
            )

        print("=" * 72)
        print("REFERENCE VALIDATION BATCH APPLY")
        print("=" * 72)
        print("Database:", database_path)
        print("Revision:", revision)
        print("Subscription:", subscription.display_name)
        print("Source:", source.name)
        print(
            "Final URL:",
            dispatch_result.final_urls[0],
        )
        print(
            "HTTP status:",
            dispatch_result.status_codes[0],
        )
        print(
            "Index requests:",
            dispatch_result.request_count,
        )
        print("Candidates:", len(candidates))
        print(
            "Date-verified candidates:",
            len(partition.date_verified),
        )
        print(
            "Date-unverified candidates:",
            len(partition.date_unverified),
        )
        print(
            "Staging scanned:",
            staging_summary.scanned,
        )
        print(
            "Staging inserted:",
            staging_summary.inserted,
        )
        print(
            "Staging refreshed:",
            staging_summary.refreshed,
        )
        print(
            "Staging verified-date skipped:",
            staging_summary.skipped_verified_date,
        )
        print("Creation limit:", summary.creation_limit)
        print(
            "Freshness examined:",
            freshness_summary.examined,
        )
        print(
            "Freshness updated:",
            freshness_summary.updated,
        )
        print(
            "Freshness CURRENT:",
            freshness_summary.current,
        )
        print(
            "Freshness AGING:",
            freshness_summary.aging,
        )
        print(
            "Freshness STALE:",
            freshness_summary.stale,
        )
        print(
            "Freshness UNKNOWN:",
            freshness_summary.unknown,
        )
        print("Created:", summary.created)
        print("Duplicates:", summary.duplicates)
        print(
            "Historical backlog skipped:",
            summary.backlog_skipped,
        )
        print()

        print("CREATED ITEMS")

        if not created_rows:
            print("- NONE")

        for index, record in enumerate(
            created_rows,
            start=1,
        ):
            print()
            print(f"{index}. {record.title}")
            print(
                "   Published:",
                record.published_at.isoformat(),
            )
            print(
                "   Provider item:",
                record.provider_item_id,
            )
            print(
                "   Ingest mode:",
                record.ingest_mode.value,
            )
            print(
                "   Source language:",
                record.source_language,
            )
            print(
                "   Translation status:",
                record.translation_status.value,
            )
            print(
                "   Korean title:",
                record.translated_title_ko or "-",
            )
            print(
                "   Translation provider:",
                record.translation_provider or "-",
            )
            print(
                "   URL:",
                record.canonical_url,
            )

        print()
        print("DATABASE COUNTS")
        print(
            "Analyst references:",
            before_references,
            "->",
            after_references,
        )
        print(
            "Automatic references:",
            before_automatic,
            "->",
            after_automatic,
        )
        print(
            "Reference coverages:",
            before_coverages,
            "->",
            after_coverages,
        )
        print(
            "Information events:",
            before_events,
            "->",
            after_events,
        )
        print(
            "Discovery candidates:",
            before_discovery_candidates,
            "->",
            after_discovery_candidates,
        )
        print(
            "Subscription discovery candidates:",
            before_subscription_candidates,
            "->",
            after_subscription_candidates,
        )
        print(
            "External documents downloaded:",
            dispatch_result.external_documents_downloaded,
        )
        print("Result: REFERENCE VALIDATION BATCH APPLY PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
