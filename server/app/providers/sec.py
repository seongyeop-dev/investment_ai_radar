from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.backoff import ReconnectBackoff
from app.core.config import Settings
from app.core.time import Clock, SystemClock
from app.models.disclosures import ProviderName, ProviderStatus
from app.providers.common import (
    ProviderCompany,
    ProviderDisclosure,
    ProviderFetchResult,
)

TICKER_MAPPING_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVE_DOCUMENT_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_without_zeroes}/"
    "{accession_without_dashes}/{primary_document}"
)
SEC_MAX_REQUESTS_PER_SECOND = 10
SEC_MIN_REQUEST_INTERVAL_SECONDS = 1.0
PRIORITY_FORMS = {"8-K", "10-K", "10-Q", "6-K", "20-F", "40-F"}


class SecEdgarProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        clock: Clock | None = None,
        sleep: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
        max_attempts: int = 2,
    ) -> None:
        self._settings = settings
        self._client = client
        self._clock = clock or SystemClock()
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic
        self._max_attempts = max_attempts
        self._last_request_at: float | None = None
        self._request_count = 0
        self._cache: dict[str, tuple[float, Any]] = {}
        self._backoff = ReconnectBackoff(jitter_ratio=0.2, maximum_seconds=4)

    @property
    def status(self) -> ProviderStatus:
        return (
            ProviderStatus.READY
            if self._settings.sec_configured
            else ProviderStatus.NOT_CONFIGURED
        )

    def fetch_company_tickers(self) -> ProviderFetchResult:
        if self.status is ProviderStatus.NOT_CONFIGURED:
            return ProviderFetchResult(
                provider=ProviderName.SEC_EDGAR,
                status=ProviderStatus.NOT_CONFIGURED,
            )
        self._request_count = 0
        response = self._request_json(TICKER_MAPPING_URL)
        if isinstance(response, ProviderFetchResult):
            return response
        try:
            fields = response["fields"]
            rows = response["data"]
            field_indexes = {name: fields.index(name) for name in fields}
            fetched_at = self._clock.now()
            companies = []
            for row in rows:
                cik = str(row[field_indexes["cik"]]).strip().zfill(10)
                ticker = str(row[field_indexes["ticker"]]).strip().upper()
                name = str(row[field_indexes["name"]]).strip()
                exchange_value = row[field_indexes["exchange"]]
                exchange = str(exchange_value).strip().upper() if exchange_value else None
                if not cik.isdigit() or len(cik) != 10 or not ticker or not name:
                    raise ValueError("invalid SEC company row")
                companies.append(
                    ProviderCompany(
                        provider=ProviderName.SEC_EDGAR,
                        provider_company_id=f"{cik}:{ticker}",
                        symbol=ticker,
                        company_name=name,
                        exchange=exchange,
                        cik=cik,
                        corp_code=None,
                        stock_code=None,
                        source_url=TICKER_MAPPING_URL,
                        source_updated_at=None,
                        fetched_at=fetched_at,
                    )
                )
            return ProviderFetchResult(
                provider=ProviderName.SEC_EDGAR,
                status=ProviderStatus.READY,
                companies=tuple(companies),
                request_count=self._request_count,
            )
        except (KeyError, TypeError, ValueError):
            return self._error(
                ProviderStatus.FAILED,
                "INVALID_PROVIDER_RESPONSE",
                self._request_count,
            )

    def fetch_submissions(self, cik: str, *, limit: int = 100) -> ProviderFetchResult:
        if self.status is ProviderStatus.NOT_CONFIGURED:
            return ProviderFetchResult(
                provider=ProviderName.SEC_EDGAR,
                status=ProviderStatus.NOT_CONFIGURED,
            )
        normalized_cik = cik.strip().zfill(10)
        if len(normalized_cik) != 10 or not normalized_cik.isdigit():
            return self._error(ProviderStatus.ERROR, "INVALID_CIK")
        self._request_count = 0
        response = self._request_json(SUBMISSIONS_URL.format(cik=normalized_cik))
        if isinstance(response, ProviderFetchResult):
            return response
        try:
            company_name = str(response["name"]).strip()
            filings = response["filings"]
            max_items = max(1, min(limit, 1000))
            disclosures: list[ProviderDisclosure] = []
            seen: set[str] = set()

            def append_rows(rows: dict[str, list[object]]) -> None:
                accessions = rows.get("accessionNumber", [])
                for index in range(len(accessions)):
                    if len(disclosures) >= max_items:
                        return

                    def value(name: str, row_index: int = index) -> str:
                        values = rows.get(name, [])
                        return str(values[row_index]).strip() if row_index < len(values) else ""

                    accession = value("accessionNumber")
                    primary = value("primaryDocument")
                    form = value("form").upper()
                    base_form = form.removesuffix("/A")
                    if base_form not in PRIORITY_FORMS:
                        continue
                    if not accession or accession in seen or not primary:
                        continue
                    accepted = value("acceptanceDateTime")
                    filing_date = value("filingDate")
                    published = (
                        datetime.fromisoformat(accepted.replace("Z", "+00:00")).astimezone(UTC)
                        if accepted
                        else datetime.strptime(filing_date, "%Y-%m-%d").replace(tzinfo=UTC)
                    )
                    seen.add(accession)
                    disclosures.append(
                        ProviderDisclosure(
                            provider=ProviderName.SEC_EDGAR,
                            provider_document_id=accession,
                            accession_number=accession,
                            receipt_number=None,
                            form_type=form,
                            report_type=value("reportDate") or None,
                            title=value("primaryDocDescription") or form,
                            company_name=company_name,
                            official_url=ARCHIVE_DOCUMENT_URL.format(
                                cik_without_zeroes=str(int(normalized_cik)),
                                accession_without_dashes=accession.replace("-", ""),
                                primary_document=primary,
                            ),
                            published_at=published,
                            source_updated_at=published,
                            primary_document=primary,
                            amendment=form.endswith("/A"),
                        )
                    )

            append_rows(filings["recent"])
            for file_metadata in filings.get("files", []):
                if len(disclosures) >= max_items:
                    break
                name = str(file_metadata.get("name", "")).strip()
                if not name or "/" in name or "\\" in name:
                    continue
                supplemental = self._request_json(SUBMISSIONS_FILE_URL.format(name=name))
                if isinstance(supplemental, ProviderFetchResult):
                    break
                append_rows(supplemental)
            return ProviderFetchResult(
                provider=ProviderName.SEC_EDGAR,
                status=ProviderStatus.READY,
                disclosures=tuple(disclosures),
                request_count=self._request_count,
            )
        except (KeyError, TypeError, ValueError, IndexError):
            return self._error(
                ProviderStatus.FAILED,
                "INVALID_PROVIDER_RESPONSE",
                self._request_count,
            )

    def _request_json(self, url: str) -> Any | ProviderFetchResult:
        now = self._monotonic()
        cached = self._cache.get(url)
        if cached is not None and now - cached[0] <= 300:
            return cached[1]
        for attempt in range(self._max_attempts):
            self._rate_limit()
            try:
                with self._client_context() as client:
                    self._request_count += 1
                    response = client.get(
                        url,
                        headers={
                            "User-Agent": self._settings.sec_user_agent,
                            "Accept-Encoding": "gzip, deflate",
                        },
                        timeout=10.0,
                    )
                if response.status_code in {403, 429}:
                    if attempt + 1 < self._max_attempts:
                        retry_after = response.headers.get("Retry-After", "").strip()
                        delay = (
                            float(retry_after)
                            if retry_after.replace(".", "", 1).isdigit()
                            else self._backoff.delay(attempt)
                        )
                        self._sleep(min(max(delay, 0), 60))
                        continue
                    status = (
                        ProviderStatus.RATE_LIMITED
                        if response.status_code == 429
                        else ProviderStatus.ERROR
                    )
                    return self._error(
                        status,
                        f"HTTP_{response.status_code}",
                        self._request_count,
                    )
                if response.status_code == 404:
                    return self._error(
                        ProviderStatus.FAILED,
                        "HTTP_404",
                        self._request_count,
                    )
                response.raise_for_status()
                body = response.json()
                self._cache[url] = (self._monotonic(), body)
                return body
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt + 1 < self._max_attempts:
                    self._sleep(self._backoff.delay(attempt))
                    continue
                return self._error(
                    ProviderStatus.NETWORK_UNAVAILABLE,
                    "NETWORK_UNAVAILABLE",
                    self._request_count,
                )
            except httpx.HTTPStatusError as error:
                return self._error(
                    ProviderStatus.FAILED,
                    f"HTTP_{error.response.status_code}",
                    self._request_count,
                )
            except ValueError:
                return self._error(
                    ProviderStatus.FAILED,
                    "INVALID_PROVIDER_RESPONSE",
                    self._request_count,
                )
        return self._error(ProviderStatus.FAILED, "REQUEST_FAILED", self._request_count)

    def _rate_limit(self) -> None:
        now = self._monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < SEC_MIN_REQUEST_INTERVAL_SECONDS:
                self._sleep(SEC_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = self._monotonic()

    def _client_context(self):
        return nullcontext(self._client) if self._client is not None else httpx.Client()

    @staticmethod
    def _error(
        status: ProviderStatus, code: str, request_count: int = 0
    ) -> ProviderFetchResult:
        return ProviderFetchResult(
            provider=ProviderName.SEC_EDGAR,
            status=status,
            request_count=request_count,
            error_code=code,
        )
