from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.database import Database
from app.models.analyst_references import (
    AnalystReferenceRecord,
    ReferenceDiscoveryCandidateRecord,
    ReferenceDiscoveryCandidateReviewAction,
    ReferenceDiscoveryCandidateReviewRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.database import SourceGrade, SourceRecord
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.repositories.reference_discovery_candidates import (
    ReferenceDiscoveryCandidateRepository,
)
from app.schemas.reference_discovery_candidate_review import (
    ReferenceDiscoveryCandidateDismissRequest,
    ReferenceDiscoveryCandidatePromoteRequest,
    ReferenceDiscoveryCandidateVerifyDateRequest,
)
from app.services.reference_discovery_candidate_review import (
    ReferenceDiscoveryCandidateReviewConflictError,
    ReferenceDiscoveryCandidateReviewService,
)

OBSERVED_AT = datetime(2026, 8, 4, tzinfo=UTC)
PUBLISHED_AT = datetime(2025, 2, 22, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    status: ReferenceDiscoveryCandidateStatus
    promoted_reference_id: str | None
    history_actions: tuple[
        ReferenceDiscoveryCandidateReviewAction,
        ...,
    ]
    history_reference_ids: tuple[str | None, ...]
    reference_ids: tuple[str, ...]


class ForcedHistoryFailure(RuntimeError):
    pass


@contextmanager
def _database(
    tmp_path: Path,
) -> Iterator[Database]:
    database_path = tmp_path / "candidate-concurrency.sqlite3"
    database = Database(f"sqlite+pysqlite:///{database_path.as_posix()}")
    database.create_schema()

    try:
        yield database
    finally:
        database.engine.dispose()


def _seed_candidate(
    database: Database,
    *,
    status: ReferenceDiscoveryCandidateStatus,
) -> str:
    with database.session_scope() as session:
        source = SourceRecord(
            name="Concurrency Source",
            source_type="REFERENCE_INDEX",
            source_grade=SourceGrade.A,
            domain="concurrency.test",
            official=True,
            enabled=True,
            feed_url=("https://concurrency.test/index"),
            provider_type="REFERENCE_INDEX",
            language="en",
            request_interval_seconds=21600,
            timeout_seconds=20,
            max_items=50,
            original_source_name=None,
            created_at=OBSERVED_AT,
            updated_at=OBSERVED_AT,
        )
        session.add(source)
        session.flush()

        subscription = ReferenceSubscriptionRecord(
            source_id=source.id,
            subject_type=next(iter(ReferenceSubjectType)),
            display_name="Concurrency Subscription",
            match_mode=ReferenceMatchMode.ALL_SOURCE,
            match_terms=[],
            enabled=True,
            created_at=OBSERVED_AT,
            updated_at=OBSERVED_AT,
        )
        session.add(subscription)
        session.flush()

        candidate = ReferenceDiscoveryCandidateRecord(
            source_id=source.id,
            subscription_id=subscription.id,
            provider_item_id="concurrency-item",
            publisher_name=source.name,
            title="Concurrency candidate",
            analyst_name="Concurrency Analyst",
            canonical_url=("https://concurrency.test/report"),
            published_at=(
                PUBLISHED_AT
                if status is ReferenceDiscoveryCandidateStatus.DATE_VERIFIED
                else None
            ),
            verification_status=status,
            first_seen_at=OBSERVED_AT,
            last_seen_at=OBSERVED_AT,
            seen_count=1,
            public_abstract="Public metadata.",
            promoted_reference_id=None,
            reviewed_at=None,
            created_at=OBSERVED_AT,
            updated_at=OBSERVED_AT,
        )
        session.add(candidate)
        session.flush()

        return candidate.id


def _prime_stale_candidate(
    session: Session,
    candidate_id: str,
    expected_status: (ReferenceDiscoveryCandidateStatus),
) -> ReferenceDiscoveryCandidateRecord:
    row = ReferenceDiscoveryCandidateRepository(session).get(candidate_id)

    assert row is not None
    assert row.candidate.verification_status is expected_status

    return row.candidate


def _verify(
    session: Session,
    candidate_id: str,
) -> None:
    ReferenceDiscoveryCandidateReviewService(session).verify_date(
        candidate_id,
        ReferenceDiscoveryCandidateVerifyDateRequest(
            published_at=PUBLISHED_AT,
            reason="Concurrency verification.",
        ),
        now=OBSERVED_AT,
    )


def _promote(
    session: Session,
    candidate_id: str,
) -> None:
    ReferenceDiscoveryCandidateReviewService(session).promote(
        candidate_id,
        ReferenceDiscoveryCandidatePromoteRequest(
            confirm=True,
            reason="Concurrency promotion.",
        ),
        now=OBSERVED_AT,
    )


def _dismiss(
    session: Session,
    candidate_id: str,
) -> None:
    ReferenceDiscoveryCandidateReviewService(session).dismiss(
        candidate_id,
        ReferenceDiscoveryCandidateDismissRequest(
            confirm=True,
            reason="Concurrency dismissal.",
        ),
        now=OBSERVED_AT,
    )


def _snapshot(
    database: Database,
    candidate_id: str,
) -> ReviewSnapshot:
    with database.session_scope() as session:
        candidate = session.get(
            ReferenceDiscoveryCandidateRecord,
            candidate_id,
        )
        assert candidate is not None

        histories = tuple(
            session.scalars(
                select(ReferenceDiscoveryCandidateReviewRecord).order_by(
                    ReferenceDiscoveryCandidateReviewRecord.created_at.asc(),
                    ReferenceDiscoveryCandidateReviewRecord.id.asc(),
                )
            )
        )
        references = tuple(
            session.scalars(
                select(AnalystReferenceRecord).order_by(AnalystReferenceRecord.id.asc())
            )
        )

        return ReviewSnapshot(
            status=candidate.verification_status,
            promoted_reference_id=(candidate.promoted_reference_id),
            history_actions=tuple(history.action for history in histories),
            history_reference_ids=tuple(history.promoted_reference_id for history in histories),
            reference_ids=tuple(reference.id for reference in references),
        )


def _sessions(
    database: Database,
) -> tuple[Session, Session]:
    return (
        database.session_factory(),
        database.session_factory(),
    )


def test_verify_verify_allows_exactly_one_winner(
    tmp_path: Path,
) -> None:
    with _database(tmp_path) as database:
        candidate_id = _seed_candidate(
            database,
            status=(ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED),
        )
        first, second = _sessions(database)

        try:
            stale_candidates = tuple(
                _prime_stale_candidate(
                    session,
                    candidate_id,
                    ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED,
                )
                for session in (first, second)
            )
            assert len(stale_candidates) == 2

            _verify(first, candidate_id)
            first.commit()

            with pytest.raises(ReferenceDiscoveryCandidateReviewConflictError):
                _verify(second, candidate_id)
            second.rollback()
        finally:
            first.close()
            second.close()

        snapshot = _snapshot(database, candidate_id)

        assert snapshot.status is (ReferenceDiscoveryCandidateStatus.DATE_VERIFIED)
        assert snapshot.history_actions == (
            ReferenceDiscoveryCandidateReviewAction.VERIFY_DATE,
        )
        assert snapshot.reference_ids == ()
        assert snapshot.promoted_reference_id is None


def test_promote_promote_allows_exactly_one_winner(
    tmp_path: Path,
) -> None:
    with _database(tmp_path) as database:
        candidate_id = _seed_candidate(
            database,
            status=(ReferenceDiscoveryCandidateStatus.DATE_VERIFIED),
        )
        first, second = _sessions(database)

        try:
            stale_candidates = tuple(
                _prime_stale_candidate(
                    session,
                    candidate_id,
                    ReferenceDiscoveryCandidateStatus.DATE_VERIFIED,
                )
                for session in (first, second)
            )
            assert len(stale_candidates) == 2

            _promote(first, candidate_id)
            first.commit()

            with pytest.raises(ReferenceDiscoveryCandidateReviewConflictError):
                _promote(second, candidate_id)
            second.rollback()
        finally:
            first.close()
            second.close()

        snapshot = _snapshot(database, candidate_id)

        assert snapshot.status is (ReferenceDiscoveryCandidateStatus.PROMOTED)
        assert snapshot.history_actions == (ReferenceDiscoveryCandidateReviewAction.PROMOTE,)
        assert len(snapshot.reference_ids) == 1
        assert snapshot.promoted_reference_id == (snapshot.reference_ids[0])
        assert snapshot.history_reference_ids == (snapshot.reference_ids[0],)


@pytest.mark.parametrize(
    "winner",
    ["promote", "dismiss"],
)
def test_promote_dismiss_allows_exactly_one_winner(
    tmp_path: Path,
    winner: str,
) -> None:
    with _database(tmp_path) as database:
        candidate_id = _seed_candidate(
            database,
            status=(ReferenceDiscoveryCandidateStatus.DATE_VERIFIED),
        )
        first, second = _sessions(database)

        try:
            stale_candidates = tuple(
                _prime_stale_candidate(
                    session,
                    candidate_id,
                    ReferenceDiscoveryCandidateStatus.DATE_VERIFIED,
                )
                for session in (first, second)
            )
            assert len(stale_candidates) == 2

            winner_action = _promote if winner == "promote" else _dismiss
            loser_action = _dismiss if winner == "promote" else _promote

            winner_action(first, candidate_id)
            first.commit()

            with pytest.raises(ReferenceDiscoveryCandidateReviewConflictError):
                loser_action(second, candidate_id)
            second.rollback()
        finally:
            first.close()
            second.close()

        snapshot = _snapshot(database, candidate_id)

        if winner == "promote":
            assert snapshot.status is (ReferenceDiscoveryCandidateStatus.PROMOTED)
            assert snapshot.history_actions == (
                ReferenceDiscoveryCandidateReviewAction.PROMOTE,
            )
            assert len(snapshot.reference_ids) == 1
            assert snapshot.promoted_reference_id == (snapshot.reference_ids[0])
        else:
            assert snapshot.status is (ReferenceDiscoveryCandidateStatus.DISMISSED)
            assert snapshot.history_actions == (
                ReferenceDiscoveryCandidateReviewAction.DISMISS,
            )
            assert snapshot.reference_ids == ()
            assert snapshot.promoted_reference_id is None


@pytest.mark.parametrize(
    "winner",
    ["verify", "dismiss"],
)
def test_verify_dismiss_allows_exactly_one_winner(
    tmp_path: Path,
    winner: str,
) -> None:
    with _database(tmp_path) as database:
        candidate_id = _seed_candidate(
            database,
            status=(ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED),
        )
        first, second = _sessions(database)

        try:
            stale_candidates = tuple(
                _prime_stale_candidate(
                    session,
                    candidate_id,
                    ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED,
                )
                for session in (first, second)
            )
            assert len(stale_candidates) == 2

            winner_action = _verify if winner == "verify" else _dismiss
            loser_action = _dismiss if winner == "verify" else _verify

            winner_action(first, candidate_id)
            first.commit()

            with pytest.raises(ReferenceDiscoveryCandidateReviewConflictError):
                loser_action(second, candidate_id)
            second.rollback()
        finally:
            first.close()
            second.close()

        snapshot = _snapshot(database, candidate_id)
        expected_status = (
            ReferenceDiscoveryCandidateStatus.DATE_VERIFIED
            if winner == "verify"
            else ReferenceDiscoveryCandidateStatus.DISMISSED
        )
        expected_action = (
            ReferenceDiscoveryCandidateReviewAction.VERIFY_DATE
            if winner == "verify"
            else ReferenceDiscoveryCandidateReviewAction.DISMISS
        )

        assert snapshot.status is expected_status
        assert snapshot.history_actions == (expected_action,)
        assert snapshot.reference_ids == ()
        assert snapshot.promoted_reference_id is None


def test_promotion_history_failure_rolls_back_all_writes(
    tmp_path: Path,
) -> None:
    with _database(tmp_path) as database:
        candidate_id = _seed_candidate(
            database,
            status=(ReferenceDiscoveryCandidateStatus.DATE_VERIFIED),
        )
        session = database.session_factory()

        def fail_history_flush(
            failing_session: Session,
            _flush_context: object,
            _instances: object,
        ) -> None:
            if any(
                isinstance(
                    record,
                    ReferenceDiscoveryCandidateReviewRecord,
                )
                for record in failing_session.new
            ):
                raise ForcedHistoryFailure

        event.listen(
            session,
            "before_flush",
            fail_history_flush,
        )

        try:
            with (
                pytest.raises(ForcedHistoryFailure),
                session.begin(),
            ):
                _promote(session, candidate_id)
        finally:
            event.remove(
                session,
                "before_flush",
                fail_history_flush,
            )
            session.close()

        snapshot = _snapshot(database, candidate_id)

        assert snapshot.status is (ReferenceDiscoveryCandidateStatus.DATE_VERIFIED)
        assert snapshot.history_actions == ()
        assert snapshot.reference_ids == ()
        assert snapshot.promoted_reference_id is None
