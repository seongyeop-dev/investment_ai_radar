from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.analyst_references import (
    ReferenceDiscoveryCandidateStatus,
)
from app.repositories.reference_discovery_candidates import (
    ReferenceDiscoveryCandidateReadRow,
    ReferenceDiscoveryCandidateRepository,
)
from app.schemas.reference_discovery_candidates import (
    ReferenceDiscoveryCandidateList,
    ReferenceDiscoveryCandidateRead,
    ReferenceDiscoveryCandidateSourceRead,
    ReferenceDiscoveryCandidateSubscriptionRead,
)


def reference_discovery_candidate_read(
    row: ReferenceDiscoveryCandidateReadRow,
) -> ReferenceDiscoveryCandidateRead:
    candidate = row.candidate
    source = row.source
    subscription = row.subscription

    return ReferenceDiscoveryCandidateRead(
        id=candidate.id,
        source_id=candidate.source_id,
        subscription_id=candidate.subscription_id,
        provider_item_id=candidate.provider_item_id,
        publisher_name=candidate.publisher_name,
        title=candidate.title,
        analyst_name=candidate.analyst_name,
        canonical_url=candidate.canonical_url,
        published_at=candidate.published_at,
        verification_status=(candidate.verification_status),
        first_seen_at=candidate.first_seen_at,
        last_seen_at=candidate.last_seen_at,
        seen_count=candidate.seen_count,
        public_abstract=candidate.public_abstract,
        publisher_type=candidate.publisher_type,
        access_type=candidate.access_type,
        document_type=candidate.document_type,
        promoted_reference_id=(candidate.promoted_reference_id),
        reviewed_at=candidate.reviewed_at,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
        source=ReferenceDiscoveryCandidateSourceRead(
            id=source.id,
            name=source.name,
            domain=source.domain,
            source_grade=source.source_grade,
            official=source.official,
            enabled=source.enabled,
            feed_url=source.feed_url,
        ),
        subscription=(
            ReferenceDiscoveryCandidateSubscriptionRead(
                id=subscription.id,
                display_name=subscription.display_name,
                subject_type=subscription.subject_type,
                match_mode=subscription.match_mode,
                enabled=subscription.enabled,
            )
        ),
    )


class ReferenceDiscoveryCandidateReadService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.repository = ReferenceDiscoveryCandidateRepository(session)

    def get(
        self,
        candidate_id: str,
    ) -> ReferenceDiscoveryCandidateRead | None:
        row = self.repository.get(candidate_id)

        if row is None:
            return None

        return reference_discovery_candidate_read(row)

    def list(
        self,
        *,
        source_id: str | None = None,
        subscription_id: str | None = None,
        verification_status: (ReferenceDiscoveryCandidateStatus | None) = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ReferenceDiscoveryCandidateList:
        rows, total = self.repository.list(
            source_id=source_id,
            subscription_id=subscription_id,
            verification_status=verification_status,
            query=query,
            limit=limit,
            offset=offset,
        )

        return ReferenceDiscoveryCandidateList(
            items=[reference_discovery_candidate_read(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )
