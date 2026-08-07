from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystPublisherType,
    ReferenceDiscoveryCandidateRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)

VALIDATION_DOMAIN = "berkshirehathaway.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database-path",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_path = Path(args.database_path).expanduser().resolve()
    expected_database_path = (
        Path(__file__).resolve().parents[2]
        / ".local"
        / "recording_session"
        / "recording_session.db"
    ).resolve()
    if database_path != expected_database_path:
        raise RuntimeError(
            "This seed may only write to the recording-session database: "
            + str(expected_database_path)
        )
    args.database_path = database_path
    database_path = args.database_path.resolve()

    if not database_path.exists():
        raise RuntimeError(f"Validation database not found: {database_path}")

    database_url = "sqlite+pysqlite:///" + database_path.as_posix()

    engine = create_engine(database_url)

    observed_at = datetime.now(UTC)

    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        if revision != "20260803_0017":
            raise RuntimeError(f"Unexpected validation revision: {revision}")

        with Session(engine) as session:
            existing_source = session.scalar(
                select(SourceRecord).where(SourceRecord.domain == VALIDATION_DOMAIN)
            )

            if existing_source is not None:
                raise RuntimeError("Recording candidate seed already exists.")

            source = SourceRecord(
                name=("Berkshire Hathaway Shareholder Letters"),
                source_type="REFERENCE_INDEX",
                source_grade=SourceGrade.A,
                domain=VALIDATION_DOMAIN,
                official=True,
                enabled=True,
                feed_url=("https://www.berkshirehathaway.com/letters/letters.html"),
                provider_type="REFERENCE_INDEX",
                language="en",
                request_interval_seconds=21600,
                timeout_seconds=20,
                max_items=50,
                original_source_name=None,
                created_at=observed_at,
                updated_at=observed_at,
            )

            session.add(source)
            session.flush()

            subscription = ReferenceSubscriptionRecord(
                source_id=source.id,
                subject_type=(ReferenceSubjectType.EXPERT),
                display_name=("Warren Buffett"),
                match_mode=(ReferenceMatchMode.ALL_SOURCE),
                match_terms=[],
                enabled=True,
                created_at=observed_at,
                updated_at=observed_at,
            )

            session.add(subscription)
            session.flush()

            candidate = ReferenceDiscoveryCandidateRecord(
                source_id=source.id,
                subscription_id=subscription.id,
                provider_item_id=("2024ltr.pdf"),
                publisher_name=("Berkshire Hathaway"),
                title=("2024 Shareholder Letter"),
                analyst_name=("Warren Buffett"),
                canonical_url=("https://www.berkshirehathaway.com/letters/2024ltr.pdf"),
                published_at=None,
                verification_status=(ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED),
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                seen_count=1,
                public_abstract=(
                    "Official 2024 Berkshire Hathaway shareholder letter candidate "
                    "for manual publication-date review."
                ),
                publisher_type=(AnalystPublisherType.INSTITUTION),
                access_type=(AnalystAccessType.PUBLIC),
                document_type=(AnalystDocumentType.REPORT),
                promoted_reference_id=None,
                reviewed_at=None,
                created_at=observed_at,
                updated_at=observed_at,
            )

            session.add(candidate)
            session.flush()

            result = {
                "databasePath": str(database_path),
                "revision": revision,
                "sourceId": source.id,
                "subscriptionId": subscription.id,
                "candidateId": candidate.id,
                "candidateStatus": (candidate.verification_status.value),
                "sourcesUrl": ("http://127.0.0.1:3011/sources"),
                "apiUrl": ("http://127.0.0.1:8011"),
            }

            session.commit()

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
