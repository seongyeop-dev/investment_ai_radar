from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.cli import _parser
from app.core.config import Settings
from app.core.time import FixedClock
from app.database import Database
from app.models.analysis import PortfolioImpactRecord
from app.models.contracts import VerificationStatus
from app.models.database import (
    AssetType,
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
    SourceGrade,
)
from app.models.disclosures import (
    DisclosureRecord,
    EvidenceItemRecord,
    InformationEventRecord,
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    MappingMatchMethod,
    MappingStatus,
    ProviderName,
    ProviderStatus,
)
from app.models.market_data import ProviderSyncStateRecord
from app.providers.common import ProviderDisclosure
from app.providers.opendart import OpenDartProvider
from app.providers.sec import SecEdgarProvider
from app.repositories.disclosures import DisclosureRepository
from app.services.analysis import AnalysisService
from app.services.disclosure_sync import OfficialDisclosureSyncService, _event_metadata
from app.services.disclosures import (
    DisclosureIngest,
    DisclosureService,
    canonical_official_url,
)

NOW = datetime(2026, 7, 26, 12, tzinfo=UTC)


def _settings(**values: str) -> Settings:
    environment = {
        "DATABASE_URL": "sqlite+pysqlite://",
        "OPENDART_ENABLED": "true",
        "OPENDART_API_KEY": "1234567890123456789012345678901234567890",
        "SEC_EDGAR_ENABLED": "true",
        "SEC_USER_AGENT_APP_NAME": "InvestmentAIRadar",
        "SEC_USER_AGENT_CONTACT": "fixture@example.invalid",
        "OFFICIAL_DISCLOSURE_SYNC_ENABLED": "true",
    }
    environment.update(values)
    return Settings.from_env(environment)


def _zip_company_codes() -> bytes:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list><corp_code>00126380</corp_code><corp_name>Samsung</corp_name><stock_code>005930</stock_code><modify_date>20260725</modify_date></list>
  <list><corp_code>00999999</corp_code><corp_name>Private</corp_name><stock_code></stock_code><modify_date>20260724</modify_date></list>
</result>"""
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("CORPCODE.xml", xml)
    return output.getvalue()


def _official_context(
    database: Database,
    *,
    mapping_status: MappingStatus = MappingStatus.VERIFIED,
) -> tuple[str, str]:
    with database.session_scope() as session:
        portfolio = PortfolioItemRecord(
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
        instrument = InstrumentRecord(
            canonical_symbol="ACME",
            display_name="Acme Official",
            exchange="NASDAQ",
            market="NASDAQ",
            country="US",
            currency=Currency.USD,
            asset_type=AssetType.EQUITY,
            verification_status=InstrumentVerificationStatus.VERIFIED,
            verification_source="SEC_EDGAR",
            verified_at=NOW,
        )
        session.add_all([portfolio, instrument])
        session.flush()
        session.add(
            InstrumentProviderMappingRecord(
                instrument_id=instrument.id,
                provider=ProviderName.SEC_EDGAR,
                provider_symbol="ACME",
                provider_company_id="0000000001:ACME",
                cik="0000000001",
                source_url="https://www.sec.gov/files/company_tickers_exchange.json",
                fetched_at=NOW,
                verified_at=NOW if mapping_status is MappingStatus.VERIFIED else None,
                official_name="Acme Official",
                mapping_status=mapping_status,
                match_method=MappingMatchMethod.EXACT_TICKER_EXCHANGE,
                confidence=100 if mapping_status is MappingStatus.VERIFIED else 0,
                last_checked_at=NOW,
            )
        )
        session.flush()
        return portfolio.id, instrument.id


def test_provider_configuration_contract_requires_real_credentials() -> None:
    empty = Settings.from_env({})
    assert empty.open_dart_configured is False
    assert empty.sec_configured is False
    assert empty.sec_user_agent == ""

    configured = _settings()
    assert configured.open_dart_configured is True
    assert configured.sec_configured is True
    assert configured.sec_user_agent == "InvestmentAIRadar/0.2 fixture@example.invalid"


def test_opendart_not_configured_makes_zero_requests() -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    provider = OpenDartProvider(
        Settings.from_env({}),
        client=httpx.Client(transport=httpx.MockTransport(unexpected)),
    )
    result = provider.fetch_company_codes()
    assert result.status is ProviderStatus.NOT_CONFIGURED
    assert result.request_count == 0


def test_opendart_company_zip_parsing_preserves_empty_stock_code() -> None:
    records = OpenDartProvider.parse_company_codes(_zip_company_codes(), NOW)
    assert records[0].corp_code == "00126380"
    assert records[0].stock_code == "005930"
    assert records[0].source_updated_at == datetime(2026, 7, 25, tzinfo=UTC)
    assert records[1].stock_code is None


def test_opendart_disclosure_pagination_is_bounded_and_metadata_only() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page_no"])
        return httpx.Response(
            200,
            json={
                "status": "000",
                "total_page": 2,
                "list": [
                    {
                        "rcept_no": f"2026072600000{page}",
                        "report_nm": "정정 주요사항보고서" if page == 2 else "주요사항보고서",
                        "corp_name": "Fixture",
                        "rcept_dt": "20260726",
                        "pblntf_ty": "B",
                        "rm": "정정" if page == 2 else "",
                    }
                ],
            },
            request=request,
        )

    provider = OpenDartProvider(
        _settings(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=FixedClock(NOW),
    )
    result = provider.fetch_disclosures(
        corp_code="00126380",
        published_from=NOW,
        published_to=NOW,
        limit=2,
    )
    assert result.status is ProviderStatus.READY
    assert result.request_count == 2
    assert len(result.disclosures) == 2
    assert result.disclosures[1].amendment is True
    assert not hasattr(result.disclosures[0], "body")
    assert len(requests) == 2


def test_sec_ticker_mapping_uses_identifiable_user_agent_and_normalizes_cik() -> None:
    seen_user_agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agents.append(request.headers["User-Agent"])
        return httpx.Response(
            200,
            json={
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[1234, "Acme", "acme", "Nasdaq"]],
            },
            request=request,
        )

    result = SecEdgarProvider(
        _settings(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=FixedClock(NOW),
        sleep=lambda _: None,
    ).fetch_company_tickers()
    assert result.status is ProviderStatus.READY
    assert result.request_count == 1
    assert result.companies[0].cik == "0000001234"
    assert result.companies[0].symbol == "ACME"
    assert result.companies[0].exchange == "NASDAQ"
    assert seen_user_agents == ["InvestmentAIRadar/0.2 fixture@example.invalid"]


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (404, ProviderStatus.FAILED),
        (429, ProviderStatus.RATE_LIMITED),
    ],
)
def test_sec_http_failures_are_explicit(status_code: int, expected: ProviderStatus) -> None:
    result = SecEdgarProvider(
        _settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status_code, request=request)
            )
        ),
        sleep=lambda _: None,
        max_attempts=1,
    ).fetch_company_tickers()
    assert result.status is expected
    assert result.request_count == 1
    assert result.error_code == f"HTTP_{status_code}"


def test_sec_retry_after_is_honored_before_success() -> None:
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[1, "Acme", "ACME", "Nasdaq"]],
            },
            request=request,
        )

    result = SecEdgarProvider(
        _settings(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=delays.append,
        monotonic=lambda: 1.0,
        max_attempts=2,
    ).fetch_company_tickers()
    assert result.status is ProviderStatus.READY
    assert result.request_count == 2
    assert 2.0 in delays


def test_official_disclosure_evidence_correction_and_direct_impact(
    api_database: Database,
) -> None:
    portfolio_id, instrument_id = _official_context(api_database)
    with api_database.session_scope() as session:
        service = DisclosureService(DisclosureRepository(session))
        base, event, created = service.ingest(
            DisclosureIngest(
                instrument_id=instrument_id,
                provider=ProviderName.SEC_EDGAR,
                provider_document_id="0000000001-26-000001",
                accession_number="0000000001-26-000001",
                form_type="8-K",
                title="Current report",
                company_name="Acme Official",
                official_url="https://www.sec.gov/Archives/base.htm",
                published_at=NOW,
                event_type="CURRENT_REPORT",
                claim="Acme Official | 8-K | Current report",
                summary=(
                    "Acme Official가 공식 공시 ‘Current report’을 제출했습니다. "
                    "투자 영향 방향은 별도 확인이 필요합니다."
                ),
                key_facts=[{"field": "form", "value": "8-K"}],
            ),
            now=NOW,
        )
        assert created is True
        correction, corrected_event, corrected_created = service.ingest(
            DisclosureIngest(
                instrument_id=instrument_id,
                provider=ProviderName.SEC_EDGAR,
                provider_document_id="0000000001-26-000001-A",
                accession_number="0000000001-26-000001-A",
                form_type="8-K/A",
                title="Current report amendment",
                company_name="Acme Official",
                official_url="https://www.sec.gov/Archives/amendment.htm",
                published_at=NOW,
                event_type="CURRENT_REPORT",
                claim="Acme Official | 8-K/A | Current report amendment",
                summary=(
                    "Acme Official가 공식 공시 ‘Current report amendment’을 "
                    "제출했습니다. 투자 영향 방향은 별도 확인이 필요합니다."
                ),
                correction_of_document_id=base.provider_document_id,
            ),
            now=NOW,
        )
        assert corrected_created is True
        assert correction.correction_of_id == base.id
        assert corrected_event.id == event.id
        assert corrected_event.verification_status is VerificationStatus.CORRECTED
        assert session.scalar(select(func.count()).select_from(InformationEventRecord)) == 1
        assert session.scalar(select(func.count()).select_from(EvidenceItemRecord)) == 2
        disclosures = list(session.scalars(select(DisclosureRecord)))
        assert all(item.source_grade is SourceGrade.A for item in disclosures)
        assert all(not hasattr(item, "body") for item in disclosures)

        assert AnalysisService(session).sync_direct_impacts() == 1
        impact = session.scalar(select(PortfolioImpactRecord))
        assert impact is not None
        assert impact.portfolio_item_id == portfolio_id
        assert impact.impact_direction == "UNCLEAR"
        assert impact.confidence == "LOW"
        review = AnalysisService(session).latest_review(portfolio_id)
        assert review.direction.value == "WAIT"
        assert review.generated_by.value == "RULE_BASED"
        assert review.human_decision_required is True
        portfolio = session.get(PortfolioItemRecord, portfolio_id)
        assert portfolio is not None and portfolio.instrument_id is None


def test_unverified_mapping_blocks_portfolio_impact(
    api_database: Database,
) -> None:
    portfolio_id, instrument_id = _official_context(
        api_database, mapping_status=MappingStatus.UNRESOLVED
    )
    with api_database.session_scope() as session:
        DisclosureService(DisclosureRepository(session)).ingest(
            DisclosureIngest(
                instrument_id=instrument_id,
                provider=ProviderName.SEC_EDGAR,
                provider_document_id="unverified",
                form_type="8-K",
                title="Current report",
                company_name="Acme",
                official_url="https://www.sec.gov/Archives/unverified.htm",
                published_at=NOW,
                event_type="CURRENT_REPORT",
                claim="Acme official filing",
                summary="Acme가 공식 공시를 제출했습니다.",
            ),
            now=NOW,
        )
        assert AnalysisService(session).sync_direct_impacts() == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(PortfolioImpactRecord)
                .where(PortfolioImpactRecord.portfolio_item_id == portfolio_id)
            )
            == 0
        )


def test_mapping_api_is_read_only_and_hides_sec_contact(
    api_database: Database, api_client: TestClient
) -> None:
    portfolio_id, _ = _official_context(api_database)
    response = api_client.get(f"/api/v1/portfolio/{portfolio_id}/mappings")
    assert response.status_code == 200
    assert response.json()[0]["mappingStatus"] == "VERIFIED"
    assert response.json()[0]["cik"] == "0000000001"
    assert "fixture@example.invalid" not in response.text
    openapi = api_client.get("/openapi.json").json()
    assert "/api/v1/portfolio/{portfolio_id}/mappings" in openapi["paths"]
    assert "post" not in openapi["paths"]["/api/v1/portfolio/{portfolio_id}/mappings"]
    portfolio = api_client.get(f"/api/v1/portfolio/{portfolio_id}")
    assert portfolio.status_code == 200
    assert portfolio.json()["instrumentVerificationStatus"] == "VERIFIED"
    assert portfolio.json()["officialDisclosureAvailability"] == "NOT_CONFIGURED"


def test_unconfigured_provider_status_overrides_stale_ready_state(
    api_database: Database, api_client: TestClient
) -> None:
    with api_database.session_scope() as session:
        session.add(
            ProviderSyncStateRecord(
                provider="OPENDART",
                capability="OFFICIAL_DISCLOSURE",
                configured=True,
                status="READY",
                last_success_at=NOW,
                request_count=3,
                success_count=3,
            )
        )
    response = api_client.get("/api/v1/providers/status")
    assert response.status_code == 200
    item = next(value for value in response.json()["items"] if value["provider"] == "OPENDART")
    assert item["configured"] is False
    assert item["status"] == "NOT_CONFIGURED"


def test_internal_cli_exposes_official_provider_commands() -> None:
    parser = _parser()
    commands = (
        "sync-opendart-company-codes",
        "sync-sec-company-tickers",
        "sync-instrument-mappings",
        "sync-opendart-disclosures",
        "sync-sec-disclosures",
        "process-disclosure-events",
        "refresh-decision-reviews",
        "official-disclosure-smoke",
    )
    for command in commands:
        arguments = [command, "--dry-run"]
        if command == "sync-instrument-mappings":
            arguments += ["--provider", "OPENDART"]
        if command == "official-disclosure-smoke":
            arguments += ["--provider", "SEC_EDGAR"]
        assert parser.parse_args(arguments).command == command


def test_form_metadata_does_not_claim_positive_or_negative_direction() -> None:
    disclosure = ProviderDisclosure(
        provider=ProviderName.SEC_EDGAR,
        provider_document_id="a",
        accession_number="a",
        receipt_number=None,
        form_type="8-K",
        report_type=None,
        title="Current report",
        company_name="Acme",
        official_url="https://www.sec.gov/a",
        published_at=NOW,
        source_updated_at=NOW,
        primary_document="a.htm",
    )
    event_type, display_title, summary, key_facts, denied, material = _event_metadata(
        disclosure
    )
    assert event_type == "CURRENT_REPORT"
    assert display_title == "Acme | 8-K 주요사항보고"
    assert "투자 영향 방향은 별도 확인이 필요합니다" in summary
    assert "긍정" not in summary and "부정" not in summary
    assert key_facts[0]["value"] == "SEC_EDGAR"
    assert denied is False
    assert material is True


@pytest.mark.parametrize(
    ("form_type", "title", "expected"),
    [
        ("10-Q", "10-Q", "INTEL CORP | 10-Q 분기보고서"),
        ("10-Q/A", "10-Q | 10-Q", "INTEL CORP | 10-Q/A 정정 분기보고서"),
        ("8-K", "FORM 8K", "INTEL CORP | 8-K 주요사항보고"),
    ],
)
def test_sec_event_title_removes_duplicate_form(
    form_type: str,
    title: str,
    expected: str,
) -> None:
    disclosure = ProviderDisclosure(
        provider=ProviderName.SEC_EDGAR,
        provider_document_id="a",
        accession_number="a",
        receipt_number=None,
        form_type=form_type,
        report_type=None,
        title=title,
        company_name="INTEL CORP",
        official_url="https://www.sec.gov/a",
        published_at=NOW,
        source_updated_at=NOW,
        primary_document="a.htm",
    )

    _, display_title, _, _, _, _ = _event_metadata(disclosure)

    assert display_title == expected


def test_ownership_disclosure_is_reference_not_core_event() -> None:
    disclosure = ProviderDisclosure(
        provider=ProviderName.OPENDART,
        provider_document_id="a",
        accession_number=None,
        receipt_number="a",
        form_type=None,
        report_type="공시",
        title="삼성전자 | 임원ㆍ주요주주특정증권등소유상황보고서",
        company_name="삼성전자",
        official_url="https://dart.fss.or.kr/a",
        published_at=NOW,
        source_updated_at=NOW,
        primary_document=None,
    )

    event_type, display_title, _, key_facts, _, material = _event_metadata(disclosure)

    assert event_type == "OFFICIAL_DISCLOSURE"
    assert display_title == "삼성전자 | 임원ㆍ주요주주특정증권등소유상황보고서"
    assert key_facts[-1] == {
        "field": "analysisImportance",
        "value": "REFERENCE",
    }
    assert material is False


def test_official_url_canonicalization_removes_tracking_and_sorts_query() -> None:
    assert (
        canonical_official_url("HTTPS://SEC.GOV/path/?b=2&utm_source=test&a=1#section")
        == "https://sec.gov/path?a=1&b=2"
    )


def test_existing_disclosures_are_reprocessed_without_changing_raw_metadata(
    api_database: Database,
) -> None:
    _, instrument_id = _official_context(api_database)
    with api_database.session_scope() as session:
        disclosure, event, _ = DisclosureService(DisclosureRepository(session)).ingest(
            DisclosureIngest(
                instrument_id=instrument_id,
                provider=ProviderName.SEC_EDGAR,
                provider_document_id="0000000001-26-000001",
                accession_number="0000000001-26-000001",
                receipt_number=None,
                form_type="10-Q",
                report_type=None,
                title="10-Q | 10-Q",
                company_name="INTEL CORP",
                official_url="https://www.sec.gov/Archives/test.htm",
                published_at=NOW,
                event_type="OFFICIAL_DISCLOSURE",
                claim="INTEL CORP | 10-Q | 10-Q",
                summary="legacy",
            ),
            now=NOW,
        )
        raw_before = (
            disclosure.title,
            disclosure.company_name,
            disclosure.official_url,
            disclosure.provider_document_id,
        )
        dry_run = OfficialDisclosureSyncService(session, _settings()).reprocess_existing(
            dry_run=True
        )
        assert dry_run["eventsChanged"] == 1
        assert event.normalized_claim == "INTEL CORP | 10-Q | 10-Q"

        applied = OfficialDisclosureSyncService(session, _settings()).reprocess_existing()
        assert applied["eventsChanged"] == 1
        assert event.normalized_claim == "INTEL CORP | 10-Q 분기보고서"
        assert disclosure.material_change is True
        assert (
            disclosure.title,
            disclosure.company_name,
            disclosure.official_url,
            disclosure.provider_document_id,
        ) == raw_before

        repeated = OfficialDisclosureSyncService(session, _settings()).reprocess_existing()
        assert repeated["eventsChanged"] == 0
        assert repeated["titlesChanged"] == 0
        assert repeated["classificationsChanged"] == 0
