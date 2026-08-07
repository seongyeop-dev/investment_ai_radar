from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import SystemClock
from app.models.analyst_references import (
    ReferenceDiscoveryCandidateRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.database import SourceRecord
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ReferenceDiscoveryStagingSummary:
    scanned: int
    inserted: int
    refreshed: int
    skipped_verified_date: int


@dataclass(
    frozen=True,
    slots=True,
)
class ReferenceCandidatePartition:
    date_verified: tuple[
        ReferenceIndexCandidate,
        ...,
    ]
    date_unverified: tuple[
        ReferenceIndexCandidate,
        ...,
    ]


def partition_reference_candidates(
    candidates: Iterable[ReferenceIndexCandidate],
) -> ReferenceCandidatePartition:
    date_verified: list[ReferenceIndexCandidate] = []

    date_unverified: list[ReferenceIndexCandidate] = []

    for candidate in candidates:
        if candidate.published_at is None:
            date_unverified.append(candidate)
        else:
            date_verified.append(candidate)

    return ReferenceCandidatePartition(
        date_verified=tuple(date_verified),
        date_unverified=tuple(date_unverified),
    )


def stage_unverified_reference_candidates(
    session: Session,
    *,
    source: SourceRecord,
    subscription_id: str,
    candidates: Iterable[ReferenceIndexCandidate],
    seen_at: datetime | None = None,
) -> ReferenceDiscoveryStagingSummary:
    source_id = str(source.id or "").strip()
    normalized_subscription_id = subscription_id.strip()

    if not source_id:
        raise ValueError("source.id must not be empty")

    if not normalized_subscription_id:
        raise ValueError("subscription_id must not be empty")

    observed_at = seen_at if seen_at is not None else SystemClock().now()

    candidate_list = list(candidates)

    unverified_candidates = [
        candidate for candidate in candidate_list if candidate.published_at is None
    ]

    provider_item_ids = {
        candidate.provider_item_id.strip()
        for candidate in unverified_candidates
        if candidate.provider_item_id.strip()
    }

    existing_by_provider_item_id: dict[
        str,
        ReferenceDiscoveryCandidateRecord,
    ] = {}

    if provider_item_ids:
        existing_rows = session.scalars(
            select(ReferenceDiscoveryCandidateRecord).where(
                ReferenceDiscoveryCandidateRecord.source_id == source_id,
                ReferenceDiscoveryCandidateRecord.provider_item_id.in_(provider_item_ids),
            )
        ).all()

        existing_by_provider_item_id = {row.provider_item_id: row for row in existing_rows}

    inserted = 0
    refreshed = 0
    skipped_verified_date = 0

    for candidate in candidate_list:
        if candidate.published_at is not None:
            skipped_verified_date += 1
            continue

        provider_item_id = candidate.provider_item_id.strip()

        if not provider_item_id:
            raise ValueError("candidate.provider_item_id must not be empty")

        existing = existing_by_provider_item_id.get(provider_item_id)

        if existing is None:
            record = ReferenceDiscoveryCandidateRecord(
                source_id=source_id,
                subscription_id=(normalized_subscription_id),
                provider_item_id=(provider_item_id),
                publisher_name=source.name,
                title=candidate.title,
                analyst_name=(candidate.author_name),
                canonical_url=(candidate.canonical_url),
                published_at=None,
                verification_status=(ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED),
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                seen_count=1,
                public_abstract=(candidate.public_abstract),
                publisher_type=(candidate.publisher_type),
                access_type=(candidate.access_type),
                document_type=(candidate.document_type),
                created_at=observed_at,
                updated_at=observed_at,
            )

            session.add(record)

            existing_by_provider_item_id[provider_item_id] = record

            inserted += 1
            continue

        existing.publisher_name = source.name
        existing.title = candidate.title
        existing.analyst_name = candidate.author_name
        existing.canonical_url = candidate.canonical_url
        existing.public_abstract = candidate.public_abstract
        existing.publisher_type = candidate.publisher_type
        existing.access_type = candidate.access_type
        existing.document_type = candidate.document_type
        existing.last_seen_at = observed_at
        existing.updated_at = observed_at
        existing.seen_count += 1

        refreshed += 1

    session.flush()

    return ReferenceDiscoveryStagingSummary(
        scanned=len(candidate_list),
        inserted=inserted,
        refreshed=refreshed,
        skipped_verified_date=(skipped_verified_date),
    )
