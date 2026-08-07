from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import Database
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)


def _source() -> SourceRecord:
    return SourceRecord(
        name="Oaktree Official Insights",
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain="oaktreecapital.com",
        official=True,
        enabled=True,
        feed_url=("https://www.oaktreecapital.com/insights/rss"),
        provider_type="RSS",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=10,
        max_items=50,
        original_source_name=None,
    )


def test_reference_subscription_list_is_empty(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/analyst-references/subscriptions")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }


def test_reference_subscription_list_and_detail(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()

        subscription = ReferenceSubscriptionRecord(
            source_id=source.id,
            subject_type=ReferenceSubjectType.EXPERT,
            display_name="Howard Marks",
            match_mode=ReferenceMatchMode.AUTHOR,
            match_terms=[
                "Howard Marks",
                "Howard S. Marks",
            ],
            enabled=True,
        )

        session.add(subscription)
        session.flush()

        subscription_id = subscription.id

    list_response = api_client.get(
        "/api/v1/analyst-references/subscriptions",
        params={
            "subjectType": "EXPERT",
            "matchMode": "AUTHOR",
            "enabled": "true",
            "query": "Howard",
        },
    )

    assert list_response.status_code == 200

    body = list_response.json()

    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0

    item = body["items"][0]

    assert item["id"] == subscription_id
    assert item["displayName"] == "Howard Marks"
    assert item["subjectType"] == "EXPERT"
    assert item["matchMode"] == "AUTHOR"
    assert item["matchTerms"] == [
        "Howard Marks",
        "Howard S. Marks",
    ]
    assert item["enabled"] is True

    assert item["source"]["name"] == ("Oaktree Official Insights")
    assert item["source"]["sourceGrade"] == "A"
    assert item["source"]["official"] is True
    assert item["source"]["domain"] == ("oaktreecapital.com")
    assert item["source"]["providerType"] == "RSS"

    detail_response = api_client.get(
        f"/api/v1/analyst-references/subscriptions/{subscription_id}"
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == subscription_id


def test_reference_subscription_detail_returns_404(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/api/v1/analyst-references/subscriptions/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == ("Reference subscription was not found.")
