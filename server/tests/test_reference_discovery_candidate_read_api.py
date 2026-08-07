from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from app.models.analyst_references import (
    ReferenceDiscoveryCandidateRecord,
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


def _record_count(
    api_database,
    model,
) -> int:
    with api_database.session_scope() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _seed_candidate(
    api_database,
    *,
    suffix: str = "primary",
) -> dict[str, object]:
    observed_at = datetime(
        2026,
        8,
        3,
        3,
        0,
        tzinfo=UTC,
    )
    source_grade = next(iter(SourceGrade))
    subject_type = next(iter(ReferenceSubjectType))
    match_mode = next(iter(ReferenceMatchMode))

    with api_database.session_scope() as session:
        source = SourceRecord(
            name=f"Candidate Source {suffix}",
            source_type="REFERENCE_INDEX",
            source_grade=source_grade,
            domain=f"{suffix}.example.com",
            official=True,
            enabled=True,
            feed_url=(f"https://{suffix}.example.com/insights"),
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
            subject_type=subject_type,
            display_name=f"Analyst {suffix}",
            match_mode=match_mode,
            match_terms=[
                f"Analyst {suffix}",
            ],
            enabled=True,
            created_at=observed_at,
            updated_at=observed_at,
        )
        session.add(subscription)
        session.flush()

        candidate = ReferenceDiscoveryCandidateRecord(
            source_id=source.id,
            subscription_id=subscription.id,
            provider_item_id=f"provider-item-{suffix}",
            publisher_name=source.name,
            title=f"Undated memo {suffix}",
            analyst_name=f"Analyst {suffix}",
            canonical_url=(f"https://{suffix}.example.com/insights/{suffix}"),
            published_at=None,
            verification_status=(ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED),
            first_seen_at=observed_at,
            last_seen_at=observed_at,
            seen_count=1,
            created_at=observed_at,
            updated_at=observed_at,
        )
        session.add(candidate)
        session.flush()

        return {
            "candidate_id": candidate.id,
            "source_id": source.id,
            "subscription_id": subscription.id,
            "source_name": source.name,
            "source_domain": source.domain,
            "source_grade": source_grade.value,
            "subscription_name": (subscription.display_name),
            "subject_type": subject_type.value,
            "match_mode": match_mode.value,
            "title": candidate.title,
            "canonical_url": candidate.canonical_url,
            "observed_at": observed_at,
        }


def _candidate_snapshot(
    api_database,
    candidate_id: str,
) -> tuple[object, ...]:
    with api_database.session_scope() as session:
        candidate = session.get(
            ReferenceDiscoveryCandidateRecord,
            candidate_id,
        )

        assert candidate is not None

        return (
            candidate.published_at,
            candidate.verification_status,
            candidate.first_seen_at,
            candidate.last_seen_at,
            candidate.seen_count,
            candidate.created_at,
            candidate.updated_at,
        )


def test_candidate_list_is_empty(
    api_client,
) -> None:
    response = api_client.get("/api/v1/analyst-references/discovery-candidates")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }


def test_candidate_list_and_detail_are_read_only(
    api_client,
    api_database,
) -> None:
    seeded = _seed_candidate(api_database)

    candidate_id = str(seeded["candidate_id"])

    counts_before = {
        "candidates": _record_count(
            api_database,
            ReferenceDiscoveryCandidateRecord,
        ),
        "sources": _record_count(
            api_database,
            SourceRecord,
        ),
        "subscriptions": _record_count(
            api_database,
            ReferenceSubscriptionRecord,
        ),
    }
    snapshot_before = _candidate_snapshot(
        api_database,
        candidate_id,
    )

    list_response = api_client.get("/api/v1/analyst-references/discovery-candidates")

    assert list_response.status_code == 200

    list_body = list_response.json()

    assert list_body["total"] == 1
    assert list_body["limit"] == 50
    assert list_body["offset"] == 0
    assert len(list_body["items"]) == 1

    item = list_body["items"][0]

    assert item["id"] == candidate_id
    assert item["sourceId"] == seeded["source_id"]
    assert item["subscriptionId"] == seeded["subscription_id"]
    assert item["title"] == seeded["title"]
    assert item["canonicalUrl"] == seeded["canonical_url"]
    assert item["publishedAt"] is None
    assert item["verificationStatus"] == "DATE_UNVERIFIED"
    assert item["seenCount"] == 1
    assert item["publicAbstract"] is None
    assert item["publisherType"] == "INSTITUTION"
    assert item["accessType"] == "PUBLIC"
    assert item["documentType"] == "OTHER"
    assert item["promotedReferenceId"] is None
    assert item["reviewedAt"] is None

    assert item["source"]["name"] == seeded["source_name"]
    assert item["source"]["domain"] == seeded["source_domain"]
    assert item["source"]["sourceGrade"] == seeded["source_grade"]
    assert item["source"]["official"] is True
    assert item["source"]["enabled"] is True

    assert item["subscription"]["displayName"] == seeded["subscription_name"]
    assert item["subscription"]["subjectType"] == seeded["subject_type"]
    assert item["subscription"]["matchMode"] == seeded["match_mode"]
    assert item["subscription"]["enabled"] is True

    detail_response = api_client.get(
        f"/api/v1/analyst-references/discovery-candidates/{candidate_id}"
    )

    assert detail_response.status_code == 200
    assert detail_response.json() == item

    forbidden_fields = {
        "fullText",
        "articleBody",
        "pdfBinary",
        "documentBinary",
        "shortSummary",
        "recommendation",
        "generatedTargetPrice",
        "decisionReview",
        "portfolioImpact",
    }

    assert forbidden_fields.isdisjoint(item)

    counts_after = {
        "candidates": _record_count(
            api_database,
            ReferenceDiscoveryCandidateRecord,
        ),
        "sources": _record_count(
            api_database,
            SourceRecord,
        ),
        "subscriptions": _record_count(
            api_database,
            ReferenceSubscriptionRecord,
        ),
    }
    snapshot_after = _candidate_snapshot(
        api_database,
        candidate_id,
    )

    assert counts_after == counts_before
    assert snapshot_after == snapshot_before


def test_candidate_list_filters_and_pagination(
    api_client,
    api_database,
) -> None:
    seeded = _seed_candidate(api_database)

    base_path = "/api/v1/analyst-references/discovery-candidates"

    filter_urls = [
        (f"{base_path}?sourceId={seeded['source_id']}"),
        (f"{base_path}?subscriptionId={seeded['subscription_id']}"),
        (f"{base_path}?verificationStatus=DATE_UNVERIFIED"),
        (f"{base_path}?query=Undated%20memo"),
        (f"{base_path}?query={seeded['source_domain']}"),
        (f"{base_path}?query=Analyst%20primary"),
    ]

    for url in filter_urls:
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert len(response.json()["items"]) == 1

    missing_source_response = api_client.get(f"{base_path}?sourceId={uuid4()}")

    assert missing_source_response.status_code == 200
    assert missing_source_response.json()["total"] == 0

    missing_query_response = api_client.get(f"{base_path}?query=not-present")

    assert missing_query_response.status_code == 200
    assert missing_query_response.json()["total"] == 0

    pagination_response = api_client.get(f"{base_path}?limit=1&offset=1")

    assert pagination_response.status_code == 200
    assert pagination_response.json() == {
        "items": [],
        "total": 1,
        "limit": 1,
        "offset": 1,
    }


def test_unknown_candidate_returns_structured_404(
    api_client,
) -> None:
    candidate_id = "00000000-0000-0000-0000-000000000000"

    response = api_client.get(f"/api/v1/analyst-references/discovery-candidates/{candidate_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": ("REFERENCE_DISCOVERY_CANDIDATE_NOT_FOUND"),
        "message": ("Reference discovery candidate was not found."),
    }


def test_candidate_query_validation(
    api_client,
) -> None:
    base_path = "/api/v1/analyst-references/discovery-candidates"

    invalid_limit_response = api_client.get(f"{base_path}?limit=201")
    invalid_offset_response = api_client.get(f"{base_path}?offset=-1")
    invalid_status_response = api_client.get(f"{base_path}?verificationStatus=INVALID")

    assert invalid_limit_response.status_code == 422
    assert invalid_offset_response.status_code == 422
    assert invalid_status_response.status_code == 422
