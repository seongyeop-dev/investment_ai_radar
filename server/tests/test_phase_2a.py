from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
)
from app.models.disclosures import (
    AssetType,
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    LifecycleStatus,
    ProviderName,
    ProviderStatus,
    TemporaryDocumentRecord,
)
from app.providers.opendart import OpenDartProvider
from app.providers.sec import SecEdgarProvider
from app.repositories.disclosures import DisclosureRepository
from app.services.disclosures import DisclosureIngest, DisclosureService
from app.services.retention import RetentionService

NOW = datetime(2026, 7, 25, tzinfo=UTC)


def _instrument(**values: object) -> InstrumentRecord:
    defaults = {
        "canonical_symbol": "005930",
        "display_name": "Samsung Electronics",
        "exchange": "KRX",
        "market": "KRX",
        "country": "KR",
        "currency": Currency.KRW,
        "asset_type": AssetType.EQUITY,
        "verification_status": InstrumentVerificationStatus.VERIFIED,
        "verification_source": ProviderName.OPENDART.value,
        "verified_at": NOW,
    }
    defaults.update(values)
    return InstrumentRecord(**defaults)


def _portfolio() -> PortfolioItemRecord:
    return PortfolioItemRecord(
        asset_type=AssetType.EQUITY,
        symbol="005930",
        name="Samsung",
        market="KRX",
        currency=Currency.KRW,
        holding_status=HoldingStatus.WATCHLIST,
        quantity=Decimal("0"),
        average_price=None,
        investment_horizon=InvestmentHorizon.UNSET,
        strategy="",
    )


def _ingest(
    instrument_id: str,
    document_id: str = "202607250001",
    **values: object,
) -> DisclosureIngest:
    defaults = {
        "instrument_id": instrument_id,
        "provider": ProviderName.OPENDART,
        "provider_document_id": document_id,
        "title": "Official material event",
        "company_name": "Samsung Electronics",
        "official_url": f"https://dart.fss.or.kr/{document_id}",
        "published_at": NOW,
        "event_type": "MATERIAL_EVENT",
        "claim": "The company disclosed a material event.",
    }
    defaults.update(values)
    return DisclosureIngest(**defaults)


@pytest.mark.parametrize(
    ("environment", "dart", "sec"),
    [
        ({}, ProviderStatus.NOT_CONFIGURED, ProviderStatus.NOT_CONFIGURED),
        (
            {
                "OPENDART_API_KEY": "1234567890123456789012345678901234567890",
                "OPENDART_SYNC_ENABLED": "true",
            },
            ProviderStatus.READY,
            ProviderStatus.NOT_CONFIGURED,
        ),
        (
            {"SEC_USER_AGENT": "fixture test@example.invalid", "SEC_SYNC_ENABLED": "true"},
            ProviderStatus.NOT_CONFIGURED,
            ProviderStatus.READY,
        ),
    ],
)
def test_provider_configuration_status(
    environment: dict[str, str], dart: ProviderStatus, sec: ProviderStatus
) -> None:
    settings = Settings.from_env(environment)
    assert OpenDartProvider(settings).status is dart
    assert SecEdgarProvider(settings).status is sec


def test_opendart_company_parser_preserves_leading_zeroes() -> None:
    xml = (
        b"<result><list><corp_code>00126380</corp_code>"
        b"<corp_name>Samsung</corp_name><stock_code>005930</stock_code>"
        b"<modify_date>20260725</modify_date></list></result>"
    )
    company = OpenDartProvider.parse_company_codes(xml, NOW)[0]
    assert company.corp_code == "00126380"
    assert company.stock_code == "005930"


def test_opendart_unlisted_company_has_no_stock_code() -> None:
    xml = (
        b"<result><list><corp_code>00000001</corp_code>"
        b"<corp_name>Unlisted</corp_name><stock_code></stock_code></list></result>"
    )
    assert OpenDartProvider.parse_company_codes(xml, NOW)[0].stock_code is None


def test_opendart_duplicate_corp_code_is_rejected() -> None:
    item = (
        "<list><corp_code>00000001</corp_code><corp_name>A</corp_name>"
        "<stock_code>000001</stock_code></list>"
    )
    with pytest.raises(ValueError, match="duplicate"):
        OpenDartProvider.parse_company_codes(f"<result>{item}{item}</result>".encode(), NOW)


def test_opendart_rate_limit_is_explicit() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(429, request=request))
    )
    provider = OpenDartProvider(
        Settings.from_env(
            {
                "OPENDART_API_KEY": "1234567890123456789012345678901234567890",
                "OPENDART_SYNC_ENABLED": "true",
            }
        ),
        client=client,
    )
    assert provider.fetch_company_codes().status is ProviderStatus.RATE_LIMITED


def test_sec_mapping_uppercases_ticker_and_zero_pads_cik() -> None:
    body = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [[320193, "Apple Inc.", "aapl", "Nasdaq"]],
    }
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=body, request=request)
        )
    )
    provider = SecEdgarProvider(
        Settings.from_env(
            {"SEC_USER_AGENT": "fixture test@example.invalid", "SEC_SYNC_ENABLED": "true"}
        ),
        client=client,
    )
    company = provider.fetch_company_tickers().companies[0]
    assert company.symbol == "AAPL"
    assert company.cik == "0000320193"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(403, ProviderStatus.ERROR), (429, ProviderStatus.RATE_LIMITED)],
)
def test_sec_handles_access_controls(status_code: int, expected: ProviderStatus) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, request=request)
        )
    )
    provider = SecEdgarProvider(
        Settings.from_env(
            {"SEC_USER_AGENT": "fixture test@example.invalid", "SEC_SYNC_ENABLED": "true"}
        ),
        client=client,
        sleep=lambda _: None,
        max_attempts=1,
    )
    assert provider.fetch_company_tickers().status is expected


def test_sec_timeout_is_bounded_and_reported() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    provider = SecEdgarProvider(
        Settings.from_env(
            {"SEC_USER_AGENT": "fixture test@example.invalid", "SEC_SYNC_ENABLED": "true"}
        ),
        client=httpx.Client(transport=httpx.MockTransport(timeout)),
        sleep=lambda _: None,
        max_attempts=1,
    )
    result = provider.fetch_company_tickers()
    assert result.status is ProviderStatus.NETWORK_UNAVAILABLE
    assert result.error_code == "NETWORK_UNAVAILABLE"


def test_sec_submission_marks_amendment_and_accepts_second_precision() -> None:
    body = {
        "name": "Fixture Corp",
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001"],
                "filingDate": ["2026-07-25"],
                "acceptanceDateTime": ["2026-07-25T12:00:00Z"],
                "reportDate": ["2026-06-30"],
                "form": ["10-Q/A"],
                "primaryDocument": ["fixture.htm"],
                "primaryDocDescription": ["Amended quarterly report"],
            }
        },
    }
    provider = SecEdgarProvider(
        Settings.from_env(
            {"SEC_USER_AGENT": "fixture test@example.invalid", "SEC_SYNC_ENABLED": "true"}
        ),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=body, request=request)
            )
        ),
    )
    disclosure = provider.fetch_submissions("1").disclosures[0]
    assert disclosure.amendment is True
    assert disclosure.published_at.tzinfo is UTC


@pytest.mark.parametrize(
    ("field", "value"),
    [("cik", "123"), ("corp_code", "123"), ("stock_code", "123")],
)
def test_mapping_identifier_lengths_are_validated(field: str, value: str) -> None:
    values = {
        "instrument_id": "instrument",
        "provider": ProviderName.OPENDART,
        "provider_company_id": "company",
        "source_url": "https://example.invalid",
        "fetched_at": NOW,
        "verified_at": NOW,
        field: value,
    }
    with pytest.raises(ValueError):
        InstrumentProviderMappingRecord(**values)


def test_instrument_search_and_manual_mapping_are_idempotent(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        instrument = _instrument()
        portfolio = _portfolio()
        session.add_all([instrument, portfolio])
        session.flush()
        ids = instrument.id, portfolio.id
    search = api_client.get("/api/v1/instruments/search?query=005930")
    assert search.status_code == 200
    assert search.json()["items"][0]["canonicalSymbol"] == "005930"
    for _ in range(2):
        response = api_client.post(
            f"/api/v1/portfolio/{ids[1]}/instrument",
            json={"instrumentId": ids[0]},
        )
        assert response.status_code == 200
        assert response.json()["instrumentVerificationStatus"] == "VERIFIED"


def test_instrument_mapping_rejects_wrong_market(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        instrument = _instrument(
            canonical_symbol="AAPL",
            market="NASDAQ",
            exchange="NASDAQ",
            country="US",
            currency=Currency.USD,
        )
        portfolio = _portfolio()
        session.add_all([instrument, portfolio])
        session.flush()
        ids = instrument.id, portfolio.id
    response = api_client.post(
        f"/api/v1/portfolio/{ids[1]}/instrument",
        json={"instrumentId": ids[0]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSTRUMENT_MARKET_MISMATCH"


def test_instrument_unmap_is_idempotent(api_database: Database, api_client: TestClient) -> None:
    with api_database.session_scope() as session:
        portfolio = _portfolio()
        session.add(portfolio)
        session.flush()
        item_id = portfolio.id
    for _ in range(2):
        assert api_client.delete(f"/api/v1/portfolio/{item_id}/instrument").status_code == 204


def test_disclosure_ingest_deduplicates_exact_document(api_database: Database) -> None:
    with api_database.session_scope() as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        service = DisclosureService(DisclosureRepository(session))
        first = service.ingest(_ingest(instrument.id), now=NOW)
        second = service.ingest(_ingest(instrument.id), now=NOW + timedelta(days=1))
        assert first[0].id == second[0].id
        assert second[2] is False
        assert first[1].source_count == 1


@pytest.mark.parametrize(
    ("flag", "lifecycle", "verification"),
    [
        ("denied", LifecycleStatus.DENIED, VerificationStatus.OFFICIALLY_DENIED),
        ("stale_reused", LifecycleStatus.STALE, VerificationStatus.STALE_REUSED),
    ],
)
def test_disclosure_lifecycle_signals(
    api_database: Database,
    flag: str,
    lifecycle: LifecycleStatus,
    verification: VerificationStatus,
) -> None:
    with api_database.session_scope() as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        values = {flag: True}
        record, event, created = DisclosureService(DisclosureRepository(session)).ingest(
            _ingest(instrument.id, **values), now=NOW
        )
        assert created is True
        assert record.lifecycle_status is lifecycle
        assert event.verification_status is verification


def test_disclosure_correction_links_original(api_database: Database) -> None:
    with api_database.session_scope() as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        service = DisclosureService(DisclosureRepository(session))
        original, _, _ = service.ingest(_ingest(instrument.id), now=NOW)
        correction, event, _ = service.ingest(
            _ingest(
                instrument.id,
                "202607250002",
                official_url="https://dart.fss.or.kr/202607250002",
                correction_of_document_id=original.provider_document_id,
            ),
            now=NOW + timedelta(days=1),
        )
        assert correction.correction_of_id == original.id
        assert event.lifecycle_status is LifecycleStatus.CORRECTED


def test_disclosure_api_does_not_expose_raw_body(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        record, _, _ = DisclosureService(DisclosureRepository(session)).ingest(
            _ingest(instrument.id), now=NOW
        )
        record_id = record.id
    response = api_client.get(f"/api/v1/disclosures/{record_id}")
    assert response.status_code == 200
    assert not {"rawBody", "rawText", "fullContent"} & response.json().keys()


def test_disclosure_list_filters_and_paginates(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        DisclosureService(DisclosureRepository(session)).ingest(_ingest(instrument.id), now=NOW)
    response = api_client.get(
        "/api/v1/disclosures?provider=OPENDART&materialChange=false&limit=1&offset=0"
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/disclosures/00000000-0000-0000-0000-000000000000",
        "/api/v1/information-events/00000000-0000-0000-0000-000000000000",
    ],
)
def test_official_read_api_missing_ids_return_404(api_client: TestClient, path: str) -> None:
    assert api_client.get(path).status_code == 404


def test_official_disclosure_import_preview_confirm_duplicate_and_domain_guard(
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
    payload = {
        "officialUrl": (
            "https://www.sec.gov/Archives/edgar/data/789019/"
            "000119312526000001/msft-20260725.htm?utm_source=recording#top"
        ),
        "title": "Microsoft 공식 SEC 공시",
        "publishedAt": NOW.isoformat(),
        "claim": "Microsoft가 SEC에 공식 공시 자료를 제출했습니다.",
        "summary": "SEC 공식 원문과 핵심 공시 메타데이터를 연결한 자료입니다.",
        "portfolioItemId": portfolio_id,
        "formType": "8-K",
        "materialChange": True,
        "confirm": False,
    }

    before = api_client.get("/api/v1/disclosures?limit=10")
    assert before.status_code == 200
    assert before.json()["total"] == 0

    preview_response = api_client.post(
        "/api/v1/disclosures/import-link",
        json=payload,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["confirmed"] is False
    assert preview["wouldCreate"] is True
    assert preview["classification"]["provider"] == "SEC_EDGAR"
    assert preview["classification"]["sourceGrade"] == "A"
    assert preview["classification"]["predictedVerificationStatus"] == "OFFICIAL_CONFIRMED"
    assert preview["duplicate"]["duplicate"] is False
    assert "utm_source" not in preview["normalizedUrl"]
    assert "#" not in preview["normalizedUrl"]
    assert api_client.get("/api/v1/disclosures?limit=10").json()["total"] == 0

    confirm_response = api_client.post(
        "/api/v1/disclosures/import-link",
        json={**payload, "confirm": True},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    confirmed = confirm_response.json()
    assert confirmed["confirmed"] is True
    assert confirmed["disclosure"]["provider"] == "SEC_EDGAR"
    assert confirmed["disclosure"]["sourceGrade"] == "A"
    assert confirmed["disclosure"]["verificationStatus"] == "OFFICIAL_CONFIRMED"
    assert confirmed["disclosure"]["relatedInstrument"]["canonicalSymbol"] == "MSFT"
    assert confirmed["disclosure"]["relatedPortfolioItems"][0]["id"] == portfolio_id

    events = api_client.get("/api/v1/information-events?limit=10")
    assert events.status_code == 200
    assert events.json()["total"] == 1
    assert events.json()["items"][0]["officialSourceCount"] == 1

    duplicate_preview = api_client.post(
        "/api/v1/disclosures/import-link",
        json=payload,
    )
    assert duplicate_preview.status_code == 200
    assert duplicate_preview.json()["wouldCreate"] is False
    assert duplicate_preview.json()["duplicate"]["duplicate"] is True

    duplicate_confirm = api_client.post(
        "/api/v1/disclosures/import-link",
        json={**payload, "confirm": True},
    )
    assert duplicate_confirm.status_code == 409

    invalid_domain = api_client.post(
        "/api/v1/disclosures/import-link",
        json={
            **payload,
            "officialUrl": "https://example.com/not-an-official-filing",
        },
    )
    assert invalid_domain.status_code == 422


def test_system_info_reports_phase_2a_defaults(api_client: TestClient) -> None:
    body = api_client.get("/api/v1/system/info").json()
    assert body["openDartStatus"] == "NOT_CONFIGURED"
    assert body["secStatus"] == "NOT_CONFIGURED"
    assert body["retentionCleanupEnabled"] is False
    assert body["automaticTradingEnabled"] is False
    assert body["aiAutomationEnabled"] is False


def test_retention_dry_run_does_not_delete(api_database: Database) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        document = TemporaryDocumentRecord(
            provider=ProviderName.OPENDART,
            provider_document_id="fixture",
            storage_reference="memory://fixture",
            expires_at=NOW - timedelta(hours=1),
        )
        session.add(document)
        session.flush()
        result = RetentionService(session, settings).run(now=NOW, dry_run=True)
        assert result.temporary_documents == 1
        assert session.get(TemporaryDocumentRecord, document.id) is not None


def test_retention_disabled_refuses_actual_cleanup(api_database: Database) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        result = RetentionService(session, settings).run(now=NOW, dry_run=False, confirm=True)
        assert result.status == "NOT_CONFIGURED"


def test_retention_confirm_removes_only_expired_temporary_metadata(
    api_database: Database,
) -> None:
    settings = Settings.from_env(
        {
            "DATABASE_URL": "sqlite+pysqlite://",
            "RETENTION_CLEANUP_ENABLED": "true",
        }
    )
    with api_database.session_scope() as session:
        expired = TemporaryDocumentRecord(
            provider=ProviderName.OPENDART,
            provider_document_id="expired",
            storage_reference="memory://expired",
            expires_at=NOW - timedelta(hours=1),
        )
        current = TemporaryDocumentRecord(
            provider=ProviderName.OPENDART,
            provider_document_id="current",
            storage_reference="memory://current",
            expires_at=NOW + timedelta(hours=1),
        )
        session.add_all([expired, current])
        session.flush()
        assert (
            RetentionService(session, settings).run(now=NOW, dry_run=False, confirm=True).status
            == "SUCCEEDED"
        )
        assert (
            session.scalar(
                select(TemporaryDocumentRecord).where(
                    TemporaryDocumentRecord.provider_document_id == "expired"
                )
            )
            is None
        )
        assert (
            session.scalar(
                select(TemporaryDocumentRecord).where(
                    TemporaryDocumentRecord.provider_document_id == "current"
                )
            )
            is not None
        )
