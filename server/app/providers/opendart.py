from __future__ import annotations

import json
import re
from contextlib import nullcontext
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import httpx

from app.core.config import Settings
from app.core.time import Clock, SystemClock
from app.models.disclosures import ProviderName, ProviderStatus
from app.providers.common import (
    ProviderCompany,
    ProviderDisclosure,
    ProviderFetchResult,
    ProviderResponseDiagnostics,
)

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DISCLOSURE_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
OFFICIAL_DISCLOSURE_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_number}"
MAX_COMPANY_ARCHIVE_BYTES = 60 * 1024 * 1024
MAX_COMPANY_ARCHIVE_FILES = 10
MAX_COMPANY_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
ZIP_CONTENT_TYPES = {
    "application/octet-stream",
    "application/x-msdownload",
    "application/zip",
    "application/x-zip-compressed",
}
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
OFFICIAL_ERROR_MAP = {
    "010": (ProviderStatus.FAILED, "INVALID_API_KEY"),
    "011": (ProviderStatus.FAILED, "API_KEY_DISABLED"),
    "012": (ProviderStatus.FAILED, "API_KEY_ACCESS_DENIED"),
    "020": (ProviderStatus.RATE_LIMITED, "RATE_LIMITED"),
    "021": (ProviderStatus.RATE_LIMITED, "RATE_LIMITED"),
    "100": (ProviderStatus.FAILED, "MISSING_REQUIRED_PARAMETER"),
    "101": (ProviderStatus.FAILED, "INVALID_REQUEST_PARAMETER"),
    "800": (ProviderStatus.FAILED, "PROVIDER_TEMPORARY_ERROR"),
    "900": (ProviderStatus.FAILED, "PROVIDER_TEMPORARY_ERROR"),
    "901": (ProviderStatus.FAILED, "API_KEY_DISABLED"),
}
SAFE_OFFICIAL_CODE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
POTENTIAL_SECRET = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{40}(?![A-Za-z0-9])")


class OpenDartProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._clock = clock or SystemClock()

    @property
    def status(self) -> ProviderStatus:
        return (
            ProviderStatus.READY
            if self._settings.open_dart_configured
            else ProviderStatus.NOT_CONFIGURED
        )

    def fetch_company_codes(self) -> ProviderFetchResult:
        if self.status is ProviderStatus.NOT_CONFIGURED:
            return ProviderFetchResult(
                provider=ProviderName.OPENDART,
                status=ProviderStatus.NOT_CONFIGURED,
            )
        request_count = 0
        try:
            with self._client_context() as client:
                request_count += 1
                response = client.get(
                    CORP_CODE_URL,
                    params={"crtfc_key": self._settings.opendart_api_key},
                    timeout=10.0,
                    follow_redirects=True,
                )
            payload_kind, official_code, official_message = self._classify_payload(
                response.content,
                response.headers.get("Content-Type"),
            )
            diagnostics = self._response_diagnostics(
                response,
                payload_kind=payload_kind,
                official_code=official_code,
                official_message=official_message,
            )
            if response.url.host != "opendart.fss.or.kr":
                return self._error(
                    ProviderStatus.FAILED,
                    "UNEXPECTED_REDIRECT_HOST",
                    request_count,
                    diagnostics,
                )
            if official_code:
                return self._api_error(
                    official_code,
                    official_message,
                    request_count,
                    diagnostics,
                )
            if response.status_code == 429:
                return self._error(
                    ProviderStatus.RATE_LIMITED,
                    "RATE_LIMITED",
                    request_count,
                    diagnostics,
                )
            if response.status_code >= 500:
                return self._error(
                    ProviderStatus.FAILED,
                    "PROVIDER_TEMPORARY_ERROR",
                    request_count,
                    diagnostics,
                )
            if response.status_code != 200:
                code = (
                    "UNEXPECTED_HTML_RESPONSE"
                    if payload_kind == "HTML"
                    else f"HTTP_{response.status_code}"
                )
                return self._error(
                    ProviderStatus.FAILED,
                    code,
                    request_count,
                    diagnostics,
                )
            if payload_kind != "ZIP":
                code = (
                    "UNEXPECTED_HTML_RESPONSE"
                    if payload_kind == "HTML"
                    else "INVALID_ZIP_RESPONSE"
                )
                return self._error(
                    ProviderStatus.FAILED,
                    code,
                    request_count,
                    diagnostics,
                )
            if len(response.content) > MAX_COMPANY_ARCHIVE_BYTES:
                return self._error(
                    ProviderStatus.FAILED,
                    "INVALID_ZIP_RESPONSE",
                    request_count,
                    diagnostics,
                )
            try:
                records = self.parse_company_codes(
                    response.content,
                    self._clock.now(),
                )
            except (BadZipFile, ElementTree.ParseError, ValueError):
                return self._error(
                    ProviderStatus.FAILED,
                    "INVALID_ZIP_RESPONSE",
                    request_count,
                    diagnostics,
                )
            return ProviderFetchResult(
                provider=ProviderName.OPENDART,
                status=ProviderStatus.READY,
                companies=tuple(records),
                request_count=request_count,
                diagnostics=diagnostics,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            return self._error(
                ProviderStatus.NETWORK_UNAVAILABLE,
                "NETWORK_UNAVAILABLE",
                request_count,
            )
        except httpx.HTTPStatusError as error:
            return self._error(
                ProviderStatus.FAILED,
                f"HTTP_{error.response.status_code}",
                request_count,
            )
        except (ElementTree.ParseError, ValueError):
            return self._error(
                ProviderStatus.FAILED,
                "INVALID_ZIP_RESPONSE",
                request_count,
            )

    def fetch_disclosures(
        self,
        *,
        corp_code: str,
        published_from: datetime,
        published_to: datetime,
        limit: int = 100,
    ) -> ProviderFetchResult:
        if self.status is ProviderStatus.NOT_CONFIGURED:
            return ProviderFetchResult(
                provider=ProviderName.OPENDART,
                status=ProviderStatus.NOT_CONFIGURED,
            )
        request_count = 0
        try:
            disclosures: list[ProviderDisclosure] = []
            with self._client_context() as client:
                page = 1
                while len(disclosures) < max(limit, 1) and page <= 3:
                    request_count += 1
                    response = client.get(
                        DISCLOSURE_LIST_URL,
                        params={
                            "crtfc_key": self._settings.opendart_api_key,
                            "corp_code": corp_code,
                            "bgn_de": published_from.strftime("%Y%m%d"),
                            "end_de": published_to.strftime("%Y%m%d"),
                            "last_reprt_at": "N",
                            "page_no": page,
                            "page_count": min(max(limit - len(disclosures), 1), 100),
                        },
                        timeout=10.0,
                    )
                    if response.status_code == 429:
                        return self._error(
                            ProviderStatus.RATE_LIMITED,
                            "HTTP_429",
                            request_count,
                        )
                    if response.status_code in {403, 404}:
                        return self._error(
                            ProviderStatus.FAILED,
                            f"HTTP_{response.status_code}",
                            request_count,
                        )
                    response.raise_for_status()
                    body = response.json()
                    code = str(body.get("status", "")).strip()
                    if code == "013":
                        break
                    if code != "000":
                        return self._api_error(
                            code,
                            str(body.get("message", "")),
                            request_count,
                        )
                    disclosures.extend(
                        self._parse_disclosure(item)
                        for item in body.get("list", [])
                        if isinstance(item, dict)
                    )
                    if page >= int(body.get("total_page", page)):
                        break
                    page += 1
            return ProviderFetchResult(
                provider=ProviderName.OPENDART,
                status=ProviderStatus.READY,
                disclosures=tuple(disclosures[:limit]),
                request_count=request_count,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            return self._error(
                ProviderStatus.NETWORK_UNAVAILABLE,
                "NETWORK_UNAVAILABLE",
                request_count,
            )
        except httpx.HTTPStatusError as error:
            return self._error(
                ProviderStatus.FAILED,
                f"HTTP_{error.response.status_code}",
                request_count,
            )
        except (ValueError, TypeError):
            return self._error(
                ProviderStatus.FAILED,
                "INVALID_PROVIDER_RESPONSE",
                request_count,
            )

    @staticmethod
    def parse_company_codes(
        content: bytes,
        fetched_at: datetime,
    ) -> list[ProviderCompany]:
        xml_content = content
        if content.startswith(ZIP_SIGNATURES):
            with ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if not entries or len(entries) > MAX_COMPANY_ARCHIVE_FILES:
                    raise ValueError("OpenDART archive file count is unsafe")
                total_size = 0
                corp_code_entries = []
                for entry in entries:
                    normalized_name = entry.filename.replace("\\", "/")
                    path = PurePosixPath(normalized_name)
                    if (
                        entry.filename.startswith(("/", "\\"))
                        or "\\" in entry.filename
                        or ".." in path.parts
                        or path.is_absolute()
                        or entry.flag_bits & 0x1
                    ):
                        raise ValueError("OpenDART archive path is unsafe")
                    if not entry.is_dir():
                        total_size += entry.file_size
                        if path.name.lower() == "corpcode.xml":
                            corp_code_entries.append(entry)
                if total_size > MAX_COMPANY_UNCOMPRESSED_BYTES or len(corp_code_entries) != 1:
                    raise ValueError("OpenDART archive content is unsafe")
                entry = corp_code_entries[0]
                if (
                    entry.is_dir()
                    or entry.file_size <= 0
                    or entry.file_size > MAX_COMPANY_UNCOMPRESSED_BYTES
                ):
                    raise ValueError("OpenDART XML archive entry is unsafe")
                xml_content = archive.read(entry)
        root = ElementTree.fromstring(xml_content)
        seen: set[str] = set()
        records: list[ProviderCompany] = []
        for item in root.findall(".//list"):
            corp_code = (item.findtext("corp_code") or "").strip()
            corp_name = (item.findtext("corp_name") or "").strip()
            stock_code = (item.findtext("stock_code") or "").strip()
            modify_date = (item.findtext("modify_date") or "").strip()
            if len(corp_code) != 8 or not corp_code.isdigit() or not corp_name:
                continue
            if corp_code in seen:
                raise ValueError("duplicate OpenDART corpCode")
            seen.add(corp_code)
            if stock_code and (len(stock_code) != 6 or not stock_code.isdigit()):
                stock_code = ""
            try:
                source_updated_at = (
                    datetime.strptime(modify_date, "%Y%m%d").replace(tzinfo=UTC)
                    if modify_date
                    else None
                )
            except ValueError:
                source_updated_at = None
            records.append(
                ProviderCompany(
                    provider=ProviderName.OPENDART,
                    provider_company_id=corp_code,
                    symbol=stock_code,
                    company_name=corp_name,
                    exchange=None,
                    cik=None,
                    corp_code=corp_code,
                    stock_code=stock_code or None,
                    source_url=CORP_CODE_URL,
                    source_updated_at=source_updated_at,
                    fetched_at=fetched_at,
                )
            )
        if not records:
            raise ValueError("OpenDART company archive contains no valid records")
        return records

    def _parse_disclosure(self, item: dict[str, object]) -> ProviderDisclosure:
        receipt = str(item.get("rcept_no", "")).strip()
        title = str(item.get("report_nm", "")).strip()
        company = str(item.get("corp_name", "")).strip()
        published = datetime.strptime(str(item.get("rcept_dt", "")), "%Y%m%d").replace(
            tzinfo=UTC
        )
        if not receipt or not title or not company:
            raise ValueError("invalid OpenDART disclosure record")
        remark = str(item.get("rm", ""))
        return ProviderDisclosure(
            provider=ProviderName.OPENDART,
            provider_document_id=receipt,
            accession_number=None,
            receipt_number=receipt,
            form_type=None,
            report_type=str(item.get("pblntf_ty", "")).strip() or None,
            title=title,
            company_name=company,
            official_url=OFFICIAL_DISCLOSURE_URL.format(receipt_number=receipt),
            published_at=published,
            source_updated_at=None,
            primary_document=None,
            amendment="정정" in title or "정정" in remark,
        )

    def _client_context(self):
        return nullcontext(self._client) if self._client is not None else httpx.Client()

    @staticmethod
    def _classify_payload(
        content: bytes,
        content_type_header: str | None,
    ) -> tuple[str, str | None, str | None]:
        if not content:
            return "EMPTY", None, None
        if content.startswith(ZIP_SIGNATURES):
            return "ZIP", None, None

        stripped = content.lstrip()
        content_type = (content_type_header or "").split(";", 1)[0].lower()
        if stripped.startswith((b"{", b"[")) or "json" in content_type:
            try:
                body = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return "UNKNOWN", None, None
            if isinstance(body, dict):
                return (
                    "JSON_ERROR",
                    str(body.get("status", "")).strip() or None,
                    str(body.get("message", "")).strip() or None,
                )
            return "JSON_ERROR", None, None

        lowered = stripped[:256].lower()
        if (
            content_type == "text/html"
            or lowered.startswith(b"<!doctype html")
            or lowered.startswith(b"<html")
        ):
            return "HTML", None, None
        if stripped.startswith(b"<") or "xml" in content_type:
            try:
                root = ElementTree.fromstring(content)
            except ElementTree.ParseError:
                return "UNKNOWN", None, None
            if root.tag.lower().endswith("html"):
                return "HTML", None, None
            return (
                "XML_ERROR",
                (root.findtext(".//status") or "").strip() or None,
                (root.findtext(".//message") or "").strip() or None,
            )
        return "UNKNOWN", None, None

    def _response_diagnostics(
        self,
        response: httpx.Response,
        *,
        payload_kind: str,
        official_code: str | None,
        official_message: str | None,
    ) -> ProviderResponseDiagnostics:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip() or None
        raw_length = response.headers.get("Content-Length", "").strip()
        try:
            content_length = int(raw_length) if raw_length else None
        except ValueError:
            content_length = None
        safe_code = (
            official_code
            if official_code and SAFE_OFFICIAL_CODE.fullmatch(official_code)
            else None
        )
        return ProviderResponseDiagnostics(
            http_status=response.status_code,
            content_type=content_type[:120] if content_type else None,
            content_length=content_length,
            content_disposition_present="Content-Disposition" in response.headers,
            payload_kind=payload_kind,
            zip_signature_valid=response.content.startswith(ZIP_SIGNATURES),
            redirect_count=len(response.history),
            official_status_code=safe_code,
            official_message=self._safe_official_message(official_message),
        )

    def _safe_official_message(self, value: str | None) -> str | None:
        if not value:
            return None
        message = " ".join(value.split())
        secret = self._settings.opendart_api_key
        if secret:
            message = message.replace(secret, "[REDACTED]")
        message = POTENTIAL_SECRET.sub("[REDACTED]", message)
        return message[:200] or None

    def _api_error(
        self,
        code: str,
        message: str | None,
        request_count: int,
        diagnostics: ProviderResponseDiagnostics | None = None,
    ) -> ProviderFetchResult:
        safe_code = code if SAFE_OFFICIAL_CODE.fullmatch(code) else "UNKNOWN"
        status, error_code = OFFICIAL_ERROR_MAP.get(
            safe_code,
            (ProviderStatus.FAILED, f"OPENDART_{safe_code}"),
        )
        if diagnostics is None:
            diagnostics = ProviderResponseDiagnostics(
                official_status_code=safe_code,
                official_message=self._safe_official_message(message),
                payload_kind="JSON_ERROR",
            )
        return self._error(
            status,
            error_code,
            request_count,
            diagnostics,
        )

    @staticmethod
    def _error(
        status: ProviderStatus,
        code: str,
        request_count: int = 0,
        diagnostics: ProviderResponseDiagnostics | None = None,
    ) -> ProviderFetchResult:
        return ProviderFetchResult(
            provider=ProviderName.OPENDART,
            status=status,
            request_count=request_count,
            error_code=code,
            diagnostics=diagnostics,
        )
