from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.services.reference_sync import (
    reference_item_matches,
)


class ReferenceDiscoveryState(StrEnum):
    READY = "READY"
    DATE_UNVERIFIED = "DATE_UNVERIFIED"
    NOT_MATCHED = "NOT_MATCHED"


@dataclass(frozen=True, slots=True)
class ReferenceDiscoveryPreview:
    provider_item_id: str
    title: str
    canonical_url: str
    author_name: str | None
    published_at: str | None
    matched: bool
    ingest_ready: bool
    state: ReferenceDiscoveryState


def preview_reference_candidate(
    *,
    subscription: ReferenceSubscriptionRecord,
    candidate: ReferenceIndexCandidate,
) -> ReferenceDiscoveryPreview:
    if candidate.published_at is None:
        return ReferenceDiscoveryPreview(
            provider_item_id=candidate.provider_item_id,
            title=candidate.title,
            canonical_url=candidate.canonical_url,
            author_name=candidate.author_name,
            published_at=None,
            matched=(subscription.enabled and subscription.match_mode.value == "ALL_SOURCE"),
            ingest_ready=False,
            state=ReferenceDiscoveryState.DATE_UNVERIFIED,
        )

    item = candidate.to_feed_item()

    matched = reference_item_matches(
        subscription,
        item,
    )

    return ReferenceDiscoveryPreview(
        provider_item_id=candidate.provider_item_id,
        title=candidate.title,
        canonical_url=candidate.canonical_url,
        author_name=candidate.author_name,
        published_at=(candidate.published_at.isoformat()),
        matched=matched,
        ingest_ready=matched,
        state=(
            ReferenceDiscoveryState.READY if matched else ReferenceDiscoveryState.NOT_MATCHED
        ),
    )


def preview_reference_candidates(
    *,
    subscription: ReferenceSubscriptionRecord,
    candidates: tuple[
        ReferenceIndexCandidate,
        ...,
    ],
) -> tuple[
    ReferenceDiscoveryPreview,
    ...,
]:
    return tuple(
        preview_reference_candidate(
            subscription=subscription,
            candidate=candidate,
        )
        for candidate in candidates
    )
