from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import Database
from app.models.database import SourceRecord
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)

BASE_PATH = "/api/v1/analyst-references/subscriptions/source-management"


def _payload(
    *,
    name: str = "Official Research Source",
    domain: str = "research.example.com",
    feed_url: str = ("https://research.example.com/feed"),
    confirm: bool = False,
) -> dict[str, object]:
    return {
        "name": name,
        "sourceGrade": "A",
        "domain": domain,
        "official": True,
        "enabled": True,
        "feedUrl": feed_url,
        "providerType": "REFERENCE_INDEX",
        "language": "en",
        "requestIntervalSeconds": 21600,
        "timeoutSeconds": 10,
        "maxItems": 50,
        "originalSourceName": None,
        "confirm": confirm,
    }


def _source_count(
    database: Database,
) -> int:
    with database.session_scope() as session:
        return int(session.scalar(select(func.count()).select_from(SourceRecord)) or 0)


def _create_source(
    client: TestClient,
    *,
    name: str = "Official Research Source",
) -> dict[str, object]:
    response = client.post(
        f"{BASE_PATH}/import",
        json=_payload(
            name=name,
            confirm=True,
        ),
    )

    assert response.status_code == 201
    return response.json()["source"]


def test_source_preview_confirm_list_and_detail(
    api_client: TestClient,
    api_database: Database,
) -> None:
    before_count = _source_count(api_database)

    preview_response = api_client.post(
        f"{BASE_PATH}/import",
        json=_payload(confirm=False),
    )

    assert preview_response.status_code == 200

    preview = preview_response.json()

    assert preview["confirmed"] is False
    assert preview["wouldCreate"] is True
    assert preview["duplicate"]["duplicate"] is False
    assert preview["validationWarnings"] == []
    assert preview["normalizedSource"]["providerType"] == "REFERENCE_INDEX"

    assert _source_count(api_database) == before_count

    confirm_response = api_client.post(
        f"{BASE_PATH}/import",
        json=_payload(confirm=True),
    )

    assert confirm_response.status_code == 201

    source = confirm_response.json()["source"]

    assert source["name"] == ("Official Research Source")
    assert source["sourceType"] == ("EXPERT_REFERENCE")
    assert source["official"] is True
    assert source["enabled"] is True
    assert source["activeSubscriptionCount"] == 0
    assert source["totalSubscriptionCount"] == 0

    assert _source_count(api_database) == before_count + 1

    list_response = api_client.get(BASE_PATH)

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    detail_response = api_client.get(f"{BASE_PATH}/{source['id']}")

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == (source["id"])


def test_source_duplicate_preview_and_confirm_block(
    api_client: TestClient,
    api_database: Database,
) -> None:
    created = _create_source(api_client)

    before_count = _source_count(api_database)

    duplicate_preview = api_client.post(
        f"{BASE_PATH}/import",
        json=_payload(
            name=created["name"],
            feed_url=("https://research.example.com/another-feed"),
            confirm=False,
        ),
    )

    assert duplicate_preview.status_code == 200

    preview = duplicate_preview.json()

    assert preview["wouldCreate"] is False
    assert preview["duplicate"]["duplicate"] is True
    assert "name" in (preview["duplicate"]["matchedFields"])
    assert "DUPLICATE_SOURCE_NAME" in (preview["validationWarnings"])

    duplicate_confirm = api_client.post(
        f"{BASE_PATH}/import",
        json=_payload(
            name=created["name"],
            feed_url=("https://research.example.com/another-feed"),
            confirm=True,
        ),
    )

    assert duplicate_confirm.status_code == 409
    assert duplicate_confirm.json()["detail"]["code"] == ("REFERENCE_SOURCE_IMPORT_BLOCKED")

    assert _source_count(api_database) == before_count


def test_source_preview_blocks_unsafe_url_without_write(
    api_client: TestClient,
    api_database: Database,
) -> None:
    before_count = _source_count(api_database)

    response = api_client.post(
        f"{BASE_PATH}/import",
        json=_payload(
            domain="localhost.local",
            feed_url="http://127.0.0.1/feed",
            confirm=False,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["wouldCreate"] is False
    assert "INVALID_DOMAIN" in (body["validationWarnings"])
    assert "INSECURE_FEED_URL" in (body["validationWarnings"])

    assert _source_count(api_database) == before_count


def test_source_update_and_active_subscription_protection(
    api_client: TestClient,
    api_database: Database,
) -> None:
    source = _create_source(api_client)

    with api_database.session_scope() as session:
        subscription = ReferenceSubscriptionRecord(
            source_id=source["id"],
            subject_type=(ReferenceSubjectType.EXPERT),
            display_name="Protected Expert",
            match_mode=(ReferenceMatchMode.AUTHOR),
            match_terms=[
                "Protected Expert",
            ],
            enabled=True,
        )

        session.add(subscription)
        session.flush()

        subscription_id = subscription.id

    protected_response = api_client.patch(
        f"{BASE_PATH}/{source['id']}",
        json={
            "enabled": False,
        },
    )

    assert protected_response.status_code == 409
    assert (
        protected_response.json()["detail"]["code"] == "REFERENCE_SOURCE_ACTIVE_SUBSCRIPTIONS"
    )

    settings_response = api_client.patch(
        f"{BASE_PATH}/{source['id']}",
        json={
            "requestIntervalSeconds": 43200,
            "timeoutSeconds": 20,
            "maxItems": 75,
        },
    )

    assert settings_response.status_code == 200

    settings = settings_response.json()

    assert settings["requestIntervalSeconds"] == 43200
    assert settings["timeoutSeconds"] == 20
    assert settings["maxItems"] == 75
    assert settings["activeSubscriptionCount"] == 1
    assert settings["totalSubscriptionCount"] == 1

    with api_database.session_scope() as session:
        stored_subscription = session.get(
            ReferenceSubscriptionRecord,
            subscription_id,
        )

        assert stored_subscription is not None
        stored_subscription.enabled = False

    disabled_response = api_client.patch(
        f"{BASE_PATH}/{source['id']}",
        json={
            "enabled": False,
        },
    )

    assert disabled_response.status_code == 200
    assert disabled_response.json()["enabled"] is False
    assert disabled_response.json()["activeSubscriptionCount"] == 0
    assert disabled_response.json()["totalSubscriptionCount"] == 1


def test_source_update_rejects_duplicate_feed_url(
    api_client: TestClient,
) -> None:
    first = _create_source(
        api_client,
        name="First Official Source",
    )

    second_response = api_client.post(
        f"{BASE_PATH}/import",
        json=_payload(
            name="Second Official Source",
            feed_url=("https://research.example.com/second-feed"),
            confirm=True,
        ),
    )

    assert second_response.status_code == 201

    second = second_response.json()["source"]

    conflict_response = api_client.patch(
        f"{BASE_PATH}/{second['id']}",
        json={
            "feedUrl": first["feedUrl"],
        },
    )

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"]["code"] == ("REFERENCE_SOURCE_DUPLICATE")
