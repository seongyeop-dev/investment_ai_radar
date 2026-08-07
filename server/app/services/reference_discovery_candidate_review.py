from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import require_aware_utc
from app.models.analyst_references import (
    AnalystReferenceRecord,
    ReferenceDiscoveryCandidateReviewAction,
    ReferenceDiscoveryCandidateReviewRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.repositories.reference_discovery_candidates import (
    ReferenceDiscoveryCandidateReadRow,
    ReferenceDiscoveryCandidateRepository,
)
from app.schemas.reference_discovery_candidate_review import (
    ReferenceDiscoveryCandidateDismissRequest,
    ReferenceDiscoveryCandidatePromoteRequest,
    ReferenceDiscoveryCandidateReviewHistoryList,
    ReferenceDiscoveryCandidateReviewHistoryRead,
    ReferenceDiscoveryCandidateReviewResult,
    ReferenceDiscoveryCandidateVerifyDateRequest,
)
from app.services.reference_discovery_candidates import (
    reference_discovery_candidate_read,
)
from app.services.reference_sync import (
    AutomaticReferenceIngestService,
)

MAX_REFERENCE_DISCOVERY_CANDIDATE_HISTORY_LIMIT = 200


class ReferenceDiscoveryCandidateReviewError(RuntimeError):
    code = "REFERENCE_DISCOVERY_CANDIDATE_REVIEW_ERROR"
    message = "Reference discovery candidate review failed."

    def __init__(
        self,
        *,
        reason: str | None = None,
    ) -> None:
        super().__init__(self.message)
        self.reason = reason


class ReferenceDiscoveryCandidateReviewNotFoundError(ReferenceDiscoveryCandidateReviewError):
    code = "REFERENCE_DISCOVERY_CANDIDATE_NOT_FOUND"
    message = "Reference discovery candidate was not found."


class ReferenceDiscoveryCandidateReviewStateError(ReferenceDiscoveryCandidateReviewError):
    code = "REFERENCE_DISCOVERY_CANDIDATE_STATE_INVALID"
    message = "Reference discovery candidate state does not allow this operation."


class ReferenceDiscoveryCandidateReviewConflictError(ReferenceDiscoveryCandidateReviewError):
    code = "REFERENCE_DISCOVERY_CANDIDATE_CONFLICT"
    message = "Reference discovery candidate was modified by another review operation."


class ReferenceDiscoveryCandidateReviewConfirmationError(
    ReferenceDiscoveryCandidateReviewError
):
    code = "REFERENCE_DISCOVERY_CANDIDATE_CONFIRMATION_REQUIRED"
    message = "Explicit confirmation is required."


class ReferenceDiscoveryCandidateReviewBlockedError(ReferenceDiscoveryCandidateReviewError):
    code = "REFERENCE_DISCOVERY_CANDIDATE_PROMOTION_BLOCKED"
    message = "Reference discovery candidate promotion was blocked."


def _history_read(
    record: ReferenceDiscoveryCandidateReviewRecord,
) -> ReferenceDiscoveryCandidateReviewHistoryRead:
    return ReferenceDiscoveryCandidateReviewHistoryRead(
        id=record.id,
        candidate_id=record.candidate_id,
        action=record.action,
        previous_status=record.previous_status,
        new_status=record.new_status,
        verified_published_at=(record.verified_published_at),
        promoted_reference_id=(record.promoted_reference_id),
        reason=record.reason,
        created_at=record.created_at,
    )


class ReferenceDiscoveryCandidateReviewService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session
        self.repository = ReferenceDiscoveryCandidateRepository(session)

    def _row(
        self,
        candidate_id: str,
    ) -> ReferenceDiscoveryCandidateReadRow:
        row = self.repository.get(candidate_id)

        if row is None:
            raise (ReferenceDiscoveryCandidateReviewNotFoundError())

        return row

    @staticmethod
    def _ensure_not_final(
        row: ReferenceDiscoveryCandidateReadRow,
    ) -> None:
        status = row.candidate.verification_status

        if status in {
            ReferenceDiscoveryCandidateStatus.PROMOTED,
            ReferenceDiscoveryCandidateStatus.DISMISSED,
        }:
            raise ReferenceDiscoveryCandidateReviewStateError(reason=status.value)

    def _result(
        self,
        *,
        row: ReferenceDiscoveryCandidateReadRow,
        history: (ReferenceDiscoveryCandidateReviewRecord),
        reference_id: str | None,
        reference_created: bool,
        reference_duplicate: bool,
    ) -> ReferenceDiscoveryCandidateReviewResult:
        return ReferenceDiscoveryCandidateReviewResult(
            candidate=(reference_discovery_candidate_read(row)),
            history=_history_read(history),
            reference_id=reference_id,
            reference_created=reference_created,
            reference_duplicate=reference_duplicate,
        )

    def _compare_and_swap(
        self,
        *,
        row: ReferenceDiscoveryCandidateReadRow,
        expected_status: (ReferenceDiscoveryCandidateStatus),
        new_status: ReferenceDiscoveryCandidateStatus,
        reviewed_at: datetime,
        values: dict[str, object] | None = None,
    ) -> None:
        candidate = row.candidate
        transition_values = {
            "reviewed_at": reviewed_at,
            "updated_at": reviewed_at,
            **(values or {}),
        }

        acquired = self.repository.compare_and_swap_status(
            candidate.id,
            expected_status=expected_status,
            new_status=new_status,
            values=transition_values,
        )

        if not acquired:
            raise (
                ReferenceDiscoveryCandidateReviewConflictError(
                    reason="STALE_VERIFICATION_STATUS"
                )
            )

        self.session.expire(candidate)
        self.session.refresh(candidate)

    def verify_date(
        self,
        candidate_id: str,
        payload: (ReferenceDiscoveryCandidateVerifyDateRequest),
        *,
        now: datetime | None = None,
    ) -> ReferenceDiscoveryCandidateReviewResult:
        row = self._row(candidate_id)
        self._ensure_not_final(row)

        candidate = row.candidate

        if candidate.verification_status is not (
            ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED
        ):
            raise ReferenceDiscoveryCandidateReviewStateError(
                reason=(candidate.verification_status.value)
            )

        reviewed_at = require_aware_utc(now or datetime.now(UTC))
        published_at = require_aware_utc(payload.published_at)
        previous_status = ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED
        new_status = ReferenceDiscoveryCandidateStatus.DATE_VERIFIED

        self._compare_and_swap(
            row=row,
            expected_status=previous_status,
            new_status=new_status,
            reviewed_at=reviewed_at,
            values={
                "published_at": published_at,
                "promoted_reference_id": None,
            },
        )

        history = ReferenceDiscoveryCandidateReviewRecord(
            candidate_id=candidate.id,
            action=(ReferenceDiscoveryCandidateReviewAction.VERIFY_DATE),
            previous_status=previous_status,
            new_status=new_status,
            verified_published_at=published_at,
            promoted_reference_id=None,
            reason=payload.reason,
            created_at=reviewed_at,
        )

        self.session.add(history)
        self.session.flush()

        return self._result(
            row=row,
            history=history,
            reference_id=None,
            reference_created=False,
            reference_duplicate=False,
        )

    def promote(
        self,
        candidate_id: str,
        payload: (ReferenceDiscoveryCandidatePromoteRequest),
        *,
        now: datetime | None = None,
    ) -> ReferenceDiscoveryCandidateReviewResult:
        if not payload.confirm:
            raise (ReferenceDiscoveryCandidateReviewConfirmationError())

        row = self._row(candidate_id)
        self._ensure_not_final(row)

        candidate = row.candidate

        if (
            candidate.verification_status
            is not (ReferenceDiscoveryCandidateStatus.DATE_VERIFIED)
            or candidate.published_at is None
        ):
            raise ReferenceDiscoveryCandidateReviewStateError(
                reason=(candidate.verification_status.value)
            )

        reviewed_at = require_aware_utc(now or datetime.now(UTC))

        previous_status = ReferenceDiscoveryCandidateStatus.DATE_VERIFIED
        new_status = ReferenceDiscoveryCandidateStatus.PROMOTED

        index_candidate = ReferenceIndexCandidate(
            provider_item_id=(candidate.provider_item_id),
            title=candidate.title,
            canonical_url=(candidate.canonical_url),
            published_at=(candidate.published_at),
            author_name=(candidate.analyst_name),
            public_abstract=(candidate.public_abstract),
            publisher_type=(candidate.publisher_type),
            access_type=(candidate.access_type),
            document_type=(candidate.document_type),
        )

        self._compare_and_swap(
            row=row,
            expected_status=previous_status,
            new_status=new_status,
            reviewed_at=reviewed_at,
            values={
                "promoted_reference_id": None,
            },
        )

        ingest_result = AutomaticReferenceIngestService(self.session).ingest(
            subscription=row.subscription,
            source=row.source,
            item=index_candidate.to_feed_item(),
            dry_run=False,
            now=reviewed_at,
        )

        if ingest_result.reference_id is None or not (
            ingest_result.created or ingest_result.duplicate
        ):
            raise (ReferenceDiscoveryCandidateReviewBlockedError(reason=ingest_result.reason))

        reference = self.session.get(
            AnalystReferenceRecord,
            ingest_result.reference_id,
        )

        if reference is None:
            raise (
                ReferenceDiscoveryCandidateReviewBlockedError(
                    reason="REFERENCE_NOT_FOUND_AFTER_INGEST"
                )
            )

        candidate.promoted_reference_id = reference.id

        history = ReferenceDiscoveryCandidateReviewRecord(
            candidate_id=candidate.id,
            action=(ReferenceDiscoveryCandidateReviewAction.PROMOTE),
            previous_status=previous_status,
            new_status=new_status,
            verified_published_at=(candidate.published_at),
            promoted_reference_id=(reference.id),
            reason=payload.reason,
            created_at=reviewed_at,
        )

        self.session.add(history)
        self.session.flush()

        return self._result(
            row=row,
            history=history,
            reference_id=reference.id,
            reference_created=(ingest_result.created),
            reference_duplicate=(ingest_result.duplicate),
        )

    def dismiss(
        self,
        candidate_id: str,
        payload: (ReferenceDiscoveryCandidateDismissRequest),
        *,
        now: datetime | None = None,
    ) -> ReferenceDiscoveryCandidateReviewResult:
        if not payload.confirm:
            raise (ReferenceDiscoveryCandidateReviewConfirmationError())

        row = self._row(candidate_id)
        self._ensure_not_final(row)

        candidate = row.candidate
        reviewed_at = require_aware_utc(now or datetime.now(UTC))
        previous_status = candidate.verification_status
        new_status = ReferenceDiscoveryCandidateStatus.DISMISSED

        self._compare_and_swap(
            row=row,
            expected_status=previous_status,
            new_status=new_status,
            reviewed_at=reviewed_at,
            values={
                "promoted_reference_id": None,
            },
        )

        history = ReferenceDiscoveryCandidateReviewRecord(
            candidate_id=candidate.id,
            action=(ReferenceDiscoveryCandidateReviewAction.DISMISS),
            previous_status=previous_status,
            new_status=new_status,
            verified_published_at=(candidate.published_at),
            promoted_reference_id=None,
            reason=payload.reason,
            created_at=reviewed_at,
        )

        self.session.add(history)
        self.session.flush()

        return self._result(
            row=row,
            history=history,
            reference_id=None,
            reference_created=False,
            reference_duplicate=False,
        )

    def history(
        self,
        candidate_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> ReferenceDiscoveryCandidateReviewHistoryList:
        self._row(candidate_id)

        normalized_limit = min(
            max(limit, 1),
            MAX_REFERENCE_DISCOVERY_CANDIDATE_HISTORY_LIMIT,
        )
        normalized_offset = max(
            offset,
            0,
        )

        total = self.session.scalar(
            select(func.count())
            .select_from(ReferenceDiscoveryCandidateReviewRecord)
            .where(ReferenceDiscoveryCandidateReviewRecord.candidate_id == candidate_id)
        )

        records = self.session.scalars(
            select(ReferenceDiscoveryCandidateReviewRecord)
            .where(ReferenceDiscoveryCandidateReviewRecord.candidate_id == candidate_id)
            .order_by(
                ReferenceDiscoveryCandidateReviewRecord.created_at.desc(),
                ReferenceDiscoveryCandidateReviewRecord.id.asc(),
            )
            .limit(normalized_limit)
            .offset(normalized_offset)
        ).all()

        return ReferenceDiscoveryCandidateReviewHistoryList(
            items=[_history_read(record) for record in records],
            total=int(total or 0),
            limit=limit,
            offset=offset,
        )
