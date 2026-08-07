from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import Database
from app.models.database import (
    SourceGrade,
    SourceRecord,
)


def _source(
    *,
    name: str,
    domain: str,
    source_type: str = "EXPERT_REFERENCE",
    official: bool = True,
    enabled: bool = True,
    feed_url: str | None = "https://example.com/feed",
    provider_type: str | None = "RSS",
) -> SourceRecord:
    return SourceRecord(
        name=name,
        source_type=source_type,
        source_grade=SourceGrade.A,
        domain=domain,
        official=official,
        enabled=enabled,
        feed_url=feed_url,
        provider_type=provider_type,
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=10,
        max_items=50,
        original_source_name=None,
    )


def test_subscription_source_list_is_empty(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/analyst-references/subscriptions/sources")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }


def test_subscription_source_list_returns_only_eligible_sources(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        session.add_all(
            [
                _source(
                    name="Oaktree Official Insights",
                    domain="oaktreecapital.com",
                    feed_url=("https://www.oaktreecapital.com/insights/rss"),
                ),
                _source(
                    name="Unofficial Expert Feed",
                    domain="unofficial.example",
                    official=False,
                ),
                _source(
                    name="Disabled Expert Feed",
                    domain="disabled.example",
                    enabled=False,
                ),
                _source(
                    name="General Company News",
                    domain="company-news.example",
                    source_type="COMPANY_NEWS",
                ),
                _source(
                    name="Missing Feed Source",
                    domain="missing-feed.example",
                    feed_url=None,
                ),
                _source(
                    name="Missing Provider Source",
                    domain="missing-provider.example",
                    provider_type=None,
                ),
            ]
        )

    response = api_client.get("/api/v1/analyst-references/subscriptions/sources")

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert len(body["items"]) == 1

    source = body["items"][0]

    assert source["name"] == ("Oaktree Official Insights")
    assert source["domain"] == ("oaktreecapital.com")
    assert source["sourceType"] == ("EXPERT_REFERENCE")
    assert source["sourceGrade"] == "A"
    assert source["official"] is True
    assert source["enabled"] is True
    assert source["providerType"] == "RSS"


def test_subscription_source_list_supports_query(
    api_client: TestClient,
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        session.add_all(
            [
                _source(
                    name="Oaktree Official Insights",
                    domain="oaktreecapital.com",
                ),
                _source(
                    name="Berkshire Hathaway Letters",
                    domain="berkshirehathaway.com",
                ),
            ]
        )

    response = api_client.get(
        "/api/v1/analyst-references/subscriptions/sources",
        params={
            "query": "Berkshire",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["items"][0]["name"] == ("Berkshire Hathaway Letters")
