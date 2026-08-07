from __future__ import annotations

from datetime import UTC, datetime

from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.services.reference_discovery import (
    ReferenceDiscoveryState,
    preview_reference_candidate,
)


def _subscription(
    *,
    match_mode: ReferenceMatchMode,
    match_terms: list[str],
) -> ReferenceSubscriptionRecord:
    return ReferenceSubscriptionRecord(
        source_id=("44444444-4444-4444-8444-444444444441"),
        subject_type=ReferenceSubjectType.EXPERT,
        display_name="Fixture",
        match_mode=match_mode,
        match_terms=match_terms,
        enabled=True,
    )


def test_ready_candidate_matches_author() -> None:
    subscription = _subscription(
        match_mode=ReferenceMatchMode.AUTHOR,
        match_terms=[
            "Howard Marks",
        ],
    )

    candidate = ReferenceIndexCandidate(
        provider_item_id="oaktree:memo",
        title="A Public Memo",
        canonical_url=("https://example.test/insights/memo/example"),
        published_at=datetime(
            2026,
            7,
            30,
            tzinfo=UTC,
        ),
        author_name="Howard Marks",
    )

    preview = preview_reference_candidate(
        subscription=subscription,
        candidate=candidate,
    )

    assert preview.matched is True
    assert preview.ingest_ready is True
    assert preview.state is ReferenceDiscoveryState.READY


def test_unverified_date_is_not_ingest_ready() -> None:
    subscription = _subscription(
        match_mode=ReferenceMatchMode.ALL_SOURCE,
        match_terms=[],
    )

    candidate = ReferenceIndexCandidate(
        provider_item_id="2025ltr.pdf",
        title=("Berkshire Hathaway 2025 Shareholder Letter"),
        canonical_url=("https://example.test/letters/2025ltr.pdf"),
        published_at=None,
        author_name="Greg Abel",
    )

    preview = preview_reference_candidate(
        subscription=subscription,
        candidate=candidate,
    )

    assert preview.matched is True
    assert preview.ingest_ready is False
    assert preview.published_at is None
    assert preview.state is ReferenceDiscoveryState.DATE_UNVERIFIED


def test_unmatched_ready_candidate_is_rejected() -> None:
    subscription = _subscription(
        match_mode=ReferenceMatchMode.KEYWORD,
        match_terms=[
            "semiconductor",
        ],
    )

    candidate = ReferenceIndexCandidate(
        provider_item_id="oaktree:credit",
        title="Private Credit",
        canonical_url=("https://example.test/insights/memo/private-credit"),
        published_at=datetime(
            2026,
            4,
            9,
            tzinfo=UTC,
        ),
        author_name="Howard Marks",
    )

    preview = preview_reference_candidate(
        subscription=subscription,
        candidate=candidate,
    )

    assert preview.matched is False
    assert preview.ingest_ready is False
    assert preview.state is ReferenceDiscoveryState.NOT_MATCHED
