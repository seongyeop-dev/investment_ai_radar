from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
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
    ReferenceSubscriptionRecord,
)
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.services.reference_discovery_staging import (
    stage_unverified_reference_candidates,
)


@pytest.fixture
def database_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(
        engine,
        tables=[
            SourceRecord.__table__,
            ReferenceSubscriptionRecord.__table__,
            ReferenceDiscoveryCandidateRecord.__table__,
        ],
    )

    with Session(engine) as session:
        yield session


def _source() -> SourceRecord:
    return SourceRecord(
        id="source-1",
        name=("Berkshire Hathaway Warren Buffett Letters"),
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain="berkshirehathaway.com",
        official=True,
        enabled=True,
        feed_url=("https://www.berkshirehathaway.com/letters/letters.html"),
        provider_type="REFERENCE_INDEX",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=20,
        max_items=50,
        original_source_name=None,
    )


def _candidate(
    *,
    title: str = "2024 Shareholder Letter",
    published_at: datetime | None = None,
    public_abstract: str | None = ("Official public candidate metadata."),
    publisher_type: AnalystPublisherType = (AnalystPublisherType.RESEARCH_HOUSE),
    access_type: AnalystAccessType = (AnalystAccessType.LOGIN_REQUIRED),
    document_type: AnalystDocumentType = (AnalystDocumentType.REPORT),
) -> ReferenceIndexCandidate:
    return ReferenceIndexCandidate(
        provider_item_id="2024ltr.pdf",
        title=title,
        canonical_url=("https://www.berkshirehathaway.com/letters/2024ltr.pdf"),
        published_at=published_at,
        author_name="Warren Buffett",
        public_abstract=public_abstract,
        publisher_type=publisher_type,
        access_type=access_type,
        document_type=document_type,
    )


def test_unverified_candidate_is_inserted(
    database_session: Session,
) -> None:
    observed_at = datetime(
        2026,
        8,
        3,
        1,
        0,
        tzinfo=UTC,
    )

    summary = stage_unverified_reference_candidates(
        database_session,
        source=_source(),
        subscription_id="subscription-1",
        candidates=[_candidate()],
        seen_at=observed_at,
    )

    record = database_session.scalar(select(ReferenceDiscoveryCandidateRecord))

    assert summary.scanned == 1
    assert summary.inserted == 1
    assert summary.refreshed == 0
    assert summary.skipped_verified_date == 0

    assert record is not None
    assert record.published_at is None
    assert record.verification_status == ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED
    assert record.seen_count == 1
    assert record.first_seen_at == observed_at
    assert record.last_seen_at == observed_at
    assert record.public_abstract == ("Official public candidate metadata.")
    assert record.publisher_type == (AnalystPublisherType.RESEARCH_HOUSE)
    assert record.access_type == (AnalystAccessType.LOGIN_REQUIRED)
    assert record.document_type == (AnalystDocumentType.REPORT)


def test_repeat_discovery_refreshes_existing_row(
    database_session: Session,
) -> None:
    first_seen = datetime(
        2026,
        8,
        3,
        1,
        0,
        tzinfo=UTC,
    )

    second_seen = first_seen + timedelta(hours=6)

    stage_unverified_reference_candidates(
        database_session,
        source=_source(),
        subscription_id="subscription-1",
        candidates=[_candidate()],
        seen_at=first_seen,
    )

    summary = stage_unverified_reference_candidates(
        database_session,
        source=_source(),
        subscription_id="subscription-1",
        candidates=[
            _candidate(
                title=("2024 Annual Shareholder Letter"),
                public_abstract=("Updated public candidate metadata."),
                publisher_type=(AnalystPublisherType.FINANCIAL_MEDIA),
                access_type=(AnalystAccessType.PAYWALLED),
                document_type=(AnalystDocumentType.COMMENTARY),
            )
        ],
        seen_at=second_seen,
    )

    count = database_session.scalar(
        select(func.count()).select_from(ReferenceDiscoveryCandidateRecord)
    )

    record = database_session.scalar(select(ReferenceDiscoveryCandidateRecord))

    assert count == 1
    assert summary.inserted == 0
    assert summary.refreshed == 1

    assert record is not None
    assert record.seen_count == 2
    assert record.first_seen_at == first_seen
    assert record.last_seen_at == second_seen
    assert record.title == ("2024 Annual Shareholder Letter")
    assert record.public_abstract == ("Updated public candidate metadata.")
    assert record.publisher_type == (AnalystPublisherType.FINANCIAL_MEDIA)
    assert record.access_type == (AnalystAccessType.PAYWALLED)
    assert record.document_type == (AnalystDocumentType.COMMENTARY)


def test_verified_date_candidate_is_not_staged(
    database_session: Session,
) -> None:
    summary = stage_unverified_reference_candidates(
        database_session,
        source=_source(),
        subscription_id="subscription-1",
        candidates=[
            _candidate(
                published_at=datetime(
                    2025,
                    2,
                    22,
                    tzinfo=UTC,
                )
            )
        ],
    )

    count = database_session.scalar(
        select(func.count()).select_from(ReferenceDiscoveryCandidateRecord)
    )

    assert summary.scanned == 1
    assert summary.inserted == 0
    assert summary.refreshed == 0
    assert summary.skipped_verified_date == 1
    assert count == 0


def test_model_declares_source_provider_uniqueness() -> None:
    constraint_names = {
        constraint.name
        for constraint in (ReferenceDiscoveryCandidateRecord.__table__.constraints)
    }

    assert "uq_reference_discovery_candidate_source_provider_item" in constraint_names


def test_migration_revision_is_0016() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / ("20260803_0016_reference_discovery_candidates.py")
    )

    source = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "20260803_0016"' in source
    assert 'down_revision: str | None = "20260802_0015"' in source
    assert '"reference_discovery_candidates"' in source
