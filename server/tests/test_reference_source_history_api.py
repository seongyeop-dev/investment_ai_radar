from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import Database
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_source_history import (
    ReferenceSourceChangeRecord,
)

BASE_PATH = "/api/v1/analyst-references/subscriptions/source-management"


def _seed_history(
    database: Database,
) -> str:
    source_id = str(uuid4())

    with database.session_scope() as session:
        source = SourceRecord(
            id=source_id,
            name="History API Source",
            source_type="EXPERT_REFERENCE",
            source_grade=SourceGrade.A,
            domain="history.example.com",
            official=True,
            enabled=True,
            feed_url=("https://history.example.com/feed"),
            provider_type="REFERENCE_INDEX",
            language="en",
            request_interval_seconds=21600,
            timeout_seconds=20,
            max_items=50,
            original_source_name=None,
        )

        session.add(source)
        session.flush()

        session.add_all(
            [
                ReferenceSourceChangeRecord(
                    id=str(uuid4()),
                    source_id=source_id,
                    operation="CREATE",
                    changed_fields=[
                        "name",
                        "domain",
                    ],
                    before_values=None,
                    after_values={
                        "name": "History API Source",
                        "domain": ("history.example.com"),
                    },
                    backup_path=("backups/reference_source_management/create.db"),
                    created_at=datetime(
                        2026,
                        8,
                        2,
                        1,
                        0,
                        tzinfo=UTC,
                    ),
                ),
                ReferenceSourceChangeRecord(
                    id=str(uuid4()),
                    source_id=source_id,
                    operation="UPDATE",
                    changed_fields=[
                        "timeout_seconds",
                    ],
                    before_values={
                        "timeout_seconds": 20,
                    },
                    after_values={
                        "timeout_seconds": 25,
                    },
                    backup_path=("backups/reference_source_management/update.db"),
                    created_at=datetime(
                        2026,
                        8,
                        2,
                        2,
                        0,
                        tzinfo=UTC,
                    ),
                ),
            ]
        )

    return source_id


def test_source_history_lists_latest_first(
    api_client: TestClient,
    api_database: Database,
) -> None:
    source_id = _seed_history(api_database)

    response = api_client.get(
        f"{BASE_PATH}/{source_id}/history",
        params={
            "limit": 50,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 2
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 2

    latest = body["items"][0]
    oldest = body["items"][1]

    assert latest["sourceId"] == source_id
    assert latest["operation"] == "UPDATE"
    assert latest["changedFields"] == [
        "timeout_seconds",
    ]
    assert latest["beforeValues"] == {
        "timeout_seconds": 20,
    }
    assert latest["afterValues"] == {
        "timeout_seconds": 25,
    }
    assert latest["backupPath"].endswith("update.db")
    assert "createdAt" in latest

    assert oldest["operation"] == "CREATE"
    assert oldest["beforeValues"] is None


def test_source_history_supports_pagination(
    api_client: TestClient,
    api_database: Database,
) -> None:
    source_id = _seed_history(api_database)

    response = api_client.get(
        f"{BASE_PATH}/{source_id}/history",
        params={
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["operation"] == "CREATE"


def test_source_history_returns_404_for_unknown_source(
    api_client: TestClient,
) -> None:
    source_id = str(uuid4())

    response = api_client.get(f"{BASE_PATH}/{source_id}/history")

    assert response.status_code == 404
