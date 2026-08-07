from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.time import FixedClock
from app.database import Database
from app.models.database import (
    AssetType,
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
)
from app.models.disclosures import (
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    MappingStatus,
    ProviderName,
    ProviderStatus,
)
from app.models.market_data import QuoteSnapshotRecord
from app.providers.common import ProviderCompany, ProviderFetchResult
from app.providers.public_quotes import PublicQuote, PublicQuoteProvider
from app.providers.sec import SecEdgarProvider
from app.repositories.instruments import InstrumentRepository
from app.services.instruments import InstrumentService
from app.services.market_calendar import MarketCode, ScheduleStatus, default_market_calendar
from app.services.public_quotes import PublicQuoteService, quote_freshness
from app.services.retention import RetentionService
from app.services.risk_recommendation import RiskRecommendationService

NOW = datetime(2026, 7, 26, 9, 0, tzinfo=UTC)


def _crypto_portfolio(*, market: str = "UPBIT") -> PortfolioItemRecord:
    return PortfolioItemRecord(
        asset_type=AssetType.CRYPTO,
        symbol="BTC",
        name="Bitcoin",
        market=market,
        currency=Currency.KRW if market == "UPBIT" else Currency.USDT,
        holding_status=HoldingStatus.HOLDING,
        quantity=Decimal("0.125"),
        average_price=Decimal("100000000"),
        investment_horizon=InvestmentHorizon.LONG,
        strategy="",
    )


def _quote_client(provider: str, *, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, request=request)
        if provider == "UPBIT":
            return httpx.Response(
                200,
                json=[
                    {
                        "market": "KRW-BTC",
                        "trade_price": "123456789.123456789",
                        "timestamp": int(NOW.timestamp() * 1000),
                    }
                ],
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "mins": 5,
                "price": "98765.43210000",
                "closeTime": int(NOW.timestamp() * 1000),
            },
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_phase_4a_configuration_defaults_are_safe() -> None:
    settings = Settings.from_env({})
    assert settings.open_dart_configured is False
    assert settings.sec_configured is False
    assert settings.upbit_public_market_enabled is True
    assert settings.binance_public_market_enabled is True
    assert settings.market_calendar_enabled is False


@pytest.mark.parametrize(
    ("provider", "symbol", "currency", "price"),
    [
        ("UPBIT", "KRW-BTC", "KRW", Decimal("123456789.123456789")),
        ("BINANCE", "BTCUSDT", "USDT", Decimal("98765.43210000")),
    ],
)
def test_public_quote_parses_decimal_and_provider_timestamp(
    provider: str, symbol: str, currency: str, price: Decimal
) -> None:
    result = PublicQuoteProvider(
        provider,
        enabled=True,
        client=_quote_client(provider),
        clock=FixedClock(NOW + timedelta(seconds=1)),
    ).fetch_btc()
    assert result.status is ProviderStatus.READY
    assert result.request_count == 1
    assert result.quote is not None
    assert result.quote.provider_symbol == symbol
    assert result.quote.quote_currency == currency
    assert result.quote.price == price
    assert result.quote.provider_event_at == NOW


@pytest.mark.parametrize("provider", ["UPBIT", "BINANCE"])
def test_public_quote_rate_limit_is_explicit(provider: str) -> None:
    result = PublicQuoteProvider(
        provider,
        enabled=True,
        client=_quote_client(provider, status=429),
    ).fetch_btc()
    assert result.status is ProviderStatus.RATE_LIMITED
    assert result.error_code == "HTTP_429"


def test_public_quote_malformed_response_is_failed() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"unexpected": True}, request=request)
        )
    )
    result = PublicQuoteProvider("UPBIT", enabled=True, client=client).fetch_btc()
    assert result.status is ProviderStatus.FAILED
    assert result.quote is None


def test_public_quote_timeout_is_network_unavailable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture", request=request)

    client = httpx.Client(transport=httpx.MockTransport(timeout))
    result = PublicQuoteProvider("BINANCE", enabled=True, client=client).fetch_btc()
    assert result.status is ProviderStatus.NETWORK_UNAVAILABLE


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(30, "LIVE"), (300, "RECENT"), (1800, "DELAYED"), (7200, "STALE")],
)
def test_quote_freshness_uses_provider_time(seconds: int, expected: str) -> None:
    quote = PublicQuote(
        provider="UPBIT",
        provider_symbol="KRW-BTC",
        price=Decimal("1"),
        quote_currency="KRW",
        provider_event_at=NOW,
        fetched_at=NOW + timedelta(seconds=seconds),
    )
    assert quote_freshness(quote) == expected


def test_quote_sync_requires_confirmation(api_database: Database) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        output = PublicQuoteService(session, settings).sync(dry_run=False, confirm=False)
        assert output["status"] == "CONFIRM_REQUIRED"
        assert session.scalar(select(func.count()).select_from(QuoteSnapshotRecord)) == 0


def test_quote_sync_skips_unregistered_provider_without_request(
    api_database: Database,
) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network request: {request.url}")

    clients = {
        name: httpx.Client(transport=httpx.MockTransport(unexpected))
        for name in ("UPBIT", "BINANCE")
    }
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        output = PublicQuoteService(session, settings).sync(
            dry_run=True, confirm=False, clients=clients
        )
        assert output["requestCount"] == 0
        assert output["notApplicable"] == 2


def test_upbit_sync_creates_verified_metadata_without_mutating_portfolio_link(
    api_database: Database,
) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        portfolio = _crypto_portfolio()
        session.add(portfolio)
        session.flush()
        original_id = portfolio.id
        output = PublicQuoteService(session, settings).sync(
            provider="UPBIT",
            dry_run=False,
            confirm=True,
            clients={"UPBIT": _quote_client("UPBIT")},
        )
        assert output["created"] == 1
        assert session.get(PortfolioItemRecord, original_id).instrument_id is None
        mapping = session.scalar(select(InstrumentProviderMappingRecord))
        assert mapping is not None
        assert mapping.mapping_status is MappingStatus.VERIFIED
        assert mapping.provider_symbol == "KRW-BTC"


def test_quote_snapshot_fingerprint_suppresses_duplicates(
    api_database: Database,
) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        session.add(_crypto_portfolio())
        session.flush()
        service = PublicQuoteService(session, settings)
        for _ in range(2):
            result = service.sync(
                provider="UPBIT",
                dry_run=False,
                confirm=True,
                clients={"UPBIT": _quote_client("UPBIT")},
            )
        assert result["duplicates"] == 1
        assert session.scalar(select(func.count()).select_from(QuoteSnapshotRecord)) == 1


def test_instrument_mapping_exact_stock_code_only(api_database: Database) -> None:
    company = ProviderCompany(
        provider=ProviderName.OPENDART,
        provider_company_id="00126380",
        symbol="005930",
        company_name="Samsung Electronics",
        exchange="KRX",
        cik=None,
        corp_code="00126380",
        stock_code="005930",
        source_url="https://opendart.fss.or.kr/",
        source_updated_at=NOW,
        fetched_at=NOW,
    )
    with api_database.session_scope() as session:
        session.add(
            PortfolioItemRecord(
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
        )
        session.flush()
        output = InstrumentService(InstrumentRepository(session)).sync_companies(
            ProviderFetchResult(
                provider=ProviderName.OPENDART,
                status=ProviderStatus.READY,
                companies=(company,),
            )
        )
        assert output["verified"] == 1
        mapping = session.scalar(select(InstrumentProviderMappingRecord))
        assert mapping is not None
        assert mapping.match_method.value == "EXACT_STOCK_CODE"


def test_sec_submissions_reads_bounded_recent_file() -> None:
    root = {
        "name": "Fixture Corp",
        "filings": {
            "recent": {
                "accessionNumber": [],
                "filingDate": [],
                "acceptanceDateTime": [],
                "reportDate": [],
                "form": [],
                "primaryDocument": [],
                "primaryDocDescription": [],
            },
            "files": [{"name": "CIK0000000001-submissions-001.json"}],
        },
    }
    history = {
        "accessionNumber": ["0000000001-26-000001"],
        "filingDate": ["2026-07-25"],
        "acceptanceDateTime": ["2026-07-25T12:00:00Z"],
        "reportDate": ["2026-06-30"],
        "form": ["10-Q"],
        "primaryDocument": ["fixture.htm"],
        "primaryDocDescription": ["Quarterly report"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = history if request.url.path.endswith("-001.json") else root
        return httpx.Response(200, json=body, request=request)

    provider = SecEdgarProvider(
        Settings.from_env(
            {
                "SEC_USER_AGENT": "fixture test@example.invalid",
                "SEC_EDGAR_ENABLED": "true",
            }
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )
    result = provider.fetch_submissions("1", limit=1)
    assert result.status is ProviderStatus.READY
    assert result.disclosures[0].accession_number == "0000000001-26-000001"


def test_instrument_mapping_ambiguous_official_candidates_is_conflicting(
    api_database: Database,
) -> None:
    companies = tuple(
        ProviderCompany(
            provider=ProviderName.SEC_EDGAR,
            provider_company_id=f"000000000{index}",
            symbol="ACME",
            company_name=f"Acme {index}",
            exchange="NASDAQ",
            cik=f"000000000{index}",
            corp_code=None,
            stock_code=None,
            source_url="https://www.sec.gov/",
            source_updated_at=NOW,
            fetched_at=NOW,
        )
        for index in (1, 2)
    )
    with api_database.session_scope() as session:
        session.add(
            PortfolioItemRecord(
                asset_type=AssetType.EQUITY,
                symbol="ACME",
                name="Acme",
                market="NASDAQ",
                currency=Currency.USD,
                holding_status=HoldingStatus.WATCHLIST,
                quantity=Decimal("0"),
                average_price=None,
                investment_horizon=InvestmentHorizon.UNSET,
                strategy="",
            )
        )
        session.flush()
        output = InstrumentService(InstrumentRepository(session)).sync_companies(
            ProviderFetchResult(
                provider=ProviderName.SEC_EDGAR,
                status=ProviderStatus.READY,
                companies=companies,
            )
        )
        assert output["conflicting"] == 1
        mapping = session.scalar(select(InstrumentProviderMappingRecord))
        assert mapping is not None
        assert mapping.mapping_status is MappingStatus.CONFLICTING
        assert mapping.verified_at is None


def test_provider_and_quote_read_apis_hide_secrets(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        portfolio = _crypto_portfolio()
        session.add(portfolio)
        session.flush()
        portfolio_id = portfolio.id
    status = api_client.get("/api/v1/providers/status")
    quote = api_client.get(f"/api/v1/portfolio/{portfolio_id}/quote")
    assert status.status_code == 200
    assert quote.status_code == 200
    assert quote.json()["quoteStatus"] == "NOT_COLLECTED"
    text = status.text + quote.text
    assert "apiKey" not in text
    assert "userAgent" not in text
    assert "databasePath" not in text


def test_provider_routes_are_read_only(api_app: object) -> None:
    schema = api_app.openapi()  # type: ignore[attr-defined]
    paths = schema["paths"]
    assert "post" not in paths["/api/v1/providers"]
    assert "/api/v1/orders" not in paths
    assert not any("sync" in path and "post" in methods for path, methods in paths.items())


def test_market_calendar_covers_weekend_dst_and_early_close() -> None:
    adapter = default_market_calendar(enabled=True)
    assert adapter.configured
    weekend = adapter.session(MarketCode.KRX, date(2026, 7, 26))
    krx_holiday = adapter.session(MarketCode.KRX, date(2026, 10, 5))
    us_holiday = adapter.session(MarketCode.NASDAQ, date(2026, 12, 25))
    summer = adapter.session(MarketCode.NASDAQ, date(2026, 7, 27))
    early = adapter.session(MarketCode.NASDAQ, date(2026, 11, 27))
    assert weekend.schedule_status is ScheduleStatus.CLOSED
    assert krx_holiday.schedule_status is ScheduleStatus.CLOSED
    assert us_holiday.schedule_status is ScheduleStatus.CLOSED
    assert summer.market_timezone == "America/New_York"
    assert summer.open_at is not None and summer.open_at.hour == 13
    assert early.early_close is True


def test_retention_dry_run_counts_expired_quote(api_database: Database) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        instrument = InstrumentRecord(
            canonical_symbol="BTC",
            display_name="Bitcoin",
            exchange="UPBIT",
            market="UPBIT",
            country="XX",
            currency=Currency.KRW,
            asset_type=AssetType.CRYPTO,
        )
        session.add(instrument)
        session.flush()
        session.add(
            QuoteSnapshotRecord(
                instrument_id=instrument.id,
                provider="UPBIT",
                provider_symbol="KRW-BTC",
                price=Decimal("1"),
                quote_currency="KRW",
                provider_event_at=NOW,
                fetched_at=NOW,
                freshness_status="LIVE",
                source_status="READY",
                sequence=1,
                fingerprint="a" * 64,
                expires_at=NOW - timedelta(seconds=1),
            )
        )
        session.flush()
        result = RetentionService(session, settings).run(now=NOW, dry_run=True)
        assert result.quote_snapshots == 1
        assert session.scalar(select(func.count()).select_from(QuoteSnapshotRecord)) == 1


def test_risk_recommendation_ignores_preserved_crypto_quote(
    api_database: Database,
) -> None:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    with api_database.session_scope() as session:
        session.add(_crypto_portfolio())
        session.flush()
        PublicQuoteService(session, settings).sync(
            provider="UPBIT",
            dry_run=False,
            confirm=True,
            clients={"UPBIT": _quote_client("UPBIT")},
        )
        recommendation = RiskRecommendationService(session, clock=FixedClock(NOW)).recommend()
        coverage = recommendation.data_coverage
        assert coverage.market_price_provider_configured is False
        assert coverage.partial_market_price_coverage is False
        assert coverage.quoted_crypto_position_count == 0
        assert session.scalar(select(func.count()).select_from(QuoteSnapshotRecord)) == 1
        assert recommendation.confidence.value != "HIGH"
        assert "MARKET_PRICE_PROVIDER" in recommendation.missing_inputs
