from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import Database
from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystIngestMode,
    AnalystPublisherType,
    AnalystReferenceRecord,
    AnalystUserState,
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


def _source() -> SourceRecord:
    return SourceRecord(
        name="Management Test Source",
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain="management-test.example",
        official=True,
        enabled=True,
        feed_url=("https://management-test.example/feed"),
        provider_type="REFERENCE_INDEX",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=10,
        max_items=50,
        original_source_name=None,
    )


def _automatic_reference(
    *,
    source_id: str,
    subscription_id: str,
    suffix: str,
) -> AnalystReferenceRecord:
    now = datetime(
        2026,
        8,
        1,
        tzinfo=UTC,
    )

    return AnalystReferenceRecord(
        source_id=source_id,
        subscription_id=subscription_id,
        provider_item_id=f"management-{suffix}",
        ingest_mode=AnalystIngestMode.AUTOMATIC,
        user_state=AnalystUserState.NEW,
        discovered_at=now,
        publisher_name="Management Test Source",
        publisher_type=(AnalystPublisherType.INSTITUTION),
        title=f"Management reference {suffix}",
        analyst_name="Howard Marks",
        published_at=now,
        canonical_url=(f"https://management-test.example/reference/{suffix}"),
        access_type=AnalystAccessType.PUBLIC,
        document_type=(AnalystDocumentType.COMMENTARY),
        source_retrieved_at=now,
        source_fingerprint=suffix * 64,
        freshness_status=(AnalystFreshnessStatus.CURRENT),
        is_active=True,
    )


def test_subscription_management_update_and_count(
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
            ],
            enabled=True,
        )

        session.add(subscription)
        session.flush()

        session.add_all(
            [
                _automatic_reference(
                    source_id=source.id,
                    subscription_id=subscription.id,
                    suffix="a",
                ),
                _automatic_reference(
                    source_id=source.id,
                    subscription_id=subscription.id,
                    suffix="b",
                ),
            ]
        )

        subscription_id = subscription.id

    detail = api_client.get(f"/api/v1/analyst-references/subscriptions/{subscription_id}")

    assert detail.status_code == 200
    assert detail.json()["automaticReferenceCount"] == 2

    response = api_client.patch(
        (f"/api/v1/analyst-references/subscriptions/{subscription_id}"),
        json={
            "displayName": ("  Howard   Marks Updated  "),
            "matchMode": "KEYWORD",
            "matchTerms": [
                "private credit",
                "Private Credit",
                "  AI  ",
            ],
            "enabled": False,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["displayName"] == "Howard Marks Updated"
    assert body["matchMode"] == "KEYWORD"
    assert body["matchTerms"] == [
        "private credit",
        "AI",
    ]
    assert body["enabled"] is False
    assert body["automaticReferenceCount"] == 2

    enabled_response = api_client.patch(
        (f"/api/v1/analyst-references/subscriptions/{subscription_id}"),
        json={
            "enabled": True,
        },
    )

    assert enabled_response.status_code == 200
    assert enabled_response.json()["enabled"] is True

    with api_database.session_scope() as session:
        stored = session.get(
            ReferenceSubscriptionRecord,
            subscription_id,
        )

        assert stored is not None
        assert stored.display_name == "Howard Marks Updated"
        assert stored.match_mode is (ReferenceMatchMode.KEYWORD)
        assert stored.match_terms == [
            "private credit",
            "AI",
        ]
        assert stored.enabled is True


def test_subscription_management_rejects_empty_update(
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
            match_terms=["Howard Marks"],
            enabled=True,
        )

        session.add(subscription)
        session.flush()

        subscription_id = subscription.id

    response = api_client.patch(
        (f"/api/v1/analyst-references/subscriptions/{subscription_id}"),
        json={},
    )

    assert response.status_code == 422
    assert "At least one update field" in response.text


def test_subscription_management_requires_terms(
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
            match_terms=["Howard Marks"],
            enabled=True,
        )

        session.add(subscription)
        session.flush()

        subscription_id = subscription.id

    response = api_client.patch(
        (f"/api/v1/analyst-references/subscriptions/{subscription_id}"),
        json={
            "matchMode": "KEYWORD",
            "matchTerms": [],
        },
    )

    assert response.status_code == 422
    assert "require at least one match term" in response.text


def test_subscription_management_returns_404(
    api_client: TestClient,
) -> None:
    response = api_client.patch(
        ("/api/v1/analyst-references/subscriptions/00000000-0000-0000-0000-000000000000"),
        json={
            "enabled": False,
        },
    )

    assert response.status_code == 404
