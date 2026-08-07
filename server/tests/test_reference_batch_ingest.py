from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.database import Database
from app.models.analyst_references import (
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
)
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.disclosures import (
    InformationEventRecord,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.services.reference_batch_ingest import (
    ingest_reference_candidates,
)
from app.services.reference_freshness_refresh import refresh_automatic_reference_freshness

SOURCE_ID = "55555555-5555-4555-8555-555555555551"


def _source() -> SourceRecord:
    return SourceRecord(
        id=SOURCE_ID,
        name="Oaktree Batch Fixture",
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain="oaktree-batch.test",
        official=True,
        enabled=True,
        feed_url=("https://oaktree-batch.test/insights"),
        provider_type="REFERENCE_INDEX",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=10,
        max_items=50,
        original_source_name=None,
    )


def _subscription() -> ReferenceSubscriptionRecord:
    return ReferenceSubscriptionRecord(
        source_id=SOURCE_ID,
        subject_type=ReferenceSubjectType.EXPERT,
        display_name="Howard Marks",
        match_mode=ReferenceMatchMode.AUTHOR,
        match_terms=[
            "Howard Marks",
            "Howard S. Marks",
        ],
        enabled=True,
    )


def _candidate(
    day: int,
) -> ReferenceIndexCandidate:
    return ReferenceIndexCandidate(
        provider_item_id=(f"oaktree:memo-{day}"),
        title=f"Memo {day}",
        canonical_url=(f"https://oaktree-batch.test/insights/memo/memo-{day}"),
        published_at=datetime(
            2026,
            7,
            day,
            8,
            0,
            tzinfo=UTC,
        ),
        author_name="Howard Marks",
    )


def _candidates() -> tuple[
    ReferenceIndexCandidate,
    ...,
]:
    values = [_candidate(day) for day in range(1, 6)]

    values.append(
        ReferenceIndexCandidate(
            provider_item_id=("berkshire:unverified"),
            title="Unverified Letter",
            canonical_url=("https://oaktree-batch.test/letters/unverified.pdf"),
            published_at=None,
            author_name="Howard Marks",
        )
    )

    return tuple(values)


def _count(
    database: Database,
    model: type,
) -> int:
    with database.session_scope() as session:
        value = session.scalar(select(func.count()).select_from(model))

        return int(value or 0)


def test_batch_dry_run_limits_to_latest_three_without_writes(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        subscription = _subscription()

        session.add_all(
            [
                source,
                subscription,
            ]
        )
        session.flush()

        summary = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=_candidates(),
            creation_limit=3,
            dry_run=True,
        )

        assert summary.examined == 6
        assert summary.matched == 5
        assert summary.date_unverified == 1
        assert summary.backlog_skipped == 0
        assert summary.processed == 3
        assert summary.created == 0
        assert summary.duplicates == 0
        assert summary.would_create == 3
        assert summary.existing_cutoff is None
        assert summary.dry_run is True

    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 0
    )


def test_batch_bootstrap_then_ignores_historical_backlog(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        subscription = _subscription()

        session.add_all(
            [
                source,
                subscription,
            ]
        )
        session.flush()

        first = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=_candidates(),
            creation_limit=3,
            dry_run=False,
            now=datetime(
                2026,
                7,
                30,
                9,
                0,
                tzinfo=UTC,
            ),
        )

        assert first.created == 3
        assert first.duplicates == 0
        assert first.backlog_skipped == 0

        titles = set(session.scalars(select(AnalystReferenceRecord.title)))

        assert titles == {
            "Memo 3",
            "Memo 4",
            "Memo 5",
        }

        second = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=_candidates(),
            creation_limit=3,
            dry_run=False,
        )

        assert second.created == 0
        assert second.duplicates == 1
        assert second.backlog_skipped == 4
        assert second.existing_cutoff == datetime(
            2026,
            7,
            5,
            8,
            0,
            tzinfo=UTC,
        )

        titles_after_rerun = set(session.scalars(select(AnalystReferenceRecord.title)))

        assert titles_after_rerun == {
            "Memo 3",
            "Memo 4",
            "Memo 5",
        }

        new_candidate = _candidate(6)

        third = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=(
                *_candidates(),
                new_candidate,
            ),
            creation_limit=3,
            dry_run=False,
        )

        assert third.created == 1
        assert third.duplicates == 1
        assert third.backlog_skipped == 4

        final_titles = set(session.scalars(select(AnalystReferenceRecord.title)))

        assert final_titles == {
            "Memo 3",
            "Memo 4",
            "Memo 5",
            "Memo 6",
        }

        fourth = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=(
                *_candidates(),
                new_candidate,
            ),
            creation_limit=3,
            dry_run=False,
        )

        assert fourth.created == 0
        assert fourth.duplicates == 1
        assert fourth.backlog_skipped == 5

        reference_count = session.scalar(
            select(func.count()).select_from(AnalystReferenceRecord)
        )
        coverage_count = session.scalar(
            select(func.count()).select_from(AnalystReferenceCoverageRecord)
        )
        information_event_count = session.scalar(
            select(func.count()).select_from(InformationEventRecord)
        )

        assert int(reference_count or 0) == 4
        assert int(coverage_count or 0) == 0
        assert int(information_event_count or 0) == 0


def test_batch_persists_calculated_freshness_statuses(
    api_database: Database,
) -> None:
    from dataclasses import replace
    from datetime import timedelta

    now = datetime(
        2026,
        7,
        31,
        8,
        0,
        tzinfo=UTC,
    )

    base_candidates = _candidates()

    definitions = (
        (
            base_candidates[0],
            "Freshness Current",
            10,
            "CURRENT",
        ),
        (
            base_candidates[1],
            "Freshness Aging",
            60,
            "AGING",
        ),
        (
            base_candidates[2],
            "Freshness Stale",
            120,
            "STALE",
        ),
    )

    candidates = tuple(
        replace(
            candidate,
            provider_item_id=("freshness:" + expected_status.lower()),
            title=title,
            canonical_url=("https://oaktree-batch.test/freshness/" + expected_status.lower()),
            published_at=(now - timedelta(days=age_days)),
        )
        for (
            candidate,
            title,
            age_days,
            expected_status,
        ) in definitions
    )

    expected_statuses = {
        title: expected_status
        for (
            _candidate,
            title,
            _age_days,
            expected_status,
        ) in definitions
    }

    with api_database.session_scope() as session:
        source = _source()
        subscription = _subscription()

        session.add_all(
            [
                source,
                subscription,
            ]
        )
        session.flush()

        summary = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=candidates,
            creation_limit=3,
            dry_run=False,
            now=now,
        )

        assert summary.examined == 3
        assert summary.matched == 3
        assert summary.processed == 3
        assert summary.created == 3
        assert summary.duplicates == 0
        assert summary.would_create == 0

        records = list(
            session.scalars(
                select(AnalystReferenceRecord).where(
                    AnalystReferenceRecord.title.in_(expected_statuses)
                )
            )
        )

        assert len(records) == 3

        stored_statuses = {
            record.title: getattr(
                record.freshness_status,
                "value",
                record.freshness_status,
            )
            for record in records
        }

        assert stored_statuses == expected_statuses

        coverage_count = session.scalar(
            select(func.count()).select_from(AnalystReferenceCoverageRecord)
        )

        information_event_count = session.scalar(
            select(func.count()).select_from(InformationEventRecord)
        )

        assert int(coverage_count or 0) == 0
        assert int(information_event_count or 0) == 0


def test_batch_refreshes_existing_reference_freshness(
    api_database: Database,
) -> None:
    from dataclasses import replace
    from datetime import timedelta

    initial_now = datetime(
        2026,
        7,
        1,
        8,
        0,
        tzinfo=UTC,
    )

    refresh_now = datetime(
        2026,
        7,
        31,
        8,
        0,
        tzinfo=UTC,
    )

    base_candidates = _candidates()

    definitions = (
        (
            base_candidates[0],
            "Refresh Current To Aging",
            10,
        ),
        (
            base_candidates[1],
            "Refresh Aging To Stale",
            70,
        ),
        (
            base_candidates[2],
            "Refresh Stale Unchanged",
            120,
        ),
    )

    candidates = tuple(
        replace(
            candidate,
            provider_item_id=("refresh:" + str(index)),
            title=title,
            canonical_url=("https://oaktree-batch.test/refresh/" + str(index)),
            published_at=(initial_now - timedelta(days=age_days)),
        )
        for index, (
            candidate,
            title,
            age_days,
        ) in enumerate(
            definitions,
            start=1,
        )
    )

    expected_statuses = {
        "Refresh Current To Aging": "AGING",
        "Refresh Aging To Stale": "STALE",
        "Refresh Stale Unchanged": "STALE",
    }

    with api_database.session_scope() as session:
        source = _source()
        subscription = _subscription()

        session.add_all(
            [
                source,
                subscription,
            ]
        )
        session.flush()

        ingest_summary = ingest_reference_candidates(
            session,
            subscription=subscription,
            source=source,
            candidates=candidates,
            creation_limit=3,
            dry_run=False,
            now=initial_now,
        )

        assert ingest_summary.created == 3

        refresh_summary = refresh_automatic_reference_freshness(
            session,
            subscription_id=str(subscription.id),
            now=refresh_now,
        )

        assert refresh_summary.examined == 3
        assert refresh_summary.updated == 2
        assert refresh_summary.current == 0
        assert refresh_summary.aging == 1
        assert refresh_summary.stale == 2
        assert refresh_summary.unknown == 0

        records = list(
            session.scalars(
                select(AnalystReferenceRecord).where(
                    AnalystReferenceRecord.title.in_(expected_statuses)
                )
            )
        )

        stored_statuses = {
            record.title: getattr(
                record.freshness_status,
                "value",
                record.freshness_status,
            )
            for record in records
        }

        assert stored_statuses == expected_statuses

        repeated_summary = refresh_automatic_reference_freshness(
            session,
            subscription_id=str(subscription.id),
            now=refresh_now,
        )

        assert repeated_summary.examined == 3
        assert repeated_summary.updated == 0
        assert repeated_summary.current == 0
        assert repeated_summary.aging == 1
        assert repeated_summary.stale == 2
        assert repeated_summary.unknown == 0

        coverage_count = session.scalar(
            select(func.count()).select_from(AnalystReferenceCoverageRecord)
        )

        information_event_count = session.scalar(
            select(func.count()).select_from(InformationEventRecord)
        )

        assert int(coverage_count or 0) == 0
        assert int(information_event_count or 0) == 0


def test_batch_rejects_invalid_creation_limit(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        subscription = _subscription()

        session.add_all(
            [
                source,
                subscription,
            ]
        )
        session.flush()

        try:
            ingest_reference_candidates(
                session,
                subscription=subscription,
                source=source,
                candidates=_candidates(),
                creation_limit=0,
            )
        except ValueError as exc:
            assert "creation_limit must be at least 1" in str(exc)
        else:
            raise AssertionError("ValueError was not raised")
