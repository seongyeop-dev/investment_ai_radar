from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, not_, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.database import (
    HoldingStatus,
    PortfolioItemRecord,
    PositionStatus,
    TrackingStatus,
)
from app.models.disclosures import (
    CollectionRunRecord,
    CollectionRunType,
    CollectionStatus,
    DisclosureRecord,
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    ProviderCursorRecord,
    ProviderName,
    ProviderStatus,
)
from app.models.market_data import ProviderSyncStateRecord
from app.providers.common import ProviderDisclosure
from app.providers.opendart import OpenDartProvider
from app.providers.sec import SecEdgarProvider
from app.repositories.disclosures import DisclosureRepository
from app.services.disclosures import (
    DisclosureIngest,
    DisclosureService,
    canonical_official_url,
)


def _event_metadata(
    disclosure: ProviderDisclosure,
) -> tuple[str, str, str, list[dict[str, str]], bool, bool]:
    title = disclosure.title.strip()
    normalized = title.lower()
    denied = "공식 부인" in title or "부인 공시" in title
    classifications = (
        ("정정", "CORRECTION"),
        ("실적전망", "GUIDANCE_CHANGE"),
        ("영업실적", "EARNINGS"),
        ("잠정실적", "EARNINGS"),
        ("단일판매", "MAJOR_CONTRACT"),
        ("공급계약", "MAJOR_CONTRACT"),
        ("계약해지", "CONTRACT_TERMINATION"),
        ("유상증자", "EQUITY_FINANCING"),
        ("전환사채", "CONVERTIBLE_BOND"),
        ("인수", "ACQUISITION_OR_DISPOSAL"),
        ("매각", "ACQUISITION_OR_DISPOSAL"),
        ("대표이사", "MANAGEMENT_CHANGE"),
        ("감사의견", "AUDIT_OR_ACCOUNTING"),
        ("상장폐지", "LISTING_RISK"),
        ("소송", "LITIGATION_OR_REGULATION"),
        ("배당", "DIVIDEND"),
    )
    event_type = next(
        (value for keyword, value in classifications if keyword.lower() in normalized),
        {
            "8-K": "CURRENT_REPORT",
            "10-K": "ANNUAL_REPORT",
            "10-Q": "QUARTERLY_REPORT",
            "6-K": "FOREIGN_CURRENT_REPORT",
            "20-F": "FOREIGN_ANNUAL_REPORT",
            "40-F": "CANADIAN_ANNUAL_REPORT",
        }.get((disclosure.form_type or "").removesuffix("/A"), "OFFICIAL_DISCLOSURE"),
    )
    if denied:
        event_type = "OFFICIAL_DENIAL"
    form = (disclosure.form_type or "").upper()
    form_labels = {
        "10-Q": "10-Q 분기보고서",
        "10-Q/A": "10-Q/A 정정 분기보고서",
        "10-K": "10-K 연차보고서",
        "10-K/A": "10-K/A 정정 연차보고서",
        "8-K": "8-K 주요사항보고",
        "8-K/A": "8-K/A 정정 주요사항보고",
        "6-K": "6-K 외국기업보고",
        "6-K/A": "6-K/A 정정 외국기업보고",
        "20-F": "20-F 외국기업 연차보고서",
        "20-F/A": "20-F/A 정정 외국기업 연차보고서",
    }
    report_name = form_labels.get(form)
    if report_name is None:
        report_name = re.sub(
            rf"^\s*{re.escape(disclosure.company_name)}\s*[\-|:]\s*",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()
        report_name = re.sub(r"\s*\|\s*", " | ", report_name)
        pieces = []
        for piece in report_name.split(" | "):
            if piece and piece.casefold() not in {value.casefold() for value in pieces}:
                pieces.append(piece)
        report_name = " | ".join(pieces) or disclosure.report_type or "공식 공시"
    display_title = f"{disclosure.company_name} | {report_name}"
    core_event_types = {
        "CORRECTION",
        "GUIDANCE_CHANGE",
        "EARNINGS",
        "MAJOR_CONTRACT",
        "CONTRACT_TERMINATION",
        "EQUITY_FINANCING",
        "CONVERTIBLE_BOND",
        "ACQUISITION_OR_DISPOSAL",
        "MANAGEMENT_CHANGE",
        "AUDIT_OR_ACCOUNTING",
        "LISTING_RISK",
        "LITIGATION_OR_REGULATION",
        "DIVIDEND",
        "CURRENT_REPORT",
        "QUARTERLY_REPORT",
        "ANNUAL_REPORT",
        "FOREIGN_CURRENT_REPORT",
        "FOREIGN_ANNUAL_REPORT",
        "OFFICIAL_DENIAL",
    }
    material = event_type in core_event_types
    summary = f"{display_title}가 확인됐습니다. " + (
        "투자 영향 방향은 별도 확인이 필요합니다."
        if material
        else "참고 공시이며 투자 영향은 확인되지 않았습니다."
    )
    key_facts = [
        {"field": "provider", "value": disclosure.provider.value},
        {
            "field": "formOrReportType",
            "value": disclosure.form_type or disclosure.report_type or "공시",
        },
        {"field": "analysisImportance", "value": "CORE" if material else "REFERENCE"},
    ]
    return event_type, display_title, summary, key_facts, denied, material


class OfficialDisclosureSyncService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def sync(
        self,
        provider: ProviderName,
        *,
        since: datetime | None = None,
        instrument_id: str | None = None,
        portfolio_id: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> dict[str, int | str]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        bounded_limit = min(max(limit, 1), 50)
        configured = self.settings.official_disclosure_sync_enabled and (
            self.settings.open_dart_configured
            if provider is ProviderName.OPENDART
            else self.settings.sec_configured
        )
        if not configured:
            return {
                "status": "NOT_CONFIGURED",
                "fetched": 0,
                "created": 0,
                "duplicates": 0,
                "requestCount": 0,
                "failed": 0,
            }
        mappings = self._eligible_mappings(
            provider,
            instrument_id,
            portfolio_id=portfolio_id,
            symbol=symbol,
        )
        fetched = 0
        created = 0
        duplicates = 0
        request_count = 0
        failed = 0
        successful_mappings = 0
        last_failure_status: ProviderStatus | None = None
        last_error_code: str | None = None
        if not mappings:
            return {
                "status": "NO_ELIGIBLE_MAPPINGS",
                "fetched": 0,
                "created": 0,
                "duplicates": 0,
                "requestCount": 0,
                "failed": 0,
            }
        cursor = self.session.get(
            ProviderCursorRecord,
            {"provider": provider, "scope": "official-disclosures"},
        )
        overlap_start = since or (
            cursor.last_successful_at - timedelta(days=1)
            if cursor and cursor.last_successful_at
            else current - timedelta(days=30)
        )
        provider_client = (
            OpenDartProvider(self.settings)
            if provider is ProviderName.OPENDART
            else SecEdgarProvider(self.settings)
        )
        service = DisclosureService(DisclosureRepository(self.session))
        for mapping in mappings:
            if fetched >= bounded_limit:
                break
            mapping_limit = min(10, bounded_limit - fetched)
            if provider is ProviderName.OPENDART:
                result = provider_client.fetch_disclosures(
                    corp_code=mapping.corp_code or "",
                    published_from=overlap_start,
                    published_to=current,
                    limit=mapping_limit,
                )
            else:
                result = provider_client.fetch_submissions(
                    mapping.cik or "", limit=mapping_limit
                )
            request_count += result.request_count
            if result.status is not ProviderStatus.READY:
                failed += 1
                last_failure_status = result.status
                last_error_code = result.error_code
                continue
            successful_mappings += 1
            for disclosure in result.disclosures:
                if not overlap_start <= disclosure.published_at <= current:
                    continue
                fetched += 1
                duplicate = service.repository.find_duplicate(
                    provider,
                    disclosure.provider_document_id,
                    canonical_official_url(disclosure.official_url),
                )
                if duplicate is not None:
                    duplicates += 1
                    if dry_run:
                        continue
                elif dry_run:
                    created += 1
                    continue
                correction_id = (
                    self._correction_target(mapping.instrument_id, disclosure.form_type)
                    if disclosure.amendment
                    else None
                )
                (
                    event_type,
                    display_title,
                    summary,
                    key_facts,
                    denied,
                    material,
                ) = _event_metadata(disclosure)
                _, _, was_created = service.ingest(
                    DisclosureIngest(
                        instrument_id=mapping.instrument_id,
                        provider=provider,
                        provider_document_id=disclosure.provider_document_id,
                        accession_number=disclosure.accession_number,
                        receipt_number=disclosure.receipt_number,
                        form_type=disclosure.form_type,
                        report_type=disclosure.report_type,
                        title=disclosure.title,
                        company_name=disclosure.company_name,
                        official_url=disclosure.official_url,
                        published_at=disclosure.published_at,
                        source_updated_at=disclosure.source_updated_at,
                        event_type=event_type,
                        claim=display_title,
                        summary=summary,
                        key_facts=key_facts,
                        correction_of_document_id=correction_id,
                        denied=denied,
                        material_change=material,
                    ),
                    now=current,
                )
                created += int(was_created)
                if duplicate is None:
                    duplicates += int(not was_created)
        status = (
            last_failure_status.value
            if successful_mappings == 0 and last_failure_status is not None
            else "PARTIAL"
            if failed
            else "DRY_RUN"
            if dry_run
            else "SUCCEEDED"
        )
        output = {
            "status": status,
            "fetched": fetched,
            "created": created,
            "duplicates": duplicates,
            "requestCount": request_count,
            "failed": failed,
        }
        if not dry_run:
            before = cursor.cursor_value if cursor else None
            if cursor is None:
                cursor = ProviderCursorRecord(provider=provider, scope="official-disclosures")
                self.session.add(cursor)
            cursor.last_attempt_at = current
            cursor.overlap_window_start = overlap_start
            if successful_mappings:
                cursor.cursor_value = current.isoformat()
                cursor.last_successful_at = current
            self.session.add(
                CollectionRunRecord(
                    provider=provider,
                    run_type=CollectionRunType.DISCLOSURE_SYNC,
                    started_at=current,
                    finished_at=current,
                    status=(
                        CollectionStatus.SUCCEEDED
                        if successful_mappings
                        else CollectionStatus.FAILED
                    ),
                    fetched_count=fetched,
                    created_count=created,
                    duplicate_count=duplicates,
                    cursor_before=before,
                    error_count=failed,
                    cursor_after=cursor.cursor_value,
                    result_details=output,
                )
            )
            state = self.session.get(
                ProviderSyncStateRecord,
                {
                    "provider": provider.value,
                    "capability": "OFFICIAL_DISCLOSURE",
                },
            )
            if state is None:
                state = ProviderSyncStateRecord(
                    provider=provider.value,
                    capability="OFFICIAL_DISCLOSURE",
                    configured=True,
                    status=status,
                )
                self.session.add(state)
            state.configured = True
            state.status = (
                ProviderStatus.READY.value if successful_mappings and not failed else status
            )
            state.last_attempt_at = current
            state.request_count = int(state.request_count or 0) + request_count
            if successful_mappings:
                state.last_success_at = current
                state.last_error_code = None
                state.consecutive_failures = 0
                state.success_count = int(state.success_count or 0) + successful_mappings
            else:
                state.last_error_code = last_error_code
                state.consecutive_failures = int(state.consecutive_failures or 0) + 1
            self.session.flush()
        return output

    def reprocess_existing(self, *, dry_run: bool = False) -> dict[str, int | str]:
        """Rebuild generated event metadata without changing raw provider metadata."""
        records = list(
            self.session.scalars(
                select(DisclosureRecord).order_by(
                    DisclosureRecord.event_id,
                    DisclosureRecord.published_at,
                    DisclosureRecord.id,
                )
            )
        )
        event_plans: dict[str, tuple[str, str, str, bool, datetime]] = {}
        titles_changed = 0
        classifications_changed = 0
        core_count = 0
        reference_count = 0

        for record in records:
            disclosure = ProviderDisclosure(
                provider=record.provider,
                provider_document_id=record.provider_document_id,
                accession_number=record.accession_number,
                receipt_number=record.receipt_number,
                form_type=record.form_type,
                report_type=record.report_type,
                title=record.title,
                company_name=record.company_name,
                official_url=record.official_url,
                published_at=record.published_at,
                source_updated_at=record.source_updated_at,
                primary_document=None,
                amendment=(record.form_type or "").endswith("/A"),
            )
            (
                event_type,
                display_title,
                summary,
                key_facts,
                _denied,
                material,
            ) = _event_metadata(disclosure)
            core_count += int(material)
            reference_count += int(not material)
            titles_changed += int(record.summary != summary)
            classifications_changed += int(
                record.material_change != material or record.key_facts != key_facts
            )
            if not dry_run:
                record.summary = summary
                record.key_facts = key_facts
                record.material_change = material

            previous = event_plans.get(record.event_id)
            if previous is None:
                event_plans[record.event_id] = (
                    event_type,
                    display_title,
                    summary,
                    material,
                    record.published_at,
                )
            else:
                previous_type, previous_title, previous_summary, previous_material, at = (
                    previous
                )
                if record.published_at >= at:
                    event_plans[record.event_id] = (
                        event_type,
                        display_title,
                        summary,
                        previous_material or material,
                        record.published_at,
                    )
                elif material and not previous_material:
                    event_plans[record.event_id] = (
                        previous_type,
                        previous_title,
                        previous_summary,
                        True,
                        at,
                    )

        events_changed = 0
        repository = DisclosureRepository(self.session)
        for event_id, plan in event_plans.items():
            event = repository.get_event(event_id)
            if event is None:
                continue
            event_type, display_title, summary, material, _published_at = plan
            changed = (
                event.event_type != event_type
                or event.normalized_claim != display_title
                or event.current_summary != summary
                or event.material_change != material
            )
            events_changed += int(changed)
            if not dry_run and changed:
                event.event_type = event_type
                event.normalized_claim = display_title
                event.current_summary = summary
                event.material_change = material

        if not dry_run:
            self.session.flush()
        return {
            "status": "DRY_RUN" if dry_run else "SUCCEEDED",
            "processed": len(records),
            "core": core_count,
            "reference": reference_count,
            "titlesChanged": titles_changed,
            "classificationsChanged": classifications_changed,
            "eventsChanged": events_changed,
            "providerRequests": 0,
        }

    def _eligible_mappings(
        self,
        provider: ProviderName,
        instrument_id: str | None,
        *,
        portfolio_id: str | None = None,
        symbol: str | None = None,
    ) -> list[InstrumentProviderMappingRecord]:
        statuses = {
            HoldingStatus.HOLDING,
            HoldingStatus.WATCHLIST,
            HoldingStatus.REENTRY_WATCH,
        }
        if self.settings.include_sold_in_disclosure_sync:
            statuses.add(HoldingStatus.SOLD)
        statement = (
            select(InstrumentProviderMappingRecord)
            .join(
                InstrumentRecord,
                InstrumentRecord.id == InstrumentProviderMappingRecord.instrument_id,
            )
            .join(
                PortfolioItemRecord,
                or_(
                    PortfolioItemRecord.instrument_id == InstrumentRecord.id,
                    (PortfolioItemRecord.market == InstrumentRecord.market)
                    & (PortfolioItemRecord.symbol == InstrumentRecord.canonical_symbol),
                ),
            )
            .where(
                InstrumentProviderMappingRecord.provider == provider,
                InstrumentProviderMappingRecord.active.is_(True),
                InstrumentProviderMappingRecord.mapping_status == "VERIFIED",
                InstrumentRecord.active.is_(True),
                InstrumentRecord.verification_status == InstrumentVerificationStatus.VERIFIED,
                PortfolioItemRecord.archived_at.is_(None),
                or_(
                    PortfolioItemRecord.position_status == PositionStatus.HOLDING,
                    PortfolioItemRecord.tracking_status.in_(
                        {TrackingStatus.REENTRY_WATCH, TrackingStatus.WATCHLIST}
                    ),
                    PortfolioItemRecord.holding_status.in_(statuses),
                ),
                not_(
                    and_(
                        PortfolioItemRecord.position_status == PositionStatus.CLOSED,
                        PortfolioItemRecord.tracking_status == TrackingStatus.NONE,
                    )
                ),
            )
            .order_by(
                case(
                    (PortfolioItemRecord.position_status == PositionStatus.HOLDING, 0),
                    (
                        PortfolioItemRecord.tracking_status == TrackingStatus.REENTRY_WATCH,
                        1,
                    ),
                    (PortfolioItemRecord.tracking_status == TrackingStatus.WATCHLIST, 2),
                    (PortfolioItemRecord.holding_status == HoldingStatus.HOLDING, 3),
                    (
                        PortfolioItemRecord.holding_status == HoldingStatus.REENTRY_WATCH,
                        4,
                    ),
                    (PortfolioItemRecord.holding_status == HoldingStatus.WATCHLIST, 5),
                    else_=99,
                ),
                PortfolioItemRecord.market,
                PortfolioItemRecord.symbol,
            )
        )
        if instrument_id:
            statement = statement.where(InstrumentRecord.id == instrument_id)
        if portfolio_id:
            statement = statement.where(PortfolioItemRecord.id == portfolio_id)
        if symbol:
            statement = statement.where(PortfolioItemRecord.symbol == symbol.strip().upper())
        mappings: list[InstrumentProviderMappingRecord] = []
        seen: set[str] = set()
        for mapping in self.session.scalars(statement):
            if mapping.id in seen:
                continue
            seen.add(mapping.id)
            mappings.append(mapping)
            if len(mappings) == 3:
                break
        return mappings

    def _correction_target(self, instrument_id: str, form_type: str | None) -> str | None:
        base_form = (form_type or "").removesuffix("/A")
        record = self.session.scalar(
            select(DisclosureRecord)
            .where(
                DisclosureRecord.instrument_id == instrument_id,
                DisclosureRecord.form_type == base_form,
            )
            .order_by(DisclosureRecord.published_at.desc())
            .limit(1)
        )
        return record.provider_document_id if record else None
