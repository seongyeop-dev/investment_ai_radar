from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import news_not_found
from app.core.time import SystemClock
from app.models.analyst_references import AnalystReferenceRecord
from app.models.contracts import VerificationStatus
from app.models.database import (
    HoldingStatus,
    PortfolioItemRecord,
    SourceGrade,
    SourceRecord,
    WatchEntityRecord,
)
from app.models.disclosures import (
    CertaintyLevel,
    CollectionRunRecord,
    CollectionRunType,
    CollectionStatus,
    DisclosureRecord,
    EvidenceItemRecord,
    InformationEventRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    LifecycleStatus,
    NewsClaimRecord,
    NewsProviderType,
    NewsReferenceRecord,
    NewsSummaryStatus,
    ProviderCursorRecord,
    ProviderName,
    ProviderStatus,
)
from app.models.operations import OperatingMode
from app.providers.news_feed import NewsFeedItem, NewsFeedProvider
from app.repositories.news import NewsRepository

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}
CONFIRMED = ("확정", "confirmed", "approved", "완료")
PLANNED = ("계획", "planned", "will ")
REVIEW = ("검토", "under review", "considering")
PROPOSED = ("제안", "proposed")
POSSIBLE = ("가능성", "possible", "may ", "could ")
SPECULATIVE = ("전망", "rumor", "speculation", "추정")
DENIAL = ("부인", "denies", "denied", "사실무근")
CORRECTION = ("정정", "correction", "corrected")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w가-힣]+", " ", value.lower())).strip()


def canonicalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("news URL must be an absolute HTTP(S) URL")
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
        )
    )
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            f"{parsed.hostname.lower()}{port}",
            parsed.path or "/",
            query,
            "",
        )
    )


def certainty_for(value: str) -> CertaintyLevel:
    lowered = value.lower()
    if any(term in lowered for term in CONFIRMED):
        return CertaintyLevel.CONFIRMED
    if any(term in lowered for term in REVIEW):
        return CertaintyLevel.UNDER_REVIEW
    if any(term in lowered for term in PLANNED):
        return CertaintyLevel.PLANNED
    if any(term in lowered for term in PROPOSED):
        return CertaintyLevel.PROPOSED
    if any(term in lowered for term in POSSIBLE):
        return CertaintyLevel.POSSIBLE
    if any(term in lowered for term in SPECULATIVE):
        return CertaintyLevel.SPECULATIVE
    return CertaintyLevel.ANNOUNCED


def _event_subject(value: str) -> str:
    normalized = normalize_text(value)
    normalized = re.sub(
        r"\b(?:19|20)\d{2}[-년./ ]\d{1,2}(?:[-월./ ]\d{1,2})?\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"\d+(?:[.,]\d+)?", " ", normalized)
    for phrase in (*CONFIRMED, *PLANNED, *REVIEW, *PROPOSED, *POSSIBLE, *SPECULATIVE):
        normalized = normalized.replace(phrase.strip(), " ")
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass(frozen=True, slots=True)
class NewsIngestResult:
    reference: NewsReferenceRecord
    event: InformationEventRecord
    created: bool


@dataclass(frozen=True, slots=True)
class ImportantInformationImportPlan:
    portfolio_item: PortfolioItemRecord
    instrument: InstrumentRecord | None
    classification_source: SourceRecord | None
    manual_source: SourceRecord | None
    canonical_url: str
    source_domain: str
    source_grade: SourceGrade
    official_source: bool
    duplicate: NewsReferenceRecord | None
    would_create_source: bool
    would_create_instrument: bool
    validation_warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImportantInformationImportResult:
    ingest: NewsIngestResult
    source_created: bool
    instrument_created: bool
    validation_warnings: tuple[str, ...]


class NewsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = NewsRepository(session)

    def get(self, reference_id: str) -> NewsReferenceRecord:
        reference = self.repository.get(reference_id)
        if reference is None:
            raise news_not_found()
        return reference

    def ingest(
        self,
        *,
        source: SourceRecord,
        instrument: InstrumentRecord,
        item: NewsFeedItem,
        portfolio_item_id: str | None,
        now: datetime,
    ) -> NewsIngestResult:
        canonical_url = canonicalize_url(item.original_url)
        url_hash = _hash(canonical_url)
        provider = NewsProviderType(source.provider_type or NewsProviderType.RSS.value)
        duplicate = self.repository.by_provider_item(provider, item.provider_item_id)
        duplicate = duplicate or self.repository.by_url_hash(url_hash)
        if duplicate:
            duplicate.last_seen_at = max(duplicate.last_seen_at, now)
            self.session.flush()
            event = self.session.get(InformationEventRecord, duplicate.information_event_id)
            assert event is not None
            return NewsIngestResult(duplicate, event, False)

        title = item.title.strip()[:500]
        normalized_title = normalize_text(title)
        primary_claim = (item.snippet or title).strip()[:2000]
        normalized_claim = normalize_text(primary_claim)
        claim_fingerprint = _hash(normalized_claim)
        subject = _event_subject(title) or normalized_title
        event_key = _hash(f"{instrument.id}|NEWS|{subject}")[:128]
        event = self.session.scalar(
            select(InformationEventRecord).where(InformationEventRecord.event_key == event_key)
        )
        event_references = self.repository.event_references(event.id) if event else []
        first_same_claim = next(
            (
                reference
                for reference in event_references
                if reference.claim_fingerprint == claim_fingerprint
            ),
            None,
        )
        stale_reused = first_same_claim is not None
        material_change = event is not None and first_same_claim is None
        certainty = certainty_for(primary_claim)
        official, conflicting = self._official_match(instrument.id, primary_claim, certainty)
        original_origin_key = normalize_text(
            source.original_source_name or item.original_source_name or source.name
        )
        existing_origins = {reference.original_origin_key for reference in event_references}
        independent_origin = original_origin_key not in existing_origins
        verification = VerificationStatus.NEEDS_VERIFICATION
        lifecycle = LifecycleStatus.ACTIVE
        if conflicting:
            verification = VerificationStatus.CONFLICTING
        elif official or source.official:
            verification = VerificationStatus.OFFICIAL_CONFIRMED
        elif (
            independent_origin
            and len(existing_origins) >= 1
            and source.source_grade
            in {
                SourceGrade.A,
                SourceGrade.B,
            }
        ):
            verification = VerificationStatus.MULTI_SOURCE_CONFIRMED
        official_transition = bool(
            event
            and official
            and event.verification_status
            not in {
                VerificationStatus.OFFICIAL_CONFIRMED,
                VerificationStatus.CONFLICTING,
            }
        )
        if any(term in title.lower() for term in CORRECTION):
            verification = VerificationStatus.CORRECTED
            lifecycle = LifecycleStatus.CORRECTED
            material_change = True
        elif any(term in title.lower() for term in DENIAL):
            verification = VerificationStatus.OFFICIALLY_DENIED
            lifecycle = LifecycleStatus.DENIED
            material_change = True
        elif stale_reused and verification is not VerificationStatus.MULTI_SOURCE_CONFIRMED:
            verification = VerificationStatus.STALE_REUSED
            lifecycle = LifecycleStatus.STALE
        elif material_change:
            lifecycle = LifecycleStatus.UPDATED
        if official_transition:
            stale_reused = False
            material_change = True
            lifecycle = LifecycleStatus.UPDATED
            verification = (
                VerificationStatus.CONFLICTING
                if conflicting
                else VerificationStatus.OFFICIAL_CONFIRMED
            )
        changed_facts = (
            [{"field": "primaryClaim", "value": primary_claim}] if material_change else []
        )
        if event is None:
            event = InformationEventRecord(
                event_key=event_key,
                instrument_id=instrument.id,
                event_type="NEWS",
                normalized_claim=normalized_claim,
                claim_fingerprint=claim_fingerprint,
                first_seen_at=item.published_at,
                last_seen_at=item.published_at,
                lifecycle_status=lifecycle,
                verification_status=verification,
                source_count=0,
                official_source_count=0,
                current_summary=None,
            )
            self.session.add(event)
            self.session.flush()

        summary_status = (
            NewsSummaryStatus.RULE_BASED if item.snippet else NewsSummaryStatus.METADATA_ONLY
        )
        short_summary = (
            f"{instrument.display_name} 관련 공개 Feed metadata에서 "
            f"'{title}' 항목이 확인되었습니다. 공식 확인 상태는 "
            f"{verification.value}입니다."
            if item.snippet
            else "제목과 공개 metadata만 확인되었습니다. 상세 내용은 원문을 참고해야 합니다."
        )
        trust_score = self._trust_score(source.source_grade, verification, independent_origin)
        reference = NewsReferenceRecord(
            instrument_id=instrument.id,
            portfolio_item_id=portfolio_item_id,
            source_id=source.id,
            provider=provider,
            provider_item_id=item.provider_item_id,
            title=title,
            normalized_title=normalized_title,
            source_name=source.name,
            source_domain=source.domain,
            canonical_url=canonical_url,
            canonical_url_hash=url_hash,
            original_url=item.original_url,
            published_at=item.published_at,
            source_updated_at=item.source_updated_at,
            first_seen_at=now,
            last_seen_at=now,
            fetched_at=now,
            verified_at=now if official or source.official else None,
            language=source.language,
            snippet=(item.snippet or "")[:1000] or None,
            short_summary=short_summary[:1000],
            summary_status=summary_status,
            primary_claim=primary_claim,
            claim_fingerprint=claim_fingerprint,
            content_fingerprint=_hash(f"{normalized_title}|{normalized_claim}"),
            verification_status=verification,
            source_grade=source.source_grade,
            trust_score=trust_score,
            certainty_level=certainty,
            independent_origin=independent_origin,
            original_origin_key=original_origin_key,
            duplicate_of_id=first_same_claim.id if first_same_claim else None,
            information_event_id=event.id,
            material_change=material_change,
            stale_reused=stale_reused,
            lifecycle_status=lifecycle,
            official_reference_ids=[record.id for record in official],
            changed_facts=changed_facts,
        )
        self.repository.create(reference)
        claim = NewsClaimRecord(
            news_reference_id=reference.id,
            event_id=event.id,
            claim_type="PRIMARY",
            claim_text=primary_claim,
            normalized_claim=normalized_claim,
            claim_fingerprint=claim_fingerprint,
            certainty_level=certainty,
            supports_official_record_id=(
                official[0].id if official and not conflicting else None
            ),
            contradicts_official_record_id=official[0].id if conflicting else None,
            verification_status=verification,
        )
        self.repository.create_claim(claim)
        self.session.add(
            EvidenceItemRecord(
                event_id=event.id,
                source_id=source.id,
                source_url=canonical_url,
                source_title=title,
                published_at=item.published_at,
                claim=primary_claim,
                evidence_hash=_hash(f"{source.id}|{item.provider_item_id}|{claim_fingerprint}"),
                independent_origin=independent_origin,
                duplicate=stale_reused or not independent_origin,
            )
        )
        event.news_reference_count += 1
        event.source_count += 1
        event.independent_origin_count = len(existing_origins | {original_origin_key})
        if official:
            event.official_source_count = max(event.official_source_count, len(official))
            event.latest_official_at = max(record.published_at for record in official)
        event.last_seen_at = max(event.last_seen_at, item.published_at)
        event.latest_news_at = max(filter(None, [event.latest_news_at, item.published_at]))
        event.material_change = material_change
        if material_change:
            event.latest_material_change_at = item.published_at
            event.changed_facts = changed_facts
        if stale_reused:
            event.stale_reuse_count += 1
        if lifecycle is LifecycleStatus.CORRECTED:
            event.corrected_at = item.published_at
        if lifecycle is LifecycleStatus.DENIED:
            event.denied_at = item.published_at
        if lifecycle is not LifecycleStatus.STALE:
            event.lifecycle_status = lifecycle
            event.verification_status = verification
        self.session.flush()
        return NewsIngestResult(reference, event, True)

    def _official_match(
        self,
        instrument_id: str,
        claim: str,
        certainty: CertaintyLevel,
    ) -> tuple[list[DisclosureRecord], bool]:
        records = list(
            self.session.scalars(
                select(DisclosureRecord)
                .where(DisclosureRecord.instrument_id == instrument_id)
                .order_by(DisclosureRecord.published_at.desc())
                .limit(20)
            )
        )
        claim_tokens = set(normalize_text(claim).split())
        matched: list[DisclosureRecord] = []
        conflicting = False
        for record in records:
            official_text = " ".join(
                [record.title, record.summary or "", record.report_type or ""]
            )
            official_tokens = set(normalize_text(official_text).split())
            overlap = claim_tokens & official_tokens
            if len(overlap) < 2:
                continue
            matched.append(record)
            official_certainty = certainty_for(official_text)
            if certainty is CertaintyLevel.CONFIRMED and official_certainty in {
                CertaintyLevel.UNDER_REVIEW,
                CertaintyLevel.PROPOSED,
                CertaintyLevel.POSSIBLE,
                CertaintyLevel.SPECULATIVE,
            }:
                conflicting = True
        return matched, conflicting

    @staticmethod
    def _trust_score(
        grade: SourceGrade,
        verification: VerificationStatus,
        independent: bool,
    ) -> int:
        score = {
            SourceGrade.A: 80,
            SourceGrade.B: 65,
            SourceGrade.C: 40,
            SourceGrade.D: 20,
        }[grade]
        if verification is VerificationStatus.OFFICIAL_CONFIRMED:
            score += 15
        elif verification is VerificationStatus.MULTI_SOURCE_CONFIRMED:
            score += 10
        elif verification in {
            VerificationStatus.CONFLICTING,
            VerificationStatus.OFFICIALLY_DENIED,
        }:
            score -= 20
        if independent:
            score += 5
        return min(100, max(0, score))


class ImportantInformationImportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preview(
        self,
        *,
        source_url: str,
        publisher_name: str,
        portfolio_item_id: str,
    ) -> ImportantInformationImportPlan:
        canonical_url = canonicalize_url(source_url)
        parsed = urlsplit(canonical_url)
        source_domain = (parsed.hostname or "").removeprefix("www.")
        portfolio_item = self.session.get(PortfolioItemRecord, portfolio_item_id)
        if portfolio_item is None or portfolio_item.archived_at is not None:
            raise ValueError("등록된 보유·관심 종목을 찾을 수 없습니다.")

        instrument = self._instrument_for(portfolio_item)
        sources = list(
            self.session.scalars(
                select(SourceRecord).where(SourceRecord.domain == source_domain)
            )
        )
        classification_source = next(
            (source for source in sources if source.official),
            sources[0] if sources else None,
        )
        manual_source = next(
            (
                source
                for source in sources
                if source.provider_type == NewsProviderType.MANUAL_REFERENCE.value
            ),
            None,
        )
        source_grade, official_source = self._classification(
            canonical_url=canonical_url,
            classification_source=classification_source,
        )
        duplicate = NewsRepository(self.session).by_url_hash(_hash(canonical_url))
        warnings: list[str] = []
        if canonical_url != source_url.strip():
            warnings.append("URL_NORMALIZED")
        if duplicate is not None:
            warnings.append("DUPLICATE_CANONICAL_URL")
        if manual_source is None:
            warnings.append("MANUAL_SOURCE_WILL_BE_CREATED")
        if instrument is None:
            warnings.append("INSTRUMENT_WILL_BE_CREATED")
        warnings.append(
            "OFFICIAL_SOURCE_MATCHED"
            if official_source
            else "NON_OFFICIAL_SOURCE_REQUIRES_REVIEW"
        )
        if classification_source is None:
            warnings.append("SOURCE_GRADE_INFERRED_FROM_PUBLIC_METADATA")

        del publisher_name
        return ImportantInformationImportPlan(
            portfolio_item=portfolio_item,
            instrument=instrument,
            classification_source=classification_source,
            manual_source=manual_source,
            canonical_url=canonical_url,
            source_domain=source_domain,
            source_grade=source_grade,
            official_source=official_source,
            duplicate=duplicate,
            would_create_source=manual_source is None,
            would_create_instrument=instrument is None,
            validation_warnings=tuple(warnings),
        )

    def confirm(
        self,
        *,
        source_url: str,
        publisher_name: str,
        title: str,
        published_at: datetime,
        primary_claim: str,
        public_summary: str | None,
        portfolio_item_id: str,
        language: str,
        material_change: bool,
    ) -> ImportantInformationImportResult:
        plan = self.preview(
            source_url=source_url,
            publisher_name=publisher_name,
            portfolio_item_id=portfolio_item_id,
        )
        if plan.duplicate is not None:
            raise ValueError("동일한 공개 링크로 등록된 중요 정보가 이미 있습니다.")

        current = SystemClock().now()
        instrument_created = plan.instrument is None
        instrument = plan.instrument or self._create_instrument(
            plan.portfolio_item,
            now=current,
        )
        if plan.portfolio_item.instrument_id != instrument.id:
            plan.portfolio_item.instrument_id = instrument.id
            plan.portfolio_item.updated_at = current

        source_created = plan.manual_source is None
        source = plan.manual_source or SourceRecord(
            name=publisher_name,
            source_type="MANUAL_NEWS",
            source_grade=plan.source_grade,
            domain=plan.source_domain,
            official=plan.official_source,
            enabled=True,
            feed_url=None,
            provider_type=NewsProviderType.MANUAL_REFERENCE.value,
            language=language,
            request_interval_seconds=21600,
            timeout_seconds=20,
            max_items=30,
            original_source_name=publisher_name,
        )
        if source_created:
            self.session.add(source)
            self.session.flush()

        item = NewsFeedItem(
            provider_item_id=f"manual-{_hash(plan.canonical_url)[:64]}",
            title=title,
            original_url=plan.canonical_url,
            published_at=published_at,
            source_updated_at=None,
            snippet=primary_claim,
        )
        ingest = NewsService(self.session).ingest(
            source=source,
            instrument=instrument,
            item=item,
            portfolio_item_id=plan.portfolio_item.id,
            now=current,
        )
        changed_facts = (
            [{"field": "primaryClaim", "value": primary_claim}] if material_change else []
        )
        ingest.reference.short_summary = (
            public_summary
            or f"{publisher_name} 공개 정보에서 확인한 핵심 주장입니다. "
            "공식 자료 또는 복수 독립 출처와의 추가 검증이 필요합니다."
        )[:1000]
        ingest.reference.summary_status = NewsSummaryStatus.MANUAL_REVIEW_REQUIRED
        ingest.reference.material_change = material_change
        ingest.reference.changed_facts = changed_facts
        ingest.event.current_summary = public_summary or primary_claim
        ingest.event.material_change = material_change
        if material_change:
            ingest.event.latest_material_change_at = published_at
            ingest.event.changed_facts = changed_facts
        self.session.flush()
        return ImportantInformationImportResult(
            ingest=ingest,
            source_created=source_created,
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
            verification_source="USER_REGISTERED_PORTFOLIO",
            verified_at=now,
        )
        self.session.add(instrument)
        self.session.flush()
        return instrument

    def _classification(
        self,
        *,
        canonical_url: str,
        classification_source: SourceRecord | None,
    ) -> tuple[SourceGrade, bool]:
        if classification_source is not None:
            return (
                classification_source.source_grade,
                bool(classification_source.official),
            )
        analyst_reference = self.session.scalar(
            select(AnalystReferenceRecord).where(
                AnalystReferenceRecord.canonical_url == canonical_url
            )
        )
        if analyst_reference is not None and analyst_reference.publisher_type.value in {
            "BROKER",
            "RESEARCH_HOUSE",
            "FINANCIAL_MEDIA",
            "INSTITUTION",
        }:
            return SourceGrade.B, False
        return SourceGrade.C, False

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


class NewsSyncService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def sync(
        self,
        *,
        source_id: str | None = None,
        instrument_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        now: datetime | None = None,
        operating_mode: OperatingMode = OperatingMode.NORMAL,
    ) -> dict[str, int | str]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        sources = list(
            self.session.scalars(
                select(SourceRecord).where(
                    SourceRecord.enabled.is_(True),
                    SourceRecord.feed_url.is_not(None),
                    SourceRecord.provider_type.in_(
                        {
                            NewsProviderType.RSS.value,
                            NewsProviderType.ATOM.value,
                            NewsProviderType.OFFICIAL_IR_FEED.value,
                        }
                    ),
                    *([SourceRecord.id == source_id] if source_id else []),
                )
            )
        )
        if (
            not self.settings.news_sync_enabled
            or not self.settings.news_feed_sync_enabled
            or not sources
        ):
            return {"status": "NOT_CONFIGURED", "fetched": 0, "created": 0}
        candidates = self._eligible_instruments(instrument_id, operating_mode)
        fetched = created = duplicates = errors = 0
        for source in sources:
            cursor = self.session.get(
                ProviderCursorRecord,
                {
                    "provider": ProviderName.SYSTEM_BASELINE,
                    "scope": f"news:{source.id}",
                },
            )
            overlap = since or (
                cursor.last_successful_at - timedelta(days=1)
                if cursor and cursor.last_successful_at
                else current - timedelta(days=7)
            )
            result = NewsFeedProvider(self.settings, source).fetch(limit=limit)
            if result.status is not ProviderStatus.READY:
                errors += 1
                continue
            for item in result.items:
                if item.published_at < overlap:
                    continue
                fetched += 1
                match = self._match(item, candidates)
                if match is None:
                    continue
                if dry_run:
                    continue
                instrument, portfolio_id = match
                ingest = NewsService(self.session).ingest(
                    source=source,
                    instrument=instrument,
                    item=item,
                    portfolio_item_id=portfolio_id,
                    now=current,
                )
                created += int(ingest.created)
                duplicates += int(not ingest.created)
            if not dry_run:
                if cursor is None:
                    cursor = ProviderCursorRecord(
                        provider=ProviderName.SYSTEM_BASELINE,
                        scope=f"news:{source.id}",
                    )
                    self.session.add(cursor)
                cursor.last_attempt_at = current
                cursor.last_successful_at = current
                cursor.overlap_window_start = overlap
                cursor.cursor_value = current.isoformat()
        status = "DRY_RUN" if dry_run else ("FAILED" if errors and not fetched else "SUCCEEDED")
        output = {
            "status": status,
            "fetched": fetched,
            "created": created,
            "duplicates": duplicates,
            "errors": errors,
        }
        if not dry_run:
            self.session.add(
                CollectionRunRecord(
                    provider=ProviderName.SYSTEM_BASELINE,
                    run_type=CollectionRunType.NEWS_SYNC,
                    started_at=current,
                    finished_at=current,
                    status=(
                        CollectionStatus.FAILED
                        if status == "FAILED"
                        else CollectionStatus.SUCCEEDED
                    ),
                    fetched_count=fetched,
                    created_count=created,
                    duplicate_count=duplicates,
                    error_count=errors,
                    result_details=output,
                )
            )
            self.session.flush()
        return output

    def _eligible_instruments(
        self,
        instrument_id: str | None,
        operating_mode: OperatingMode = OperatingMode.NORMAL,
    ) -> list[tuple[InstrumentRecord, str]]:
        statuses = (
            {HoldingStatus.HOLDING}
            if operating_mode
            in {
                OperatingMode.SAVING,
                OperatingMode.MINIMAL,
                OperatingMode.PAUSED,
            }
            else {
                HoldingStatus.HOLDING,
                HoldingStatus.WATCHLIST,
                HoldingStatus.REENTRY_WATCH,
            }
        )
        if self.settings.include_sold_in_news_sync:
            statuses.add(HoldingStatus.SOLD)
        statement = (
            select(InstrumentRecord, PortfolioItemRecord.id)
            .join(
                PortfolioItemRecord,
                PortfolioItemRecord.instrument_id == InstrumentRecord.id,
            )
            .where(
                InstrumentRecord.active.is_(True),
                InstrumentRecord.verification_status == InstrumentVerificationStatus.VERIFIED,
                PortfolioItemRecord.archived_at.is_(None),
                PortfolioItemRecord.holding_status.in_(statuses),
            )
        )
        if instrument_id:
            statement = statement.where(InstrumentRecord.id == instrument_id)
        return list(self.session.execute(statement).tuples())

    def _match(
        self,
        item: NewsFeedItem,
        candidates: list[tuple[InstrumentRecord, str]],
    ) -> tuple[InstrumentRecord, str] | None:
        text = normalize_text(f"{item.title} {item.snippet or ''}")
        if any(term in text for term in ("sponsored", "advertisement", "광고")):
            return None
        for instrument, portfolio_id in candidates:
            terms = {
                normalize_text(instrument.canonical_symbol),
                normalize_text(instrument.display_name),
                normalize_text(instrument.local_name or ""),
            }
            watch = self.session.scalar(
                select(WatchEntityRecord).where(
                    WatchEntityRecord.symbol == instrument.canonical_symbol
                )
            )
            if watch:
                terms.update(normalize_text(value) for value in watch.aliases)
            if any(term and term in text for term in terms):
                return instrument, portfolio_id
        return None
