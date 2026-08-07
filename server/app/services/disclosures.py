from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select

from app.core.errors import disclosure_not_found, information_event_not_found
from app.core.time import SystemClock, require_aware_utc
from app.models.contracts import VerificationStatus
from app.models.database import PortfolioItemRecord, SourceGrade
from app.models.disclosures import (
    DisclosureRecord,
    EvidenceItemRecord,
    InformationEventRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    LifecycleStatus,
    ProviderName,
    SummaryStatus,
)
from app.repositories.disclosures import DisclosureRepository


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _display_normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def canonical_official_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "ref", "source"}
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def _hash(value: object) -> str:
    payload = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class DisclosureIngest:
    instrument_id: str
    provider: ProviderName
    provider_document_id: str
    title: str
    company_name: str
    official_url: str
    published_at: datetime
    event_type: str
    claim: str
    accession_number: str | None = None
    receipt_number: str | None = None
    form_type: str | None = None
    report_type: str | None = None
    source_updated_at: datetime | None = None
    summary: str | None = None
    key_facts: list[dict[str, object]] = field(default_factory=list)
    correction_of_document_id: str | None = None
    denied: bool = False
    stale_reused: bool = False
    material_change: bool = False


@dataclass(frozen=True, slots=True)
class OfficialDisclosureImportPlan:
    portfolio_item: PortfolioItemRecord
    instrument: InstrumentRecord | None
    provider: ProviderName
    provider_document_id: str
    accession_number: str | None
    receipt_number: str | None
    canonical_url: str
    duplicate: DisclosureRecord | None
    would_create_instrument: bool
    validation_warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OfficialDisclosureImportResult:
    disclosure: DisclosureRecord
    event: InformationEventRecord
    instrument_created: bool
    validation_warnings: tuple[str, ...]


def official_provider_for_url(value: str) -> ProviderName:
    canonical_url = canonical_official_url(value)
    hostname = (urlsplit(canonical_url).hostname or "").lower()
    if hostname == "sec.gov" or hostname.endswith(".sec.gov"):
        return ProviderName.SEC_EDGAR
    if hostname in {"dart.fss.or.kr", "opendart.fss.or.kr"}:
        return ProviderName.OPENDART
    raise ValueError("SEC 또는 OpenDART 공식 주소만 등록할 수 있습니다.")


def _official_document_identity(
    provider: ProviderName,
    canonical_url: str,
) -> tuple[str, str | None, str | None]:
    if provider is ProviderName.SEC_EDGAR:
        accession_match = re.search(r"(?<!\d)(\d{10}-\d{2}-\d{6})(?!\d)", canonical_url)
        accession_number = accession_match.group(1) if accession_match else None
        if accession_number is None:
            compact_match = re.search(r"(?<!\d)(\d{18})(?!\d)", canonical_url)
            if compact_match:
                compact = compact_match.group(1)
                accession_number = f"{compact[:10]}-{compact[10:12]}-{compact[12:]}"
        provider_document_id = accession_number or f"manual-sec-{_hash(canonical_url)[:40]}"
        return provider_document_id, accession_number, None

    receipt_number = next(
        (
            item
            for key, item in parse_qsl(urlsplit(canonical_url).query, keep_blank_values=True)
            if key.lower() == "rcpno" and item.isdigit()
        ),
        None,
    )
    if receipt_number is None:
        receipt_match = re.search(r"(?<!\d)(\d{14})(?!\d)", canonical_url)
        receipt_number = receipt_match.group(1) if receipt_match else None
    provider_document_id = receipt_number or f"manual-dart-{_hash(canonical_url)[:40]}"
    return provider_document_id, None, receipt_number


class DisclosureService:
    def __init__(self, repository: DisclosureRepository) -> None:
        self.repository = repository
        self.session = repository.session

    def preview_import(
        self,
        *,
        official_url: str,
        portfolio_item_id: str,
    ) -> OfficialDisclosureImportPlan:
        canonical_url = canonical_official_url(official_url)
        provider = official_provider_for_url(canonical_url)
        portfolio_item = self.session.get(PortfolioItemRecord, portfolio_item_id)
        if portfolio_item is None or portfolio_item.archived_at is not None:
            raise ValueError("등록된 보유·관심 종목을 찾을 수 없습니다.")

        instrument = self._instrument_for(portfolio_item)
        provider_document_id, accession_number, receipt_number = _official_document_identity(
            provider, canonical_url
        )
        duplicate = self.repository.find_duplicate(
            provider,
            provider_document_id,
            canonical_url,
        )
        warnings: list[str] = []
        if canonical_url != official_url.strip():
            warnings.append("URL_NORMALIZED")
        warnings.append(
            "SEC_OFFICIAL_URL_CONFIRMED"
            if provider is ProviderName.SEC_EDGAR
            else "OPENDART_OFFICIAL_URL_CONFIRMED"
        )
        if duplicate is not None:
            warnings.append("DUPLICATE_OFFICIAL_DISCLOSURE")
        if instrument is None:
            warnings.append("INSTRUMENT_WILL_BE_CREATED")

        return OfficialDisclosureImportPlan(
            portfolio_item=portfolio_item,
            instrument=instrument,
            provider=provider,
            provider_document_id=provider_document_id,
            accession_number=accession_number,
            receipt_number=receipt_number,
            canonical_url=canonical_url,
            duplicate=duplicate,
            would_create_instrument=instrument is None,
            validation_warnings=tuple(warnings),
        )

    def confirm_import(
        self,
        *,
        official_url: str,
        title: str,
        published_at: datetime,
        claim: str,
        summary: str | None,
        portfolio_item_id: str,
        form_type: str | None,
        material_change: bool,
    ) -> OfficialDisclosureImportResult:
        plan = self.preview_import(
            official_url=official_url,
            portfolio_item_id=portfolio_item_id,
        )
        if plan.duplicate is not None:
            raise ValueError("동일한 공식 공시가 이미 등록되어 있습니다.")

        current = SystemClock().now()
        instrument_created = plan.instrument is None
        instrument = plan.instrument or self._create_instrument(
            plan.portfolio_item,
            provider=plan.provider,
            now=current,
        )
        if plan.portfolio_item.instrument_id != instrument.id:
            plan.portfolio_item.instrument_id = instrument.id
            plan.portfolio_item.updated_at = current

        disclosure, event, created = self.ingest(
            DisclosureIngest(
                instrument_id=instrument.id,
                provider=plan.provider,
                provider_document_id=plan.provider_document_id,
                accession_number=plan.accession_number,
                receipt_number=plan.receipt_number,
                form_type=form_type,
                report_type=form_type,
                title=title.strip(),
                company_name=plan.portfolio_item.name,
                official_url=plan.canonical_url,
                published_at=published_at,
                event_type="OFFICIAL_DISCLOSURE",
                claim=claim.strip(),
                summary=summary.strip() if summary else None,
                material_change=material_change,
            ),
            now=current,
        )
        if not created:
            raise ValueError("동일한 공식 공시가 이미 등록되어 있습니다.")
        event.latest_official_at = published_at
        self.session.flush()
        return OfficialDisclosureImportResult(
            disclosure=disclosure,
            event=event,
            instrument_created=instrument_created,
            validation_warnings=plan.validation_warnings,
        )

    def _instrument_for(
        self,
        portfolio_item: PortfolioItemRecord,
    ) -> InstrumentRecord | None:
        if portfolio_item.instrument_id:
            instrument = self.session.get(
                InstrumentRecord,
                portfolio_item.instrument_id,
            )
            if instrument is not None:
                return instrument
        return self.session.scalar(
            select(InstrumentRecord).where(
                InstrumentRecord.market == portfolio_item.market,
                InstrumentRecord.canonical_symbol == portfolio_item.symbol,
                InstrumentRecord.active.is_(True),
            )
        )

    def _create_instrument(
        self,
        portfolio_item: PortfolioItemRecord,
        *,
        provider: ProviderName,
        now: datetime,
    ) -> InstrumentRecord:
        instrument = InstrumentRecord(
            canonical_symbol=portfolio_item.symbol,
            display_name=portfolio_item.name,
            local_name=portfolio_item.name,
            exchange=portfolio_item.market,
            market=portfolio_item.market,
            country=self._country_for(
                portfolio_item.market,
                portfolio_item.currency.value,
            ),
            currency=portfolio_item.currency,
            asset_type=portfolio_item.asset_type,
            active=True,
            verification_status=InstrumentVerificationStatus.VERIFIED,
            verification_source=f"USER_CONFIRMED_{provider.value}",
            verified_at=now,
        )
        self.session.add(instrument)
        self.session.flush()
        return instrument

    @staticmethod
    def _country_for(market: str, currency: str) -> str:
        normalized_market = market.strip().upper()
        if normalized_market in {"KRX", "KOSPI", "KOSDAQ", "UPBIT"}:
            return "KOR"
        if normalized_market in {"NASDAQ", "NYSE", "AMEX", "OTC"}:
            return "USA"
        if currency == "KRW":
            return "KOR"
        if currency == "USD":
            return "USA"
        return "ZZZ"

    def get_disclosure(self, record_id: str) -> DisclosureRecord:
        record = self.repository.get_disclosure(record_id)
        if record is None:
            raise disclosure_not_found()
        return record

    def get_event(self, event_id: str) -> InformationEventRecord:
        record = self.repository.get_event(event_id)
        if record is None:
            raise information_event_not_found()
        return record

    def ingest(
        self, payload: DisclosureIngest, *, now: datetime
    ) -> tuple[DisclosureRecord, InformationEventRecord, bool]:
        now = require_aware_utc(now)
        duplicate = self.repository.find_duplicate(
            payload.provider, payload.provider_document_id, payload.official_url
        )
        if duplicate:
            event = self.get_event(duplicate.event_id)
            display_claim = _display_normalized(payload.claim)
            if event.normalized_claim != display_claim:
                event.normalized_claim = display_claim
            if payload.summary and event.current_summary != payload.summary:
                event.current_summary = payload.summary
            if payload.material_change and not event.material_change:
                event.material_change = True
            self.repository.session.flush()
            return duplicate, event, False
        correction = None
        if payload.correction_of_document_id:
            correction = (
                self.repository.session.query(DisclosureRecord)
                .filter_by(
                    provider=payload.provider,
                    provider_document_id=payload.correction_of_document_id,
                )
                .one_or_none()
            )
        display_claim = _display_normalized(payload.claim)
        claim = _normalized(display_claim)
        event_key = _hash(f"{payload.instrument_id}|{payload.event_type.upper()}|{claim}")
        event = (
            self.get_event(correction.event_id)
            if correction is not None
            else self.repository.get_event_by_key(event_key)
        )
        created_event = event is None
        if event is None:
            event = InformationEventRecord(
                event_key=event_key,
                instrument_id=payload.instrument_id,
                event_type=payload.event_type.upper(),
                normalized_claim=display_claim,
                claim_fingerprint=_hash(claim),
                first_seen_at=payload.published_at,
                last_seen_at=payload.published_at,
                lifecycle_status=LifecycleStatus.ACTIVE,
                verification_status=VerificationStatus.OFFICIAL_CONFIRMED,
                source_count=0,
                official_source_count=0,
                current_summary=payload.summary,
            )
            self.repository.session.add(event)
            self.repository.session.flush()
        material_change = bool(
            correction or payload.denied or payload.stale_reused or payload.material_change
        )
        lifecycle = LifecycleStatus.ACTIVE
        verification = VerificationStatus.OFFICIAL_CONFIRMED
        if correction:
            lifecycle = LifecycleStatus.CORRECTED
            verification = VerificationStatus.CORRECTED
        elif payload.denied:
            lifecycle = LifecycleStatus.DENIED
            verification = VerificationStatus.OFFICIALLY_DENIED
        elif payload.stale_reused:
            lifecycle = LifecycleStatus.STALE
            verification = VerificationStatus.STALE_REUSED
        elif not created_event:
            lifecycle = LifecycleStatus.UPDATED
            material_change = True
        record = DisclosureRecord(
            instrument_id=payload.instrument_id,
            event_id=event.id,
            provider=payload.provider,
            provider_document_id=payload.provider_document_id,
            accession_number=payload.accession_number,
            receipt_number=payload.receipt_number,
            form_type=payload.form_type,
            report_type=payload.report_type,
            title=payload.title,
            company_name=payload.company_name,
            official_url=canonical_official_url(payload.official_url),
            published_at=require_aware_utc(payload.published_at),
            source_updated_at=payload.source_updated_at,
            first_seen_at=now,
            fetched_at=now,
            verified_at=now,
            verification_status=verification,
            source_grade=SourceGrade.A,
            content_fingerprint=_hash(claim),
            metadata_hash=_hash(
                {
                    "title": payload.title,
                    "url": payload.official_url,
                    "publishedAt": payload.published_at.isoformat(),
                }
            ),
            summary=payload.summary,
            summary_status=(
                SummaryStatus.STRUCTURED
                if payload.summary or payload.key_facts
                else SummaryStatus.NOT_GENERATED
            ),
            key_facts=payload.key_facts,
            material_change=material_change,
            correction_of_id=correction.id if correction else None,
            lifecycle_status=lifecycle,
        )
        self.repository.session.add(record)
        self.repository.session.flush()
        evidence = EvidenceItemRecord(
            event_id=event.id,
            disclosure_id=record.id,
            source_url=canonical_official_url(payload.official_url),
            source_title=payload.title,
            published_at=payload.published_at,
            claim=display_claim,
            evidence_hash=_hash(
                f"{payload.provider.value}|{payload.provider_document_id}|{claim}"
            ),
            independent_origin=True,
        )
        self.repository.session.add(evidence)
        event.source_count += 1
        event.official_source_count += 1
        event.last_seen_at = max(event.last_seen_at, payload.published_at)
        event.material_change = material_change
        event.lifecycle_status = lifecycle
        event.verification_status = verification
        if material_change:
            event.latest_material_change_at = payload.published_at
        if payload.summary:
            event.current_summary = payload.summary
        self.repository.session.flush()
        return record, event, True
