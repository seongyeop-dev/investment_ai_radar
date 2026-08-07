from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystIngestMode,
    AnalystPublisherType,
    AnalystReferenceRecord,
    AnalystTranslationStatus,
    AnalystUserState,
    ReferenceDiscoveryCandidateRecord,
    ReferenceDiscoveryCandidateReviewRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.services.reference_discovery_candidate_review import (
    ReferenceDiscoveryCandidateReviewConflictError,
    ReferenceDiscoveryCandidateReviewService,
)


def _count(
    api_database,
    model,
) -> int:
    with api_database.session_scope() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _seed(
    api_database,
    *,
    suffix: str,
    existing_reference: bool = False,
) -> dict[str, str]:
    observed_at = datetime(
        2026,
        8,
        3,
        6,
        0,
        tzinfo=UTC,
    )

    with api_database.session_scope() as session:
        source = SourceRecord(
            name=f"Review Source {suffix}",
            source_type="REFERENCE_INDEX",
            source_grade=SourceGrade.A,
            domain=f"{suffix}.review.test",
            official=True,
            enabled=True,
            feed_url=(f"https://{suffix}.review.test/index"),
            provider_type="REFERENCE_INDEX",
            language="en",
            request_interval_seconds=21600,
            timeout_seconds=20,
            max_items=50,
            original_source_name=None,
            created_at=observed_at,
            updated_at=observed_at,
        )
        session.add(source)
        session.flush()

        subscription = ReferenceSubscriptionRecord(
            source_id=source.id,
            subject_type=next(iter(ReferenceSubjectType)),
            display_name=f"Review Subscription {suffix}",
            match_mode=ReferenceMatchMode.ALL_SOURCE,
            match_terms=[],
            enabled=True,
            created_at=observed_at,
            updated_at=observed_at,
        )
        session.add(subscription)
        session.flush()

        provider_item_id = f"review-item-{suffix}"
        canonical_url = f"https://{suffix}.review.test/report"

        existing_id = ""

        if existing_reference:
            reference = AnalystReferenceRecord(
                source_id=source.id,
                subscription_id=subscription.id,
                provider_item_id=provider_item_id,
                ingest_mode=AnalystIngestMode.AUTOMATIC,
                user_state=AnalystUserState.NEW,
                discovered_at=observed_at,
                publisher_name=source.name,
                publisher_type=(AnalystPublisherType.INSTITUTION),
                title=f"Existing report {suffix}",
                analyst_name=f"Analyst {suffix}",
                published_at=observed_at,
                canonical_url=canonical_url,
                access_type=AnalystAccessType.PUBLIC,
                document_type=(AnalystDocumentType.REPORT),
                public_abstract=None,
                source_language="en",
                translated_title_ko=None,
                translated_abstract_ko=None,
                translation_status=(AnalystTranslationStatus.NOT_REQUESTED),
                translation_provider=None,
                translation_error=None,
                translated_at=None,
                source_retrieved_at=observed_at,
                source_fingerprint="a" * 64,
                freshness_status=(AnalystFreshnessStatus.CURRENT),
                is_active=True,
                created_at=observed_at,
                updated_at=observed_at,
            )
            session.add(reference)
            session.flush()
            existing_id = reference.id

        candidate = ReferenceDiscoveryCandidateRecord(
            source_id=source.id,
            subscription_id=subscription.id,
            provider_item_id=provider_item_id,
            publisher_name=source.name,
            title=f"Candidate report {suffix}",
            analyst_name=f"Analyst {suffix}",
            canonical_url=canonical_url,
            published_at=None,
            verification_status=(ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED),
            first_seen_at=observed_at,
            last_seen_at=observed_at,
            seen_count=1,
            public_abstract=("Verified public metadata."),
            publisher_type=(AnalystPublisherType.RESEARCH_HOUSE),
            access_type=(AnalystAccessType.LOGIN_REQUIRED),
            document_type=(AnalystDocumentType.COMMENTARY),
            promoted_reference_id=None,
            reviewed_at=None,
            created_at=observed_at,
            updated_at=observed_at,
        )
        session.add(candidate)
        session.flush()

        return {
            "candidate_id": candidate.id,
            "existing_reference_id": existing_id,
            "published_at": ("2025-02-22T00:00:00+00:00"),
        }


def test_verify_date_then_promote_creates_reference(
    api_client,
    api_database,
) -> None:
    seeded = _seed(
        api_database,
        suffix="create",
    )
    candidate_id = seeded["candidate_id"]
    base = f"/api/v1/analyst-references/discovery-candidates/{candidate_id}"

    verify_response = api_client.post(
        f"{base}/verify-date",
        json={
            "publishedAt": seeded["published_at"],
            "reason": "Official metadata checked.",
        },
    )

    assert verify_response.status_code == 200
    assert verify_response.json()["candidate"]["verificationStatus"] == "DATE_VERIFIED"
    assert verify_response.json()["history"]["action"] == "VERIFY_DATE"
    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 0
    )

    promote_response = api_client.post(
        f"{base}/promote",
        json={
            "confirm": True,
            "reason": "Approved official reference.",
        },
    )

    assert promote_response.status_code == 200

    body = promote_response.json()

    assert body["candidate"]["verificationStatus"] == "PROMOTED"
    assert body["referenceCreated"] is True
    assert body["referenceDuplicate"] is False
    assert body["referenceId"] is not None
    assert body["history"]["action"] == "PROMOTE"

    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 1
    )
    assert (
        _count(
            api_database,
            ReferenceDiscoveryCandidateReviewRecord,
        )
        == 2
    )

    with api_database.session_scope() as session:
        reference = session.scalar(select(AnalystReferenceRecord))
        candidate = session.get(
            ReferenceDiscoveryCandidateRecord,
            candidate_id,
        )

        assert reference is not None
        assert candidate is not None
        assert candidate.promoted_reference_id == reference.id
        assert reference.public_abstract == ("Verified public metadata.")
        assert reference.publisher_type == (AnalystPublisherType.RESEARCH_HOUSE)
        assert reference.access_type == (AnalystAccessType.LOGIN_REQUIRED)
        assert reference.document_type == (AnalystDocumentType.COMMENTARY)


def test_verify_date_rejects_naive_published_at(
    api_client,
    api_database,
) -> None:
    seeded = _seed(
        api_database,
        suffix="naive-timezone",
    )
    candidate_id = seeded["candidate_id"]

    response = api_client.post(
        (f"/api/v1/analyst-references/discovery-candidates/{candidate_id}/verify-date"),
        json={
            "publishedAt": "2025-02-22T00:00:00",
        },
    )

    assert response.status_code == 422
    assert (
        _count(
            api_database,
            ReferenceDiscoveryCandidateReviewRecord,
        )
        == 0
    )

    with api_database.session_scope() as session:
        candidate = session.get(
            ReferenceDiscoveryCandidateRecord,
            candidate_id,
        )

        assert candidate is not None
        assert candidate.published_at is None
        assert candidate.verification_status == (
            ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED
        )


@pytest.mark.parametrize(
    ("published_at", "expected_utc"),
    [
        (
            "2025-02-22T00:00:00Z",
            datetime(2025, 2, 22, tzinfo=UTC),
        ),
        (
            "2025-02-22T09:00:00+09:00",
            datetime(2025, 2, 22, tzinfo=UTC),
        ),
        (
            "2025-02-22T00:30:00+09:00",
            datetime(2025, 2, 21, 15, 30, tzinfo=UTC),
        ),
    ],
    ids=[
        "web-ui-z",
        "korea-offset",
        "offset-date-boundary",
    ],
)
def test_verify_date_normalizes_aware_published_at_to_utc(
    api_client,
    api_database,
    published_at: str,
    expected_utc: datetime,
) -> None:
    seeded = _seed(
        api_database,
        suffix=("aware-timezone-" + expected_utc.strftime("%Y%m%d%H%M")),
    )
    candidate_id = seeded["candidate_id"]

    response = api_client.post(
        (f"/api/v1/analyst-references/discovery-candidates/{candidate_id}/verify-date"),
        json={
            "publishedAt": published_at,
        },
    )

    assert response.status_code == 200

    body = response.json()
    candidate_published_at = datetime.fromisoformat(
        body["candidate"]["publishedAt"].replace("Z", "+00:00")
    )
    history_published_at = datetime.fromisoformat(
        body["history"]["verifiedPublishedAt"].replace("Z", "+00:00")
    )

    assert candidate_published_at == expected_utc
    assert history_published_at == expected_utc
    assert candidate_published_at.utcoffset() == (expected_utc.utcoffset())


def test_promote_duplicate_links_existing_reference(
    api_client,
    api_database,
) -> None:
    seeded = _seed(
        api_database,
        suffix="duplicate",
        existing_reference=True,
    )
    candidate_id = seeded["candidate_id"]
    base = f"/api/v1/analyst-references/discovery-candidates/{candidate_id}"

    assert (
        api_client.post(
            f"{base}/verify-date",
            json={
                "publishedAt": seeded["published_at"],
            },
        ).status_code
        == 200
    )

    response = api_client.post(
        f"{base}/promote",
        json={
            "confirm": True,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["referenceCreated"] is False
    assert body["referenceDuplicate"] is True
    assert body["referenceId"] == seeded["existing_reference_id"]
    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 1
    )

    with api_database.session_scope() as session:
        candidate = session.get(
            ReferenceDiscoveryCandidateRecord,
            candidate_id,
        )

        assert candidate is not None
        assert candidate.promoted_reference_id == seeded["existing_reference_id"]


def test_dismiss_requires_confirmation_and_reason(
    api_client,
    api_database,
) -> None:
    seeded = _seed(
        api_database,
        suffix="dismiss",
    )
    candidate_id = seeded["candidate_id"]
    url = f"/api/v1/analyst-references/discovery-candidates/{candidate_id}/dismiss"

    unconfirmed = api_client.post(
        url,
        json={
            "confirm": False,
            "reason": "Not an eligible document.",
        },
    )

    assert unconfirmed.status_code == 409
    assert (
        _count(
            api_database,
            ReferenceDiscoveryCandidateReviewRecord,
        )
        == 0
    )

    empty_reason = api_client.post(
        url,
        json={
            "confirm": True,
            "reason": "   ",
        },
    )

    assert empty_reason.status_code == 422

    confirmed = api_client.post(
        url,
        json={
            "confirm": True,
            "reason": "Not an eligible document.",
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["candidate"]["verificationStatus"] == "DISMISSED"
    assert confirmed.json()["history"]["action"] == "DISMISS"
    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 0
    )
    assert (
        _count(
            api_database,
            ReferenceDiscoveryCandidateReviewRecord,
        )
        == 1
    )


def test_promote_requires_verified_date(
    api_client,
    api_database,
) -> None:
    seeded = _seed(
        api_database,
        suffix="state",
    )
    candidate_id = seeded["candidate_id"]

    response = api_client.post(
        (f"/api/v1/analyst-references/discovery-candidates/{candidate_id}/promote"),
        json={
            "confirm": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == ("REFERENCE_DISCOVERY_CANDIDATE_STATE_INVALID")
    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 0
    )
    assert (
        _count(
            api_database,
            ReferenceDiscoveryCandidateReviewRecord,
        )
        == 0
    )


def test_review_history_and_final_state_guard(
    api_client,
    api_database,
) -> None:
    seeded = _seed(
        api_database,
        suffix="history",
    )
    candidate_id = seeded["candidate_id"]
    base = f"/api/v1/analyst-references/discovery-candidates/{candidate_id}"

    assert (
        api_client.post(
            f"{base}/verify-date",
            json={
                "publishedAt": seeded["published_at"],
            },
        ).status_code
        == 200
    )

    assert (
        api_client.post(
            f"{base}/dismiss",
            json={
                "confirm": True,
                "reason": "Review completed.",
            },
        ).status_code
        == 200
    )

    history_response = api_client.get(f"{base}/review-history")

    assert history_response.status_code == 200

    history = history_response.json()

    assert history["total"] == 2
    assert [item["action"] for item in history["items"]] == [
        "DISMISS",
        "VERIFY_DATE",
    ]

    retry_response = api_client.post(
        f"{base}/verify-date",
        json={
            "publishedAt": ("2025-02-23T00:00:00+00:00"),
        },
    )

    assert retry_response.status_code == 409
    assert (
        _count(
            api_database,
            ReferenceDiscoveryCandidateReviewRecord,
        )
        == 2
    )


def test_concurrent_review_conflict_uses_structured_409(
    api_client,
    api_database,
    monkeypatch,
) -> None:
    seeded = _seed(
        api_database,
        suffix="concurrent-conflict",
    )

    def raise_concurrent_conflict(
        _service,
        _candidate_id,
        _payload,
        *,
        now=None,
    ) -> None:
        del now
        raise ReferenceDiscoveryCandidateReviewConflictError(reason="STALE_VERIFICATION_STATUS")

    monkeypatch.setattr(
        ReferenceDiscoveryCandidateReviewService,
        "verify_date",
        raise_concurrent_conflict,
    )

    response = api_client.post(
        (
            "/api/v1/analyst-references/"
            "discovery-candidates/"
            f"{seeded['candidate_id']}/verify-date"
        ),
        json={
            "publishedAt": seeded["published_at"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": ("REFERENCE_DISCOVERY_CANDIDATE_CONFLICT"),
        "message": ("Reference discovery candidate was modified by another review operation."),
        "reason": "STALE_VERIFICATION_STATUS",
    }
