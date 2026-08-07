from __future__ import annotations

import argparse
import os

from sqlalchemy import func, select

from app.database import Database
from app.models.analyst_references import (
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
)
from app.models.database import SourceRecord
from app.models.disclosures import InformationEventRecord
from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)
from app.services.reference_batch_ingest import (
    ingest_reference_candidates,
)
from app.services.reference_index_dispatch import (
    fetch_reference_index_candidates,
)
from app.services.reference_sync import reference_item_matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview the newest public reference items for one "
            "registered subscription without writing to the database."
        )
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
        "--expect-would-create",
        type=int,
        default=None,
        help=("Expected number of newly planned references. Defaults to --limit when omitted."),
    )
    parser.add_argument(
        "--expect-duplicates",
        type=int,
        default=None,
        help="Optional expected duplicate count.",
    )

    return parser.parse_args()


def count_rows(
    session,
    model: type,
) -> int:
    value = session.scalar(select(func.count()).select_from(model))

    return int(value or 0)


def main() -> int:
    args = parse_args()

    if args.limit < 1:
        raise RuntimeError("--limit must be at least 1")

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    database = Database(database_url)

    with database.session_scope() as session:
        subscriptions = list(
            session.scalars(
                select(ReferenceSubscriptionRecord).where(
                    ReferenceSubscriptionRecord.display_name == args.subscription_name,
                    ReferenceSubscriptionRecord.enabled.is_(True),
                )
            )
        )

        if len(subscriptions) != 1:
            raise RuntimeError(
                "Expected exactly one enabled subscription "
                f"named {args.subscription_name!r}, "
                f"found {len(subscriptions)}"
            )

        subscription = subscriptions[0]

        source = session.get(
            SourceRecord,
            subscription.source_id,
        )

        if source is None:
            raise RuntimeError("Subscription source was not found")

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

        dispatch_result = fetch_reference_index_candidates(source)

        candidates = dispatch_result.candidates

        summary = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=candidates,
            creation_limit=args.limit,
            dry_run=True,
        )

        matching_ready = [
            candidate
            for candidate in candidates
            if (
                candidate.published_at is not None
                and reference_item_matches(
                    subscription,
                    candidate.to_feed_item(),
                )
            )
        ]

        matching_ready.sort(
            key=lambda candidate: (
                candidate.published_at,
                candidate.provider_item_id,
            ),
            reverse=True,
        )

        planned = matching_ready[: summary.would_create]

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

        print("=" * 72)
        print("REFERENCE SUBSCRIPTION BATCH DRY-RUN")
        print("=" * 72)
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
        print(
            "External documents downloaded:",
            dispatch_result.external_documents_downloaded,
        )
        print("Candidate count:", len(candidates))
        print("Matched ready:", summary.matched)
        print("Date unverified:", summary.date_unverified)
        print(
            "Historical backlog skipped:",
            summary.backlog_skipped,
        )
        print(
            "Existing automatic cutoff:",
            (summary.existing_cutoff.isoformat() if summary.existing_cutoff else "NONE"),
        )
        print("Creation limit:", summary.creation_limit)
        print("Would create:", summary.would_create)
        print("Duplicates skipped:", summary.duplicates)
        print()

        print("PLANNED ITEMS")

        for index, candidate in enumerate(
            planned,
            start=1,
        ):
            print()
            print(f"{index}. {candidate.title}")
            print(
                "   Published:",
                candidate.published_at.isoformat(),
            )
            print(
                "   Provider item:",
                candidate.provider_item_id,
            )
            print("   URL:", candidate.canonical_url)

        print()
        print("DATABASE COUNTS")
        print(
            "Analyst references:",
            before_references,
            "->",
            after_references,
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
        print("Database writes: 0")

        if (
            before_references != after_references
            or before_coverages != after_coverages
            or before_events != after_events
        ):
            raise RuntimeError("Dry-run unexpectedly changed database counts")

    expected_would_create = (
        args.limit if args.expect_would_create is None else args.expect_would_create
    )

    if summary.would_create != expected_would_create:
        raise RuntimeError(
            "Unexpected dry-run planned item count. "
            f"Expected {expected_would_create}, "
            f"found {summary.would_create}."
        )

    if args.expect_duplicates is not None and summary.duplicates != args.expect_duplicates:
        raise RuntimeError(
            "Unexpected dry-run duplicate count. "
            f"Expected {args.expect_duplicates}, "
            f"found {summary.duplicates}."
        )

        print("Result: REFERENCE BATCH DRY-RUN PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
