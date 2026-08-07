from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import Database
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)


def _source(
    *,
    official: bool = True,
    enabled: bool = True,
) -> SourceRecord:
    return SourceRecord(
        name="Oaktree Official Insights",
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain="oaktreecapital.com",
        official=official,
        enabled=enabled,
        feed_url=("https://www.oaktreecapital.com/insights/rss"),
        provider_type="RSS",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=10,
        max_items=50,
        original_source_name=None,
    )


def _payload(
    source_id: str,
    *,
    confirm: bool,
) -> dict[str, object]:
    return {
        "sourceId": source_id,
        "subjectType": "EXPERT",
        "displayName": "  Howard   Marks  ",
        "matchMode": "AUTHOR",
        "matchTerms": [
            " Howard Marks ",
            "howard marks",
            "Howard S. Marks",
            "",
        ],
        "confirm": confirm,
    }


def _subscription_count(
    database: Database,
) -> int:
    with database.session_scope() as session:
        count = session.scalar(select(func.count()).select_from(ReferenceSubscriptionRecord))

        return int(count or 0)


def test_subscription_import_preview_does_not_write(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()
        source_id = source.id

    response = api_client.post(
        ("/api/v1/analyst-references/subscriptions/import"),
        json=_payload(
            source_id,
            confirm=False,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["confirmed"] is False
    assert body["wouldCreate"] is True
    assert body["normalizedDisplayName"] == ("Howard Marks")
    assert body["normalizedMatchTerms"] == [
        "Howard Marks",
        "Howard S. Marks",
    ]
    assert body["validationWarnings"] == []
    assert body["duplicate"]["duplicate"] is False

    assert _subscription_count(api_database) == 0


def test_subscription_import_confirm_creates_record(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()
        source_id = source.id

    response = api_client.post(
        ("/api/v1/analyst-references/subscriptions/import"),
        json=_payload(
            source_id,
            confirm=True,
        ),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["confirmed"] is True
    assert body["subscription"]["displayName"] == ("Howard Marks")
    assert body["subscription"]["subjectType"] == ("EXPERT")
    assert body["subscription"]["matchMode"] == ("AUTHOR")
    assert body["subscription"]["enabled"] is True
    assert body["subscription"]["source"]["official"] is True

    assert _subscription_count(api_database) == 1

    list_response = api_client.get("/api/v1/analyst-references/subscriptions")

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_subscription_import_duplicate_is_blocked(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()
        source_id = source.id

    first_response = api_client.post(
        ("/api/v1/analyst-references/subscriptions/import"),
        json=_payload(
            source_id,
            confirm=True,
        ),
    )

    assert first_response.status_code == 201

    duplicate_response = api_client.post(
        ("/api/v1/analyst-references/subscriptions/import"),
        json=_payload(
            source_id,
            confirm=True,
        ),
    )

    assert duplicate_response.status_code == 409

    detail = duplicate_response.json()["detail"]

    assert detail["wouldCreate"] is False
    assert detail["duplicate"]["duplicate"] is True
    assert "DUPLICATE_SUBSCRIPTION" in detail["validationWarnings"]

    assert _subscription_count(api_database) == 1


def test_subscription_import_unofficial_source_is_blocked(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source(
            official=False,
        )
        session.add(source)
        session.flush()
        source_id = source.id

    preview_response = api_client.post(
        ("/api/v1/analyst-references/subscriptions/import"),
        json=_payload(
            source_id,
            confirm=False,
        ),
    )

    assert preview_response.status_code == 200
    assert preview_response.json()["wouldCreate"] is False
    assert "SOURCE_NOT_OFFICIAL" in preview_response.json()["validationWarnings"]

    confirm_response = api_client.post(
        ("/api/v1/analyst-references/subscriptions/import"),
        json=_payload(
            source_id,
            confirm=True,
        ),
    )

    assert confirm_response.status_code == 409
    assert _subscription_count(api_database) == 0
