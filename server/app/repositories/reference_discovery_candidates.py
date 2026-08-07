from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models.analyst_references import (
    ReferenceDiscoveryCandidateRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.database import SourceRecord
from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)

MAX_REFERENCE_DISCOVERY_CANDIDATE_LIMIT = 200


@dataclass(
    frozen=True,
    slots=True,
)
class ReferenceDiscoveryCandidateReadRow:
    candidate: ReferenceDiscoveryCandidateRecord
    source: SourceRecord
    subscription: ReferenceSubscriptionRecord


class ReferenceDiscoveryCandidateRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    @staticmethod
    def _base_statement():
        return (
            select(
                ReferenceDiscoveryCandidateRecord,
                SourceRecord,
                ReferenceSubscriptionRecord,
            )
            .join(
                SourceRecord,
                SourceRecord.id == ReferenceDiscoveryCandidateRecord.source_id,
            )
            .join(
                ReferenceSubscriptionRecord,
                ReferenceSubscriptionRecord.id
                == (ReferenceDiscoveryCandidateRecord.subscription_id),
            )
        )

    @staticmethod
    def _count_statement():
        return (
            select(func.count())
            .select_from(ReferenceDiscoveryCandidateRecord)
            .join(
                SourceRecord,
                SourceRecord.id == ReferenceDiscoveryCandidateRecord.source_id,
            )
            .join(
                ReferenceSubscriptionRecord,
                ReferenceSubscriptionRecord.id
                == (ReferenceDiscoveryCandidateRecord.subscription_id),
            )
        )

    @staticmethod
    def _read_row(
        row: tuple[
            ReferenceDiscoveryCandidateRecord,
            SourceRecord,
            ReferenceSubscriptionRecord,
        ],
    ) -> ReferenceDiscoveryCandidateReadRow:
        candidate, source, subscription = row

        return ReferenceDiscoveryCandidateReadRow(
            candidate=candidate,
            source=source,
            subscription=subscription,
        )

    def get(
        self,
        candidate_id: str,
    ) -> ReferenceDiscoveryCandidateReadRow | None:
        row = self.session.execute(
            self._base_statement().where(ReferenceDiscoveryCandidateRecord.id == candidate_id)
        ).one_or_none()

        if row is None:
            return None

        return self._read_row(
            (
                row[0],
                row[1],
                row[2],
            )
        )

    def compare_and_swap_status(
        self,
        candidate_id: str,
        *,
        expected_status: ReferenceDiscoveryCandidateStatus,
        new_status: ReferenceDiscoveryCandidateStatus,
        values: dict[str, object],
    ) -> bool:
        result = self.session.execute(
            update(ReferenceDiscoveryCandidateRecord)
            .where(
                ReferenceDiscoveryCandidateRecord.id == candidate_id,
                ReferenceDiscoveryCandidateRecord.verification_status == expected_status,
            )
            .values(
                verification_status=new_status,
                **values,
            )
            .execution_options(
                synchronize_session=False,
            )
        )

        return result.rowcount == 1

    def list(
        self,
        *,
        source_id: str | None = None,
        subscription_id: str | None = None,
        verification_status: (ReferenceDiscoveryCandidateStatus | None) = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[
        list[ReferenceDiscoveryCandidateReadRow],
        int,
    ]:
        filters = []

        if source_id is not None:
            filters.append(ReferenceDiscoveryCandidateRecord.source_id == source_id)

        if subscription_id is not None:
            filters.append(ReferenceDiscoveryCandidateRecord.subscription_id == subscription_id)

        if verification_status is not None:
            filters.append(
                ReferenceDiscoveryCandidateRecord.verification_status == verification_status
            )

        if query and query.strip():
            term = query.strip()

            filters.append(
                or_(
                    ReferenceDiscoveryCandidateRecord.title.contains(
                        term,
                        autoescape=True,
                    ),
                    ReferenceDiscoveryCandidateRecord.publisher_name.contains(
                        term,
                        autoescape=True,
                    ),
                    ReferenceDiscoveryCandidateRecord.analyst_name.contains(
                        term,
                        autoescape=True,
                    ),
                    SourceRecord.name.contains(
                        term,
                        autoescape=True,
                    ),
                    SourceRecord.domain.contains(
                        term,
                        autoescape=True,
                    ),
                    ReferenceSubscriptionRecord.display_name.contains(
                        term,
                        autoescape=True,
                    ),
                )
            )

        normalized_limit = min(
            max(limit, 1),
            MAX_REFERENCE_DISCOVERY_CANDIDATE_LIMIT,
        )
        normalized_offset = max(
            offset,
            0,
        )

        total = self.session.scalar(self._count_statement().where(*filters))

        rows = self.session.execute(
            self._base_statement()
            .where(*filters)
            .order_by(
                ReferenceDiscoveryCandidateRecord.last_seen_at.desc(),
                ReferenceDiscoveryCandidateRecord.created_at.desc(),
                ReferenceDiscoveryCandidateRecord.id.asc(),
            )
            .limit(normalized_limit)
            .offset(normalized_offset)
        ).all()

        return (
            [
                self._read_row(
                    (
                        row[0],
                        row[1],
                        row[2],
                    )
                )
                for row in rows
            ],
            int(total or 0),
        )
