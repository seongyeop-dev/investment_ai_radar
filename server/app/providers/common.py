from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models.disclosures import ProviderName, ProviderStatus


@dataclass(frozen=True, slots=True)
class ProviderResponseDiagnostics:
    http_status: int | None = None
    content_type: str | None = None
    content_length: int | None = None
    content_disposition_present: bool = False
    payload_kind: str = "UNKNOWN"
    zip_signature_valid: bool = False
    redirect_count: int = 0
    official_status_code: str | None = None
    official_message: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderCompany:
    provider: ProviderName
    provider_company_id: str
    symbol: str
    company_name: str
    exchange: str | None
    cik: str | None
    corp_code: str | None
    stock_code: str | None
    source_url: str
    source_updated_at: datetime | None
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderDisclosure:
    provider: ProviderName
    provider_document_id: str
    accession_number: str | None
    receipt_number: str | None
    form_type: str | None
    report_type: str | None
    title: str
    company_name: str
    official_url: str
    published_at: datetime
    source_updated_at: datetime | None
    primary_document: str | None
    amendment: bool = False


@dataclass(frozen=True, slots=True)
class ProviderFetchResult:
    provider: ProviderName
    status: ProviderStatus
    companies: tuple[ProviderCompany, ...] = ()
    disclosures: tuple[ProviderDisclosure, ...] = ()
    request_count: int = 0
    error_code: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: ProviderResponseDiagnostics | None = None
