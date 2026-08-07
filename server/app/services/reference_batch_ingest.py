from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analyst_references import (
    AnalystIngestMode,
    AnalystReferenceRecord,
)
from app.models.database import SourceRecord
from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.services.reference_sync import (
    AutomaticReferenceIngestService,
    ReferenceIngestResult,
    ReferenceTitleTranslationProvider,
    reference_item_matches,
)


@dataclass(frozen=True, slots=True)
class ReferenceBatchIngestSummary:
    examined: int
    matched: int
    date_unverified: int
    backlog_skipped: int
    processed: int
    created: int
    duplicates: int
    would_create: int
    creation_limit: int
    dry_run: bool
    existing_cutoff: datetime | None
    results: tuple[
        ReferenceIngestResult,
        ...,
    ]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _existing_automatic_cutoff(
    session: Session,
    *,
    subscription_id: str,
) -> datetime | None:
    value = session.scalar(
        select(func.max(AnalystReferenceRecord.published_at)).where(
            AnalystReferenceRecord.subscription_id == subscription_id,
            AnalystReferenceRecord.ingest_mode == AnalystIngestMode.AUTOMATIC,
        )
    )

    if value is None:
        return None

    return _utc(value)


def ingest_reference_candidates(
    session: Session,
    *,
    subscription: ReferenceSubscriptionRecord,
    source: SourceRecord,
    candidates: tuple[
        ReferenceIndexCandidate,
        ...,
    ],
    creation_limit: int = 3,
    dry_run: bool = True,
    translation_provider: (ReferenceTitleTranslationProvider | None) = None,
    now: datetime | None = None,
) -> ReferenceBatchIngestSummary:
    if creation_limit < 1:
        raise ValueError("creation_limit must be at least 1")

    date_unverified = sum(candidate.published_at is None for candidate in candidates)

    existing_cutoff = _existing_automatic_cutoff(
        session,
        subscription_id=str(subscription.id),
    )

    eligible_candidates: list[ReferenceIndexCandidate] = []

    backlog_skipped = 0

    for candidate in candidates:
        if candidate.published_at is None:
            continue

        published_at = _utc(candidate.published_at)

        if existing_cutoff is not None and published_at < existing_cutoff:
            backlog_skipped += 1
            continue

        eligible_candidates.append(candidate)

    eligible_candidates.sort(
        key=lambda candidate: (
            _utc(candidate.published_at),
            candidate.provider_item_id,
        ),
        reverse=True,
    )

    matched_candidates: list[ReferenceIndexCandidate] = []

    for candidate in eligible_candidates:
        item = candidate.to_feed_item()

        if reference_item_matches(
            subscription,
            item,
        ):
            matched_candidates.append(candidate)

    ingest_service = AutomaticReferenceIngestService(
        session,
        translation_provider=translation_provider,
    )

    results: list[ReferenceIngestResult] = []

    created = 0
    duplicates = 0
    would_create = 0
    accepted = 0

    for candidate in matched_candidates:
        if accepted >= creation_limit:
            break

        result = ingest_service.ingest(
            subscription=subscription,
            source=source,
            item=candidate.to_feed_item(),
            dry_run=dry_run,
            now=now,
        )

        results.append(result)

        if result.created:
            created += 1
            accepted += 1
        elif result.duplicate:
            duplicates += 1
        elif result.reason == "DRY_RUN":
            would_create += 1
            accepted += 1

    return ReferenceBatchIngestSummary(
        examined=len(candidates),
        matched=len(matched_candidates),
        date_unverified=date_unverified,
        backlog_skipped=backlog_skipped,
        processed=len(results),
        created=created,
        duplicates=duplicates,
        would_create=would_create,
        creation_limit=creation_limit,
        dry_run=dry_run,
        existing_cutoff=existing_cutoff,
        results=tuple(results),
    )
