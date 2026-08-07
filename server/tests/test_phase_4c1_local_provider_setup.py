from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest
from sqlalchemy import func, select

from app.cli import _parser, main
from app.core.config import Settings
from app.core.local_env import (
    load_local_environment,
    parse_local_env,
    valid_contact_email,
    valid_opendart_key,
)
from app.database import Database
from app.models.database import (
    AssetType,
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
)
from app.models.disclosures import (
    DisclosureRecord,
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    MappingMatchMethod,
    MappingStatus,
    ProviderName,
    ProviderStatus,
)
from app.providers.common import (
    ProviderCompany,
    ProviderDisclosure,
    ProviderFetchResult,
    ProviderResponseDiagnostics,
)
from app.providers.opendart import OpenDartProvider
from app.providers.sec import SEC_MIN_REQUEST_INTERVAL_SECONDS, SecEdgarProvider
from app.repositories.instruments import InstrumentRepository
from app.services.disclosure_sync import OfficialDisclosureSyncService
from app.services.instruments import InstrumentService

NOW = datetime(2026, 7, 26, 12, tzinfo=UTC)
DART_KEY = "1234567890123456789012345678901234567890"
SEC_CONTACT = "fixture@example.invalid"


def _company_code_zip(
    *,
    name: str = "CORPCODE.xml",
    content_type: str | None = "application/zip",
) -> tuple[bytes, dict[str, str]]:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            name,
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<result><list><corp_code>00126380</corp_code>"
                "<corp_name>Samsung</corp_name><stock_code>005930</stock_code>"
                "<modify_date>20260725</modify_date></list></result>"
            ),
        )
    headers = {"Content-Type": content_type} if content_type else {}
    return output.getvalue(), headers


def _run_provider_setup(
    tmp_path: Path,
    answers: list[str],
    *,
    existing_content: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("Windows PowerShell is not available")

    project_root = Path(__file__).resolve().parents[2]
    test_root = tmp_path / "provider-setup"
    scripts_dir = test_root / "scripts"
    scripts_dir.mkdir(parents=True)
    config_script = scripts_dir / "configure-official-providers.ps1"
    config_script.write_bytes(
        (project_root / "scripts" / "configure-official-providers.ps1").read_bytes()
    )
    target = test_root / ".env.local"
    if existing_content is not None:
        target.write_text(existing_content, encoding="utf-8")

    answer_literals = ", ".join(json.dumps(answer) for answer in answers)
    wrapper = tmp_path / "invoke-provider-setup.ps1"
    wrapper.write_text(
        (
            "$ErrorActionPreference = 'Stop'\n"
            "$global:providerTestAnswers = [Collections.Generic.Queue[string]]::new()\n"
            f"@({answer_literals}) | ForEach-Object {{\n"
            "    $global:providerTestAnswers.Enqueue($_)\n"
            "}\n"
            "function Read-Host {\n"
            "    param([string]$Prompt, [switch]$AsSecureString)\n"
            "    [Console]::WriteLine('PROMPT:' + $Prompt)\n"
            "    if ($global:providerTestAnswers.Count -eq 0) { throw 'Missing test answer' }\n"
            "    $answer = $global:providerTestAnswers.Dequeue()\n"
            "    if ($AsSecureString) {\n"
            "        return ConvertTo-SecureString $answer -AsPlainText -Force\n"
            "    }\n"
            "    return $answer\n"
            "}\n"
            f"& '{config_script}'\n"
        ),
        encoding="utf-8-sig",
    )
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
        ],
        cwd=test_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result, target


def _official_settings(**values: str) -> Settings:
    environment = {
        "OPENDART_ENABLED": "true",
        "OPENDART_API_KEY": DART_KEY,
        "SEC_EDGAR_ENABLED": "true",
        "SEC_USER_AGENT_APP_NAME": "InvestmentAIRadar",
        "SEC_USER_AGENT_CONTACT": "fixture@example.invalid",
        "OFFICIAL_DISCLOSURE_SYNC_ENABLED": "true",
    }
    environment.update(values)
    return Settings.from_env(environment)


def test_local_env_parser_preserves_values_and_process_overrides(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".env.local").write_text(
        "# local only\n"
        "OPENDART_ENABLED=true\n"
        f"OPENDART_API_KEY={DART_KEY}\n"
        "UNRELATED_VALUE=preserved\n",
        encoding="utf-8",
    )
    loaded = load_local_environment(
        {"OPENDART_ENABLED": "false"},
        project_root=root,
    )
    assert loaded["OPENDART_ENABLED"] == "false"
    assert loaded["OPENDART_API_KEY"] == DART_KEY
    assert loaded["UNRELATED_VALUE"] == "preserved"
    assert parse_local_env("export SEC_EDGAR_ENABLED=true\n") == {"SEC_EDGAR_ENABLED": "true"}


def test_secret_formats_are_validated_without_echoing_values() -> None:
    assert valid_opendart_key(DART_KEY)
    assert not valid_opendart_key("short")
    assert valid_contact_email("fixture@example.invalid")
    assert not valid_contact_email("not-an-email")
    invalid = _official_settings(OPENDART_API_KEY="short", SEC_USER_AGENT_CONTACT="bad")
    assert invalid.open_dart_configured is False
    assert invalid.sec_configured is False
    assert invalid.sec_user_agent == ""
    quoted = _official_settings(
        OPENDART_API_KEY=f'  "{DART_KEY}"  ',
        SEC_USER_AGENT_CONTACT=f"  '{SEC_CONTACT}'  ",
    )
    assert quoted.opendart_api_key == DART_KEY
    assert quoted.open_dart_configured is True
    assert quoted.sec_configured is True


def test_secret_files_are_ignored_and_configuration_script_masks() -> None:
    root = Path(__file__).resolve().parents[2]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    ignore = (root / ".ignore").read_text(encoding="utf-8-sig")
    script = (root / "scripts" / "configure-official-providers.ps1").read_text(encoding="utf-8")
    for pattern in (
        ".env.local",
        ".env.*.local",
        "server/.env",
        "server/.env.local",
    ):
        assert pattern in gitignore
        assert pattern in ignore
    assert "Read-Host $Prompt -AsSecureString" in script
    assert "ZeroFreeBSTR" in script
    assert '"*" * 32' in script
    assert "SEC Contact:" in script
    assert "OPENDART_API_KEY=<" not in script


def test_official_provider_scripts_use_utf8_bom_and_parse_in_winps() -> None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("Windows PowerShell is not available")

    root = Path(__file__).resolve().parents[2]
    scripts = (
        "configure-official-providers.ps1",
        "provider-status.ps1",
        "official-provider-smoke.ps1",
        "sync-instruments.ps1",
        "sync-disclosures.ps1",
        "process-disclosure-events.ps1",
        "refresh-decision-reviews.ps1",
    )
    for name in scripts:
        path = root / "scripts" / name
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")
        command = (
            "$tokens=$null;$errors=$null;"
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{path}',[ref]$tokens,[ref]$errors)|Out-Null;"
            "if($errors.Count -ne 0){exit 1}"
        )
        result = subprocess.run(
            [powershell, "-NoProfile", "-Command", command],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, name


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (
            ["Y", DART_KEY, "N", "Y", "Y"],
            {
                "OPENDART_ENABLED": "true",
                "SEC_EDGAR_ENABLED": "false",
                "OFFICIAL_DISCLOSURE_SYNC_ENABLED": "true",
            },
        ),
        (
            ["N", "Y", SEC_CONTACT, "Y", "Y"],
            {
                "OPENDART_ENABLED": "false",
                "SEC_EDGAR_ENABLED": "true",
                "OFFICIAL_DISCLOSURE_SYNC_ENABLED": "true",
            },
        ),
        (
            ["Y", DART_KEY, "Y", SEC_CONTACT, "Y", "Y"],
            {
                "OPENDART_ENABLED": "true",
                "SEC_EDGAR_ENABLED": "true",
                "OFFICIAL_DISCLOSURE_SYNC_ENABLED": "true",
            },
        ),
        (
            ["N", "N", "N", "Y"],
            {
                "OPENDART_ENABLED": "false",
                "SEC_EDGAR_ENABLED": "false",
                "OFFICIAL_DISCLOSURE_SYNC_ENABLED": "false",
            },
        ),
    ],
)
def test_provider_configuration_modes_and_prompt_order(
    tmp_path: Path,
    answers: list[str],
    expected: dict[str, str],
) -> None:
    result, target = _run_provider_setup(tmp_path, answers)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert target.exists()
    values = parse_local_env(target.read_text(encoding="utf-8"))
    assert {name: values[name] for name in expected} == expected
    assert output.index("OpenDART") < output.index("SEC EDGAR")
    assert output.index("SEC EDGAR") < output.index("Official sync:")
    assert output.index("Official sync:") < output.index("[CONFIGURED]")
    assert DART_KEY not in output
    assert SEC_CONTACT not in output
    if expected["SEC_EDGAR_ENABLED"] == "false":
        assert "SEC User-Agent" not in output


def test_provider_configuration_retries_invalid_secret_inputs(
    tmp_path: Path,
) -> None:
    answers = [
        "Y",
        "short",
        "R",
        DART_KEY,
        "Y",
        "",
        "R",
        "bad<email@example.invalid>",
        "R",
        SEC_CONTACT,
        "Y",
        "Y",
    ]
    result, target = _run_provider_setup(tmp_path, answers)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert target.exists()
    values = parse_local_env(target.read_text(encoding="utf-8"))
    assert values["OPENDART_API_KEY"] == DART_KEY
    assert values["SEC_USER_AGENT_CONTACT"] == SEC_CONTACT
    for secret in ("short", DART_KEY, "bad<email@example.invalid>", SEC_CONTACT):
        assert secret not in output
    assert output.count("PROMPT:OpenDART 인증키") == 2
    assert output.count("PROMPT:SEC User-Agent") == 3


@pytest.mark.parametrize(
    "answers",
    [
        ["Y", "short", "C"],
        ["N", "Y", "", "C"],
        ["N", "N", "N", "N"],
    ],
)
def test_provider_configuration_cancel_does_not_create_file(
    tmp_path: Path,
    answers: list[str],
) -> None:
    result, target = _run_provider_setup(tmp_path, answers)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert not target.exists()
    assert "[CANCELLED]" in output


def test_provider_configuration_cancel_preserves_existing_file(
    tmp_path: Path,
) -> None:
    existing = "PRESERVE_ME=unchanged\n"
    result, target = _run_provider_setup(
        tmp_path,
        ["N", "Y", "invalid", "C"],
        existing_content=existing,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert target.read_text(encoding="utf-8") == existing
    assert "invalid" not in output
    assert not list(target.parent.glob(".official-provider-config-*.tmp"))


def test_provider_configuration_atomically_updates_existing_file(
    tmp_path: Path,
) -> None:
    existing = "PRESERVE_ME=unchanged\nOPENDART_ENABLED=true\n"
    result, target = _run_provider_setup(
        tmp_path,
        ["N", "N", "N", "Y"],
        existing_content=existing,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    values = parse_local_env(target.read_text(encoding="utf-8"))
    assert values["PRESERVE_ME"] == "unchanged"
    assert values["OPENDART_ENABLED"] == "false"
    assert "[CONFIGURED]" in output
    assert not list(target.parent.glob(".official-provider-config-*.tmp"))


@pytest.mark.parametrize(
    ("code", "status", "error"),
    [
        ("010", ProviderStatus.FAILED, "INVALID_API_KEY"),
        ("011", ProviderStatus.FAILED, "API_KEY_DISABLED"),
        ("012", ProviderStatus.FAILED, "API_KEY_ACCESS_DENIED"),
        ("901", ProviderStatus.FAILED, "API_KEY_DISABLED"),
        ("020", ProviderStatus.RATE_LIMITED, "RATE_LIMITED"),
        ("100", ProviderStatus.FAILED, "MISSING_REQUIRED_PARAMETER"),
        ("800", ProviderStatus.FAILED, "PROVIDER_TEMPORARY_ERROR"),
    ],
)
def test_opendart_official_error_codes_are_explicit(
    code: str, status: ProviderStatus, error: str
) -> None:
    provider = OpenDartProvider(
        _official_settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"status": code, "message": "redacted"},
                    request=request,
                )
            )
        ),
    )
    result = provider.fetch_company_codes()
    assert result.status is status
    assert result.error_code == error
    assert result.request_count == 1
    assert result.diagnostics is not None
    assert result.diagnostics.payload_kind == "JSON_ERROR"
    assert result.diagnostics.official_status_code == code


def test_opendart_rejects_non_zip_company_payload() -> None:
    provider = OpenDartProvider(
        _official_settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    content=b"not a ZIP",
                    headers={"Content-Type": "text/plain"},
                    request=request,
                )
            )
        ),
    )
    result = provider.fetch_company_codes()
    assert result.status is ProviderStatus.FAILED
    assert result.error_code == "INVALID_ZIP_RESPONSE"
    assert result.request_count == 1
    assert result.diagnostics is not None
    assert result.diagnostics.payload_kind == "UNKNOWN"
    assert result.diagnostics.http_status == 200
    assert result.diagnostics.content_type == "text/plain"
    assert result.diagnostics.zip_signature_valid is False


def test_opendart_xml_auth_error_is_distinguished() -> None:
    provider = OpenDartProvider(
        _official_settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    content=(
                        b"<result><status>010</status><message>redacted</message></result>"
                    ),
                    headers={"Content-Type": "application/xml"},
                    request=request,
                )
            )
        ),
    )
    result = provider.fetch_company_codes()
    assert result.status is ProviderStatus.FAILED
    assert result.error_code == "INVALID_API_KEY"
    assert result.request_count == 1
    assert result.diagnostics is not None
    assert result.diagnostics.payload_kind == "XML_ERROR"
    assert result.diagnostics.official_status_code == "010"
    assert result.diagnostics.official_message == "redacted"


@pytest.mark.parametrize(
    "content_type",
    [
        "application/zip",
        "application/octet-stream",
        "application/x-zip-compressed",
        "application/x-msdownload",
        None,
        "text/plain",
    ],
)
def test_opendart_accepts_valid_zip_by_signature(
    content_type: str | None,
) -> None:
    content, headers = _company_code_zip(content_type=content_type)
    provider = OpenDartProvider(
        _official_settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    content=content,
                    headers=headers,
                    request=request,
                )
            )
        ),
    )

    result = provider.fetch_company_codes()

    assert result.status is ProviderStatus.READY
    assert len(result.companies) == 1
    assert result.diagnostics is not None
    assert result.diagnostics.payload_kind == "ZIP"
    assert result.diagnostics.zip_signature_valid is True


def test_opendart_classifies_html_without_returning_body() -> None:
    provider = OpenDartProvider(
        _official_settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    403,
                    content=b"<html><body>blocked</body></html>",
                    headers={"Content-Type": "text/html"},
                    request=request,
                )
            )
        ),
    )

    result = provider.fetch_company_codes()

    assert result.error_code == "UNEXPECTED_HTML_RESPONSE"
    assert result.diagnostics is not None
    assert result.diagnostics.payload_kind == "HTML"
    assert result.diagnostics.official_message is None


def test_opendart_redacts_secret_from_official_message() -> None:
    provider = OpenDartProvider(
        _official_settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"status": "010", "message": f"invalid {DART_KEY}"},
                    request=request,
                )
            )
        ),
    )

    result = provider.fetch_company_codes()

    assert result.diagnostics is not None
    assert result.diagnostics.official_message == "invalid [REDACTED]"
    assert DART_KEY not in result.diagnostics.official_message


@pytest.mark.parametrize("name", ["../CORPCODE.xml", "other.xml"])
def test_opendart_rejects_unsafe_or_missing_corpcode_entry(name: str) -> None:
    content, headers = _company_code_zip(name=name)
    provider = OpenDartProvider(
        _official_settings(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    content=content,
                    headers=headers,
                    request=request,
                )
            )
        ),
    )

    result = provider.fetch_company_codes()

    assert result.status is ProviderStatus.FAILED
    assert result.error_code == "INVALID_ZIP_RESPONSE"
    assert result.diagnostics is not None
    assert result.diagnostics.zip_signature_valid is True


def test_opendart_skips_invalid_optional_company_fields() -> None:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "CORPCODE.xml",
            (
                "<result>"
                "<list><corp_code>bad</corp_code><corp_name></corp_name></list>"
                "<list><corp_code>00126380</corp_code>"
                "<corp_name>Samsung</corp_name><stock_code>not-six-digits</stock_code>"
                "<modify_date>not-a-date</modify_date></list>"
                "</result>"
            ),
        )

    records = OpenDartProvider.parse_company_codes(output.getvalue(), NOW)

    assert len(records) == 1
    assert records[0].corp_code == "00126380"
    assert records[0].stock_code is None
    assert records[0].source_updated_at is None


def test_official_smoke_is_read_only_and_outputs_safe_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _official_settings()
    diagnostics = ProviderResponseDiagnostics(
        http_status=200,
        content_type="application/zip",
        content_length=100,
        content_disposition_present=True,
        payload_kind="ZIP",
        zip_signature_valid=True,
        redirect_count=0,
    )
    monkeypatch.setattr(
        "app.cli.Settings.from_env",
        lambda environment=None: settings,
    )
    monkeypatch.setattr(
        "app.cli.OpenDartProvider.fetch_company_codes",
        lambda provider: ProviderFetchResult(
            provider=ProviderName.OPENDART,
            status=ProviderStatus.READY,
            companies=(
                ProviderCompany(
                    provider=ProviderName.OPENDART,
                    provider_company_id="00126380",
                    symbol="005930",
                    company_name="Samsung",
                    exchange=None,
                    cik=None,
                    corp_code="00126380",
                    stock_code="005930",
                    source_url="https://opendart.fss.or.kr/api/corpCode.xml",
                    source_updated_at=NOW,
                    fetched_at=NOW,
                ),
            ),
            request_count=1,
            diagnostics=diagnostics,
        ),
    )
    monkeypatch.setattr(
        "app.cli.Database.from_settings",
        lambda settings: pytest.fail("smoke must not open the database"),
    )

    exit_code = main(["official-disclosure-smoke", "--provider", "OPENDART", "--confirm"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["status"] == "READY"
    assert payload["payloadKind"] == "ZIP"
    assert payload["zipSignatureValid"] is True
    assert payload["secretsExposed"] is False
    assert DART_KEY not in output
    assert SEC_CONTACT not in output


def test_sec_default_rate_is_one_request_per_second() -> None:
    delays: list[float] = []
    provider = SecEdgarProvider(
        _official_settings(),
        sleep=delays.append,
        monotonic=lambda: 0.0,
    )
    provider._rate_limit()
    provider._rate_limit()
    assert SEC_MIN_REQUEST_INTERVAL_SECONDS == 1.0
    assert delays == [1.0]


def test_mapping_dry_run_is_prioritized_bounded_and_read_only(
    api_database: Database,
) -> None:
    rows = (
        ("000001", HoldingStatus.WATCHLIST, Decimal("0")),
        ("000002", HoldingStatus.HOLDING, Decimal("1")),
        ("000003", HoldingStatus.REENTRY_WATCH, Decimal("0")),
        ("000004", HoldingStatus.HOLDING, Decimal("1")),
        ("000005", HoldingStatus.SOLD, Decimal("0")),
    )
    with api_database.session_scope() as session:
        for symbol, status, quantity in rows:
            session.add(
                PortfolioItemRecord(
                    asset_type=AssetType.EQUITY,
                    symbol=symbol,
                    name=f"Fixture {symbol}",
                    market="KRX",
                    currency=Currency.KRW,
                    holding_status=status,
                    quantity=quantity,
                    average_price=Decimal("100") if quantity else None,
                    investment_horizon=InvestmentHorizon.UNSET,
                    strategy="",
                )
            )
        session.flush()
        companies = tuple(
            ProviderCompany(
                provider=ProviderName.OPENDART,
                provider_company_id=f"{index:08d}",
                symbol=symbol,
                company_name=f"Official {symbol}",
                exchange=None,
                cik=None,
                corp_code=f"{index:08d}",
                stock_code=symbol,
                source_url="https://opendart.fss.or.kr/api/corpCode.xml",
                source_updated_at=NOW,
                fetched_at=NOW,
            )
            for index, (symbol, _, _) in enumerate(rows, 1)
        )
        result = InstrumentService(InstrumentRepository(session)).sync_companies(
            ProviderFetchResult(
                provider=ProviderName.OPENDART,
                status=ProviderStatus.READY,
                companies=companies,
                request_count=1,
            ),
            dry_run=True,
            limit=100,
        )
        assert result["portfolioCandidates"] == 4
        assert result["verified"] == 4
        assert len(result["candidateDetails"]) == 4
        assert session.scalar(select(func.count()).select_from(InstrumentRecord)) == 0
        assert (
            session.scalar(select(func.count()).select_from(InstrumentProviderMappingRecord))
            == 0
        )


def test_official_cli_defaults_are_bounded() -> None:
    parser = _parser()
    assert (
        parser.parse_args(["sync-instruments", "--provider", "OPENDART", "--dry-run"]).limit
        == 3
    )
    assert (
        parser.parse_args(["sync-disclosures", "--provider", "SEC_EDGAR", "--dry-run"]).limit
        == 30
    )


def test_first_disclosure_sync_is_three_instruments_ten_each_and_thirty_days(
    api_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with api_database.session_scope() as session:
        for index in range(4):
            symbol = f"ACM{index}"
            cik = f"{index + 1:010d}"
            portfolio = PortfolioItemRecord(
                asset_type=AssetType.EQUITY,
                symbol=symbol,
                name=f"Acme {index}",
                market="NASDAQ",
                currency=Currency.USD,
                holding_status=HoldingStatus.HOLDING,
                quantity=Decimal("1"),
                average_price=Decimal("10"),
                investment_horizon=InvestmentHorizon.UNSET,
                strategy="",
            )
            instrument = InstrumentRecord(
                canonical_symbol=symbol,
                display_name=f"Acme Official {index}",
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
                    provider_symbol=symbol,
                    provider_company_id=f"{cik}:{symbol}",
                    cik=cik,
                    source_url=("https://www.sec.gov/files/company_tickers_exchange.json"),
                    fetched_at=NOW,
                    verified_at=NOW,
                    official_name=f"Acme Official {index}",
                    mapping_status=MappingStatus.VERIFIED,
                    match_method=MappingMatchMethod.EXACT_TICKER_EXCHANGE,
                    confidence=100,
                    last_checked_at=NOW,
                )
            )

        class FakeSecProvider:
            calls: list[int] = []

            def __init__(self, settings: Settings) -> None:
                del settings

            def fetch_submissions(self, cik: str, *, limit: int) -> ProviderFetchResult:
                self.calls.append(limit)
                disclosures = tuple(
                    ProviderDisclosure(
                        provider=ProviderName.SEC_EDGAR,
                        provider_document_id=f"{cik}-{item}",
                        accession_number=f"{cik}-{item}",
                        receipt_number=None,
                        form_type="8-K",
                        report_type=None,
                        title="Current report",
                        company_name="Acme Official",
                        official_url=f"https://www.sec.gov/Archives/{cik}/{item}",
                        published_at=(
                            NOW - timedelta(days=31)
                            if item == 0
                            else NOW - timedelta(days=item)
                        ),
                        source_updated_at=NOW,
                        primary_document=f"{item}.htm",
                    )
                    for item in range(limit)
                )
                return ProviderFetchResult(
                    provider=ProviderName.SEC_EDGAR,
                    status=ProviderStatus.READY,
                    disclosures=disclosures,
                    request_count=1,
                )

        monkeypatch.setattr(
            "app.services.disclosure_sync.SecEdgarProvider",
            FakeSecProvider,
        )
        output = OfficialDisclosureSyncService(session, _official_settings()).sync(
            ProviderName.SEC_EDGAR,
            limit=100,
            dry_run=True,
            now=NOW,
        )
        assert FakeSecProvider.calls == [10, 10, 10]
        assert output["fetched"] == 27
        assert output["requestCount"] == 3
        assert session.scalar(select(func.count()).select_from(DisclosureRecord)) == 0


def test_provider_status_never_prints_secret_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OPENDART_ENABLED", "true")
    monkeypatch.setenv("OPENDART_API_KEY", DART_KEY)
    monkeypatch.setenv("SEC_EDGAR_ENABLED", "true")
    monkeypatch.setenv("SEC_USER_AGENT_CONTACT", "fixture@example.invalid")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["provider-status"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["OPENDART"]["secret"] == "SET"
    assert payload["SEC_EDGAR"]["secret"] == "SET"
    assert DART_KEY not in output
    assert "fixture@example.invalid" not in output
