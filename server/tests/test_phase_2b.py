from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from xml.etree import ElementTree

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.database import Database
from app.models.contracts import VerificationStatus
from app.models.database import (
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
    SourceGrade,
    SourceRecord,
    WatchEntityRecord,
)
from app.models.disclosures import (
    AssetType,
    CertaintyLevel,
    InstrumentRecord,
    InstrumentVerificationStatus,
    LifecycleStatus,
    NewsProviderType,
    NewsReferenceRecord,
    NewsSummaryStatus,
    ProviderCursorRecord,
    ProviderName,
    ProviderStatus,
)
from app.providers.news_feed import NewsFeedItem, NewsFeedProvider, NewsFeedResult
from app.repositories.disclosures import DisclosureRepository
from app.services.disclosures import DisclosureIngest, DisclosureService
from app.services.news import (
    NewsService,
    NewsSyncService,
    canonicalize_url,
    certainty_for,
)
from app.services.retention import RetentionService

NOW = datetime(2026, 7, 26, 12, tzinfo=UTC)


def news_settings(**values: str) -> Settings:
    environment = {
        "DATABASE_URL": "sqlite+pysqlite://",
        "NEWS_SYNC_ENABLED": "true",
        "NEWS_FEED_SYNC_ENABLED": "true",
    }
    environment.update(values)
    return Settings.from_env(environment)


def source(
    *,
    name: str = "Fixture News",
    grade: SourceGrade = SourceGrade.B,
    official: bool = False,
    provider: NewsProviderType = NewsProviderType.RSS,
    original_source_name: str | None = None,
    enabled: bool = True,
) -> SourceRecord:
    return SourceRecord(
        name=name,
        source_type="NEWS_FEED",
        source_grade=grade,
        domain="fixture.invalid",
        official=official,
        enabled=enabled,
        feed_url="https://fixture.invalid/feed.xml",
        provider_type=provider.value,
        language="ko",
        request_interval_seconds=60,
        timeout_seconds=10,
        max_items=50,
        original_source_name=original_source_name,
    )


def instrument() -> InstrumentRecord:
    return InstrumentRecord(
        canonical_symbol="005930",
        display_name="삼성전자",
        local_name="삼성전자",
        exchange="KRX",
        market="KRX",
        country="KR",
        currency=Currency.KRW,
        asset_type=AssetType.EQUITY,
        verification_status=InstrumentVerificationStatus.VERIFIED,
        verification_source="OPENDART",
        verified_at=NOW,
    )


def portfolio(instrument_id: str) -> PortfolioItemRecord:
    return PortfolioItemRecord(
        instrument_id=instrument_id,
        asset_type=AssetType.EQUITY,
        symbol="005930",
        name="삼성전자",
        market="KRX",
        currency=Currency.KRW,
        holding_status=HoldingStatus.WATCHLIST,
        quantity=Decimal("0"),
        investment_horizon=InvestmentHorizon.UNSET,
        strategy="",
    )


def feed_item(
    item_id: str = "item-1",
    *,
    title: str = "삼성전자 지원 계획 발표",
    url: str | None = None,
    published_at: datetime = NOW,
    snippet: str | None = "삼성전자 지원 계획이 발표되었습니다.",
) -> NewsFeedItem:
    return NewsFeedItem(
        provider_item_id=item_id,
        title=title,
        original_url=url or f"https://fixture.invalid/{item_id}",
        published_at=published_at,
        source_updated_at=None,
        snippet=snippet,
    )


@pytest.mark.parametrize(
    ("enabled", "feed_url", "expected"),
    [
        (False, "https://fixture.invalid/feed.xml", ProviderStatus.NOT_CONFIGURED),
        (True, None, ProviderStatus.NOT_CONFIGURED),
        (True, "https://fixture.invalid/feed.xml", ProviderStatus.READY),
    ],
)
def test_news_provider_configuration(
    enabled: bool, feed_url: str | None, expected: ProviderStatus
) -> None:
    record = source(enabled=enabled)
    record.feed_url = feed_url
    assert NewsFeedProvider(news_settings(), record).status is expected


def test_parse_rss_metadata_without_full_article() -> None:
    xml = b"""<rss><channel><item><guid>1</guid><title>Fixture</title>
    <link>https://fixture.invalid/a</link>
    <pubDate>Sun, 26 Jul 2026 12:00:00 GMT</pubDate>
    <description><![CDATA[<b>Short</b> snippet]]></description>
    </item></channel></rss>"""
    item = NewsFeedProvider.parse(xml)[0]
    assert item.provider_item_id == "1"
    assert item.snippet == "Short snippet"
    assert not hasattr(item, "full_content")


def test_parse_atom_metadata() -> None:
    xml = b"""<feed xmlns="http://www.w3.org/2005/Atom">
    <entry><id>atom-1</id><title>Atom fixture</title>
    <link href="https://fixture.invalid/atom"/>
    <updated>2026-07-26T12:00:00Z</updated><summary>Short</summary></entry></feed>"""
    item = NewsFeedProvider.parse(xml)[0]
    assert item.provider_item_id == "atom-1"
    assert item.published_at.tzinfo is UTC


def test_empty_feed_is_valid_empty_result() -> None:
    assert NewsFeedProvider.parse(b"<rss><channel /></rss>") == []


def test_invalid_feed_is_rejected() -> None:
    with pytest.raises(ElementTree.ParseError):
        NewsFeedProvider.parse(b"<rss>")


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(403, ProviderStatus.ERROR), (429, ProviderStatus.RATE_LIMITED)],
)
def test_feed_access_errors(status_code: int, expected: ProviderStatus) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, request=request)
        )
    )
    result = NewsFeedProvider(
        news_settings(),
        source(),
        client=client,
        sleep=lambda _: None,
        max_attempts=1,
    ).fetch()
    assert result.status is expected


def test_feed_timeout_is_bounded() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture", request=request)

    result = NewsFeedProvider(
        news_settings(),
        source(),
        client=httpx.Client(transport=httpx.MockTransport(timeout)),
        sleep=lambda _: None,
        max_attempts=1,
    ).fetch()
    assert result.status is ProviderStatus.ERROR


def test_feed_uses_bounded_backoff_before_success() -> None:
    attempts = 0
    delays: list[float] = []

    def response(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(429, request=request)
        return httpx.Response(200, content=b"<rss><channel /></rss>", request=request)

    result = NewsFeedProvider(
        news_settings(),
        source(),
        client=httpx.Client(transport=httpx.MockTransport(response)),
        sleep=delays.append,
        max_attempts=3,
    ).fetch()
    assert result.status is ProviderStatus.READY
    assert attempts == 3
    assert delays == [1.0, 2.0]


def test_feed_max_items_is_enforced() -> None:
    items = "".join(
        f"<item><guid>{index}</guid><title>T{index}</title>"
        f"<link>https://fixture.invalid/{index}</link>"
        "<pubDate>Sun, 26 Jul 2026 12:00:00 GMT</pubDate></item>"
        for index in range(3)
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=f"<rss><channel>{items}</channel></rss>".encode(),
                request=request,
            )
        )
    )
    result = NewsFeedProvider(
        news_settings(NEWS_MAX_ITEMS_PER_SOURCE="1"),
        source(),
        client=client,
    ).fetch()
    assert len(result.items) == 1


def test_canonical_url_removes_tracking_and_fragment() -> None:
    value = canonicalize_url("HTTPS://Fixture.Invalid/a?utm_source=x&b=2&a=1#section")
    assert value == "https://fixture.invalid/a?a=1&b=2"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("지원 확정", CertaintyLevel.CONFIRMED),
        ("지원 계획", CertaintyLevel.PLANNED),
        ("지원 검토", CertaintyLevel.UNDER_REVIEW),
        ("지원 가능성", CertaintyLevel.POSSIBLE),
        ("근거 없는 전망", CertaintyLevel.SPECULATIVE),
    ],
)
def test_certainty_is_not_flattened(text: str, expected: CertaintyLevel) -> None:
    assert certainty_for(text) is expected


def test_news_ingest_creates_reference_event_and_claim(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        holding = portfolio(company.id)
        session.add(holding)
        session.flush()
        result = NewsService(session).ingest(
            source=publisher,
            instrument=company,
            item=feed_item(),
            portfolio_item_id=holding.id,
            now=NOW,
        )
        assert result.created is True
        assert result.event.news_reference_count == 1
        assert result.reference.summary_status is NewsSummaryStatus.RULE_BASED
        assert 0 <= result.reference.trust_score <= 100


def test_same_provider_item_is_idempotent(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        service = NewsService(session)
        first = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(),
            portfolio_item_id=None,
            now=NOW,
        )
        second = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(),
            portfolio_item_id=None,
            now=NOW + timedelta(days=1),
        )
        assert second.created is False
        assert second.reference.id == first.reference.id


def test_canonical_url_duplicate_is_idempotent(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        service = NewsService(session)
        first = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(
                "url-1",
                url="https://fixture.invalid/story?utm_source=first&a=1",
            ),
            portfolio_item_id=None,
            now=NOW,
        )
        second = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(
                "url-2",
                url="https://fixture.invalid/story?a=1&utm_source=second#top",
            ),
            portfolio_item_id=None,
            now=NOW + timedelta(hours=1),
        )
        assert second.created is False
        assert second.reference.id == first.reference.id


def test_news_reference_normalizes_and_bounds_metadata(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source(grade=SourceGrade.C)
        session.add_all([company, publisher])
        session.flush()
        reference = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item(
                    "metadata",
                    title="  삼성전자---지원   계획  ",
                    snippet="x" * 1200,
                ),
                portfolio_item_id=None,
                now=NOW,
            )
            .reference
        )
        assert reference.normalized_title == "삼성전자 지원 계획"
        assert len(reference.snippet or "") == 1000
        assert reference.source_grade is SourceGrade.C
        assert reference.published_at.tzinfo is UTC
        assert 0 <= reference.trust_score <= 100


def test_day_10_and_day_15_reuse_same_event(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        service = NewsService(session)
        first = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(
                "day-10",
                title="2026-07-10 삼성전자 지원 계획 발표",
                published_at=NOW - timedelta(days=16),
            ),
            portfolio_item_id=None,
            now=NOW - timedelta(days=16),
        )
        second = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(
                "day-15",
                title="2026-07-15 삼성전자 지원 계획 발표",
                published_at=NOW - timedelta(days=11),
            ),
            portfolio_item_id=None,
            now=NOW - timedelta(days=11),
        )
        assert second.event.id == first.event.id
        assert second.reference.stale_reused is True
        assert second.reference.material_change is False


def test_new_amount_updates_existing_event(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        service = NewsService(session)
        first = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item("amount-1", title="삼성전자 지원 100억원 계획"),
            portfolio_item_id=None,
            now=NOW,
        )
        second = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(
                "amount-2",
                title="삼성전자 지원 200억원 계획",
                snippet="삼성전자 지원 금액이 200억원으로 변경되었습니다.",
                published_at=NOW + timedelta(days=1),
            ),
            portfolio_item_id=None,
            now=NOW + timedelta(days=1),
        )
        assert second.event.id == first.event.id
        assert second.reference.material_change is True
        assert second.event.lifecycle_status is LifecycleStatus.UPDATED


@pytest.mark.parametrize(
    ("title", "verification", "lifecycle"),
    [
        (
            "삼성전자 보도 정정",
            VerificationStatus.CORRECTED,
            LifecycleStatus.CORRECTED,
        ),
        (
            "삼성전자 공식 부인",
            VerificationStatus.OFFICIALLY_DENIED,
            LifecycleStatus.DENIED,
        ),
    ],
)
def test_correction_and_denial(
    api_database: Database,
    title: str,
    verification: VerificationStatus,
    lifecycle: LifecycleStatus,
) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source(official=True, grade=SourceGrade.A)
        session.add_all([company, publisher])
        session.flush()
        result = NewsService(session).ingest(
            source=publisher,
            instrument=company,
            item=feed_item(title=title),
            portfolio_item_id=None,
            now=NOW,
        )
        assert result.reference.verification_status is verification
        assert result.reference.lifecycle_status is lifecycle


def test_metadata_only_summary_when_snippet_missing(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        reference = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item(snippet=None),
                portfolio_item_id=None,
                now=NOW,
            )
            .reference
        )
        assert reference.summary_status is NewsSummaryStatus.METADATA_ONLY
        assert "원문" in (reference.short_summary or "")


@pytest.mark.parametrize("provider", [ProviderName.OPENDART, ProviderName.SEC_EDGAR])
def test_news_matches_official_disclosure(
    api_database: Database, provider: ProviderName
) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        DisclosureService(DisclosureRepository(session)).ingest(
            DisclosureIngest(
                instrument_id=company.id,
                provider=provider,
                provider_document_id=f"official-{provider.value}",
                title="삼성전자 지원 계획 발표",
                company_name="삼성전자",
                official_url=f"https://official.invalid/{provider.value}",
                published_at=NOW,
                event_type="OFFICIAL",
                claim="삼성전자 지원 계획 발표",
                summary="삼성전자 지원 계획 발표",
            ),
            now=NOW,
        )
        reference = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item(),
                portfolio_item_id=None,
                now=NOW,
            )
            .reference
        )
        assert reference.verification_status is VerificationStatus.OFFICIAL_CONFIRMED
        assert len(reference.official_reference_ids) == 1


def test_confirmed_news_conflicts_with_official_review(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        DisclosureService(DisclosureRepository(session)).ingest(
            DisclosureIngest(
                instrument_id=company.id,
                provider=ProviderName.OPENDART,
                provider_document_id="official-review",
                title="삼성전자 지원 검토",
                company_name="삼성전자",
                official_url="https://official.invalid/review",
                published_at=NOW,
                event_type="OFFICIAL",
                claim="삼성전자 지원 검토",
                summary="삼성전자 지원 검토",
            ),
            now=NOW,
        )
        reference = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item(
                    title="삼성전자 지원 확정",
                    snippet="삼성전자 지원 확정",
                ),
                portfolio_item_id=None,
                now=NOW,
            )
            .reference
        )
        assert reference.verification_status is VerificationStatus.CONFLICTING


def test_later_official_record_updates_existing_news_event(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        service = NewsService(session)
        first = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item("before-official"),
            portfolio_item_id=None,
            now=NOW,
        )
        DisclosureService(DisclosureRepository(session)).ingest(
            DisclosureIngest(
                instrument_id=company.id,
                provider=ProviderName.OPENDART,
                provider_document_id="official-later",
                title="삼성전자 지원 계획 발표",
                company_name="삼성전자",
                official_url="https://official.invalid/later",
                published_at=NOW + timedelta(days=1),
                event_type="OFFICIAL",
                claim="삼성전자 지원 계획 발표",
                summary="삼성전자 지원 계획 발표",
            ),
            now=NOW + timedelta(days=1),
        )
        later = service.ingest(
            source=publisher,
            instrument=company,
            item=feed_item(
                "after-official",
                url="https://other.invalid/after-official",
                published_at=NOW + timedelta(days=2),
            ),
            portfolio_item_id=None,
            now=NOW + timedelta(days=2),
        )
        assert later.event.id == first.event.id
        assert later.reference.material_change is True
        assert later.event.verification_status is VerificationStatus.OFFICIAL_CONFIRMED
        assert later.event.lifecycle_status is LifecycleStatus.UPDATED


def test_republish_from_same_original_source_counts_once(api_database: Database) -> None:
    with api_database.session_scope() as session:
        company = instrument()
        first_source = source(name="Outlet A", original_source_name="Wire")
        second_source = source(name="Outlet B", original_source_name="Wire")
        session.add_all([company, first_source, second_source])
        session.flush()
        service = NewsService(session)
        first = service.ingest(
            source=first_source,
            instrument=company,
            item=feed_item("wire-1"),
            portfolio_item_id=None,
            now=NOW,
        )
        second = service.ingest(
            source=second_source,
            instrument=company,
            item=feed_item(
                "wire-2",
                url="https://other.invalid/wire-2",
                published_at=NOW + timedelta(hours=1),
            ),
            portfolio_item_id=None,
            now=NOW + timedelta(hours=1),
        )
        assert second.event.id == first.event.id
        assert second.event.independent_origin_count == 1
        assert second.reference.independent_origin is False


def test_two_independent_grade_b_sources_confirm_same_event(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        company = instrument()
        first_source = source(name="Outlet One")
        second_source = source(name="Outlet Two")
        session.add_all([company, first_source, second_source])
        session.flush()
        service = NewsService(session)
        first = service.ingest(
            source=first_source,
            instrument=company,
            item=feed_item("multi-1"),
            portfolio_item_id=None,
            now=NOW,
        )
        second = service.ingest(
            source=second_source,
            instrument=company,
            item=feed_item(
                "multi-2",
                url="https://other.invalid/multi-2",
                published_at=NOW + timedelta(hours=1),
            ),
            portfolio_item_id=None,
            now=NOW + timedelta(hours=1),
        )
        assert second.event.id == first.event.id
        assert second.reference.verification_status is (
            VerificationStatus.MULTI_SOURCE_CONFIRMED
        )
        assert second.event.independent_origin_count == 2


def test_news_model_has_no_full_article_fields() -> None:
    forbidden = {"raw_html", "raw_body", "full_text", "article_body", "image"}
    assert forbidden.isdisjoint(NewsReferenceRecord.__table__.columns.keys())


def test_news_api_list_detail_and_404(api_database: Database, api_client: TestClient) -> None:
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        record = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item(),
                portfolio_item_id=None,
                now=NOW,
            )
            .reference
        )
        record_id = record.id
    listing = api_client.get("/api/v1/news?sourceGrade=B&limit=1&offset=0")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    detail = api_client.get(f"/api/v1/news/{record_id}")
    assert detail.status_code == 200
    assert detail.json()["trustScoreExplanation"].startswith("진실 확률이 아니라")
    assert "rawHtml" not in detail.json()
    missing = api_client.get("/api/v1/news/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


def test_important_information_import_preview_confirm_and_duplicate(
    api_database: Database,
    api_client: TestClient,
) -> None:
    portfolio_response = api_client.post(
        "/api/v1/portfolio",
        json={
            "assetType": "EQUITY",
            "symbol": "MSFT",
            "name": "Microsoft",
            "market": "NASDAQ",
            "currency": "USD",
            "holdingStatus": "WATCHLIST",
            "trackingStatus": "WATCHLIST",
            "quantity": "0",
            "averagePrice": None,
            "investmentHorizon": "UNSET",
            "strategy": "",
            "targetAllocation": None,
            "maxLossPercent": None,
            "notes": None,
        },
    )
    assert portfolio_response.status_code == 201, portfolio_response.text
    portfolio_id = portfolio_response.json()["id"]

    with api_database.session_scope() as session:
        session.add(
            SourceRecord(
                name="TipRanks Reference Classification",
                source_type="EXPERT_REFERENCE",
                source_grade=SourceGrade.B,
                domain="tipranks.com",
                official=False,
                enabled=True,
                feed_url="https://www.tipranks.com/",
                provider_type="REFERENCE_INDEX",
                language="en",
                request_interval_seconds=21600,
                timeout_seconds=20,
                max_items=30,
                original_source_name="TipRanks",
            )
        )

    payload = {
        "sourceUrl": (
            "https://www.tipranks.com/news/"
            "microsoft-stock-price-forecast"
            "?utm_source=recording#summary"
        ),
        "publisherName": "TipRanks",
        "title": "Microsoft 목표가 상향과 AI·클라우드 성장 평가",
        "publishedAt": NOW.isoformat(),
        "primaryClaim": (
            "Microsoft에 대한 매수 의견을 유지하고 목표가를 610달러에서 640달러로 상향했습니다."
        ),
        "publicSummary": (
            "AI와 클라우드 성장 흐름을 근거로 제시한 공개 금융 미디어 자료입니다."
        ),
        "portfolioItemId": portfolio_id,
        "language": "ko",
        "materialChange": True,
        "confirm": False,
    }

    preview_response = api_client.post(
        "/api/v1/news/import-link",
        json=payload,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["confirmed"] is False
    assert preview["wouldCreate"] is True
    assert preview["classification"]["sourceGrade"] == "B"
    assert preview["classification"]["officialSource"] is False
    assert preview["classification"]["predictedVerificationStatus"] == "NEEDS_VERIFICATION"
    assert preview["duplicate"]["duplicate"] is False
    assert "utm_source" not in preview["normalizedUrl"]
    assert "#" not in preview["normalizedUrl"]

    confirm_response = api_client.post(
        "/api/v1/news/import-link",
        json={**payload, "confirm": True},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    confirmed = confirm_response.json()
    assert confirmed["confirmed"] is True
    assert confirmed["reference"]["sourceGrade"] == "B"
    assert confirmed["reference"]["verificationStatus"] == "NEEDS_VERIFICATION"
    assert confirmed["reference"]["materialChange"] is True
    assert confirmed["reference"]["relatedInstrument"]["canonicalSymbol"] == "MSFT"

    listing = api_client.get("/api/v1/news?limit=10")
    events = api_client.get("/api/v1/information-events?limit=10")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert events.status_code == 200
    assert events.json()["total"] == 1

    duplicate_response = api_client.post(
        "/api/v1/news/import-link",
        json=payload,
    )
    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["wouldCreate"] is False
    assert duplicate["duplicate"]["duplicate"] is True


def test_system_info_news_defaults_are_not_live(api_client: TestClient) -> None:
    body = api_client.get("/api/v1/system/info").json()
    assert body["newsConfigured"] is False
    assert body["newsProviderStatus"] == "NOT_CONFIGURED"
    assert body["automaticTradingEnabled"] is False
    assert body["aiAutomationEnabled"] is False


def test_news_sync_saves_success_cursor(
    api_database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FixtureProvider:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def fetch(self, *, limit: int | None = None) -> NewsFeedResult:
            del limit
            return NewsFeedResult(status=ProviderStatus.READY, items=(feed_item(),))

    monkeypatch.setattr("app.services.news.NewsFeedProvider", FixtureProvider)
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        session.add(portfolio(company.id))
        session.flush()
        output = NewsSyncService(session, news_settings()).sync(now=NOW)
        assert output["status"] == "SUCCEEDED"
        cursor = session.scalar(select(ProviderCursorRecord))
        assert cursor is not None
        assert cursor.last_successful_at == NOW


@pytest.mark.parametrize(
    ("title", "aliases", "matched"),
    [
        ("005930 지원 계획", [], True),
        ("삼성전자 지원 계획", [], True),
        ("갤럭시 사업 계획", ["갤럭시"], True),
        ("관련 없는 기업 소식", [], False),
        ("삼성전자 광고 sponsored", [], False),
    ],
)
def test_news_relevance_rules(
    api_database: Database,
    title: str,
    aliases: list[str],
    matched: bool,
) -> None:
    with api_database.session_scope() as session:
        company = instrument()
        session.add(company)
        session.flush()
        holding = portfolio(company.id)
        session.add(holding)
        if aliases:
            session.add(WatchEntityRecord(symbol="005930", aliases=aliases))
        session.flush()
        candidates = [(company, holding.id)]
        result = NewsSyncService(session, news_settings())._match(
            feed_item(title=title, snippet=title), candidates
        )
        assert (result is not None) is matched


@pytest.mark.parametrize(
    ("verification", "holding_status"),
    [
        (InstrumentVerificationStatus.UNVERIFIED, HoldingStatus.WATCHLIST),
        (InstrumentVerificationStatus.VERIFIED, HoldingStatus.SOLD),
    ],
)
def test_news_sync_excludes_unverified_and_sold_by_default(
    api_database: Database,
    verification: InstrumentVerificationStatus,
    holding_status: HoldingStatus,
) -> None:
    with api_database.session_scope() as session:
        company = instrument()
        company.verification_status = verification
        session.add(company)
        session.flush()
        holding = portfolio(company.id)
        holding.holding_status = holding_status
        session.add(holding)
        session.flush()
        assert NewsSyncService(session, news_settings())._eligible_instruments(None) == []


def test_failed_news_sync_preserves_last_successful_cursor(
    api_database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailedProvider:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def fetch(self, *, limit: int | None = None) -> NewsFeedResult:
            del limit
            return NewsFeedResult(status=ProviderStatus.ERROR, items=())

    monkeypatch.setattr("app.services.news.NewsFeedProvider", FailedProvider)
    previous = NOW - timedelta(days=2)
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        session.add(portfolio(company.id))
        session.add(
            ProviderCursorRecord(
                provider=ProviderName.SYSTEM_BASELINE,
                scope=f"news:{publisher.id}",
                last_successful_at=previous,
            )
        )
        session.flush()
        output = NewsSyncService(session, news_settings()).sync(now=NOW)
        cursor = session.get(
            ProviderCursorRecord,
            {
                "provider": ProviderName.SYSTEM_BASELINE,
                "scope": f"news:{publisher.id}",
            },
        )
        assert output["status"] == "FAILED"
        assert cursor is not None
        assert cursor.last_successful_at == previous


def test_news_retention_dry_run_and_protected_lifecycle(
    api_database: Database,
) -> None:
    enabled_settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "RETENTION_CLEANUP_ENABLED": "true",
            "GENERAL_SUMMARY_RETENTION_DAYS": "1",
            "DUPLICATE_EVIDENCE_RETENTION_DAYS": "1",
        }
    )
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        protected = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item("protected"),
                portfolio_item_id=None,
                now=NOW - timedelta(days=3),
            )
            .reference
        )
        stale = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item(
                    "stale",
                    url="https://other.invalid/stale",
                    published_at=NOW - timedelta(days=2),
                ),
                portfolio_item_id=None,
                now=NOW - timedelta(days=2),
            )
            .reference
        )
        stale.lifecycle_status = LifecycleStatus.STALE
        stale.updated_at = NOW - timedelta(days=2)
        protected.updated_at = NOW - timedelta(days=3)
        session.flush()

        preview = RetentionService(session, enabled_settings).run(now=NOW, dry_run=True)
        assert preview.general_news_summaries == 1
        assert stale.short_summary is not None

        result = RetentionService(session, enabled_settings).run(
            now=NOW, dry_run=False, confirm=True
        )
        assert result.status == "SUCCEEDED"
        assert stale.short_summary is None
        assert stale.snippet is None
        assert protected.short_summary is not None


@pytest.mark.parametrize(
    ("lifecycle", "material_change", "pinned"),
    [
        (LifecycleStatus.ACTIVE, False, False),
        (LifecycleStatus.CORRECTED, False, False),
        (LifecycleStatus.DENIED, False, False),
        (LifecycleStatus.STALE, True, False),
        (LifecycleStatus.STALE, False, True),
    ],
)
def test_news_retention_protects_important_references(
    api_database: Database,
    lifecycle: LifecycleStatus,
    material_change: bool,
    pinned: bool,
) -> None:
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "RETENTION_CLEANUP_ENABLED": "true",
            "GENERAL_SUMMARY_RETENTION_DAYS": "1",
            "DUPLICATE_EVIDENCE_RETENTION_DAYS": "1",
        }
    )
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        reference = (
            NewsService(session)
            .ingest(
                source=publisher,
                instrument=company,
                item=feed_item(f"protected-{lifecycle.value}-{material_change}-{pinned}"),
                portfolio_item_id=None,
                now=NOW - timedelta(days=2),
            )
            .reference
        )
        reference.lifecycle_status = lifecycle
        reference.material_change = material_change
        reference.pinned = pinned
        reference.updated_at = NOW - timedelta(days=2)
        session.flush()
        RetentionService(session, settings).run(now=NOW, dry_run=False, confirm=True)
        assert reference.short_summary is not None


def test_phase_2b_integration_smoke(
    api_database: Database,
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued_items = [
        feed_item("smoke-first", title="삼성전자 지원 100억원 계획"),
        feed_item(
            "smoke-republish",
            title="삼성전자 지원 100억원 계획",
            url="https://other.invalid/smoke-republish",
            published_at=NOW + timedelta(days=1),
        ),
        feed_item(
            "smoke-update",
            title="삼성전자 지원 200억원 계획",
            url="https://other.invalid/smoke-update",
            published_at=NOW + timedelta(days=2),
            snippet="삼성전자 지원 금액이 200억원으로 변경되었습니다.",
        ),
        feed_item(
            "smoke-official",
            title="삼성전자 지원 200억원 계획",
            url="https://third.invalid/smoke-official",
            published_at=NOW + timedelta(days=4),
            snippet="삼성전자 지원 200억원 계획",
        ),
    ]

    class QueueProvider:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def fetch(self, *, limit: int | None = None) -> NewsFeedResult:
            del limit
            return NewsFeedResult(
                status=ProviderStatus.READY,
                items=(queued_items.pop(0),),
            )

    monkeypatch.setattr("app.services.news.NewsFeedProvider", QueueProvider)
    with api_database.session_scope() as session:
        company, publisher = instrument(), source()
        session.add_all([company, publisher])
        session.flush()
        session.add(portfolio(company.id))
        session.flush()
        sync = NewsSyncService(session, news_settings())

        assert sync.sync(now=NOW)["created"] == 1
        first = session.scalar(
            select(NewsReferenceRecord).where(
                NewsReferenceRecord.provider_item_id == "smoke-first"
            )
        )
        assert first is not None
        event_id = first.information_event_id

        sync.sync(now=NOW + timedelta(days=1))
        republish = session.scalar(
            select(NewsReferenceRecord).where(
                NewsReferenceRecord.provider_item_id == "smoke-republish"
            )
        )
        assert republish is not None
        assert republish.information_event_id == event_id
        assert republish.stale_reused is True

        sync.sync(now=NOW + timedelta(days=2))
        update = session.scalar(
            select(NewsReferenceRecord).where(
                NewsReferenceRecord.provider_item_id == "smoke-update"
            )
        )
        assert update is not None
        assert update.information_event_id == event_id
        assert update.material_change is True

        DisclosureService(DisclosureRepository(session)).ingest(
            DisclosureIngest(
                instrument_id=company.id,
                provider=ProviderName.OPENDART,
                provider_document_id="smoke-official",
                title="삼성전자 지원 200억원 계획 발표",
                company_name="삼성전자",
                official_url="https://official.invalid/smoke",
                published_at=NOW + timedelta(days=3),
                event_type="OFFICIAL",
                claim="삼성전자 지원 200억원 계획",
                summary="삼성전자 지원 200억원 계획",
            ),
            now=NOW + timedelta(days=3),
        )
        sync.sync(now=NOW + timedelta(days=4))
        official = session.scalar(
            select(NewsReferenceRecord).where(
                NewsReferenceRecord.provider_item_id == "smoke-official"
            )
        )
        assert official is not None
        assert official.information_event_id == event_id
        assert official.verification_status is VerificationStatus.OFFICIAL_CONFIRMED

    news_response = api_client.get("/api/v1/news?limit=10")
    disclosure_response = api_client.get("/api/v1/disclosures?limit=10")
    event_response = api_client.get(f"/api/v1/information-events/{event_id}")
    assert news_response.status_code == 200
    assert news_response.json()["total"] == 4
    assert disclosure_response.status_code == 200
    assert disclosure_response.json()["total"] == 1
    assert event_response.status_code == 200
    assert len(event_response.json()["newsReferences"]) == 4
