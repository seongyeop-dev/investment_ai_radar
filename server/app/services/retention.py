from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import require_aware_utc
from app.models.disclosures import (
    CollectionRunRecord,
    CollectionRunType,
    CollectionStatus,
    DisclosureRecord,
    EvidenceItemRecord,
    InformationEventRecord,
    LifecycleStatus,
    NewsReferenceRecord,
    ProviderName,
    TemporaryDocumentRecord,
)
from app.models.market_data import QuoteSnapshotRecord
from app.models.operations import (
    BriefingItemRecord,
    BriefingRecord,
    NotificationDeliveryRecord,
)

IMPORTANT_FORMS = {
    "10-K",
    "10-Q",
    "8-K",
    "20-F",
    "6-K",
    "ANNUAL_REPORT",
    "CORRECTION",
}


@dataclass(frozen=True, slots=True)
class RetentionResult:
    status: str
    temporary_documents: int
    collection_logs: int
    duplicate_evidence: int
    general_summaries: int
    event_fingerprints: int
    duplicate_news: int
    general_news_summaries: int
    briefing_records: int
    notification_deliveries: int
    quote_snapshots: int

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


class RetentionService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def run(
        self, *, now: datetime, dry_run: bool = True, confirm: bool = False
    ) -> RetentionResult:
        now = require_aware_utc(now)
        candidates = self._candidates(now)
        if dry_run:
            return RetentionResult(status="DRY_RUN", **candidates)
        if not self.settings.retention_cleanup_enabled or not confirm:
            return RetentionResult(status="NOT_CONFIGURED", **candidates)
        run = CollectionRunRecord(
            provider=ProviderName.SYSTEM_BASELINE,
            run_type=CollectionRunType.RETENTION_CLEANUP,
            started_at=now,
            status=CollectionStatus.RUNNING,
            result_details={},
        )
        self.session.add(run)
        self.session.flush()
        try:
            self.session.execute(
                delete(TemporaryDocumentRecord).where(TemporaryDocumentRecord.expires_at <= now)
            )
            self.session.execute(
                delete(QuoteSnapshotRecord).where(QuoteSnapshotRecord.expires_at <= now)
            )
            log_cutoff = now - timedelta(days=self.settings.collection_log_retention_days)
            self.session.execute(
                delete(CollectionRunRecord).where(
                    CollectionRunRecord.created_at < log_cutoff,
                    CollectionRunRecord.id != run.id,
                )
            )
            evidence_cutoff = now - timedelta(
                days=self.settings.duplicate_evidence_retention_days
            )
            self.session.execute(
                delete(EvidenceItemRecord).where(
                    EvidenceItemRecord.duplicate.is_(True),
                    EvidenceItemRecord.pinned.is_(False),
                    EvidenceItemRecord.created_at < evidence_cutoff,
                )
            )
            summary_cutoff = now - timedelta(days=self.settings.general_summary_retention_days)
            self.session.execute(
                update(DisclosureRecord)
                .where(
                    DisclosureRecord.updated_at < summary_cutoff,
                    DisclosureRecord.pinned.is_(False),
                    DisclosureRecord.correction_of_id.is_(None),
                    or_(
                        DisclosureRecord.form_type.is_(None),
                        DisclosureRecord.form_type.not_in(IMPORTANT_FORMS),
                    ),
                    DisclosureRecord.summary.is_not(None),
                )
                .values(summary=None, key_facts=[])
            )
            news_cutoff = now - timedelta(days=self.settings.duplicate_evidence_retention_days)
            self.session.execute(
                update(NewsReferenceRecord)
                .where(
                    NewsReferenceRecord.updated_at < news_cutoff,
                    NewsReferenceRecord.pinned.is_(False),
                    NewsReferenceRecord.material_change.is_(False),
                    NewsReferenceRecord.lifecycle_status.not_in(
                        {
                            LifecycleStatus.ACTIVE,
                            LifecycleStatus.CORRECTED,
                            LifecycleStatus.DENIED,
                        }
                    ),
                )
                .values(snippet=None, short_summary=None, changed_facts=[])
            )
            briefing_cutoff = now - timedelta(
                days=self.settings.important_briefing_retention_days
            )
            expired_briefings = list(
                self.session.scalars(
                    select(BriefingRecord).where(BriefingRecord.updated_at < briefing_cutoff)
                )
            )
            for briefing in expired_briefings:
                items = list(
                    self.session.scalars(
                        select(BriefingItemRecord).where(
                            BriefingItemRecord.briefing_id == briefing.id
                        )
                    )
                )
                protected = any(
                    item.category in {"CORRECTION", "DENIAL"}
                    or bool(
                        (
                            self.session.get(
                                InformationEventRecord,
                                item.information_event_id,
                            )
                        ).pinned
                    )
                    for item in items
                )
                if protected:
                    continue
                self.session.execute(
                    delete(NotificationDeliveryRecord).where(
                        NotificationDeliveryRecord.briefing_id == briefing.id
                    )
                )
                self.session.execute(
                    delete(BriefingItemRecord).where(
                        BriefingItemRecord.briefing_id == briefing.id
                    )
                )
                self.session.delete(briefing)
            fingerprint_cutoff = now - timedelta(
                days=self.settings.event_fingerprint_retention_days
            )
            expired_events = self.session.scalars(
                select(InformationEventRecord).where(
                    InformationEventRecord.updated_at < fingerprint_cutoff,
                    InformationEventRecord.pinned.is_(False),
                    InformationEventRecord.lifecycle_status.in_(
                        {LifecycleStatus.ARCHIVED, LifecycleStatus.STALE}
                    ),
                )
            )
            for event in expired_events:
                event.normalized_claim = ""
                event.current_summary = None
                event.claim_fingerprint = hashlib.sha256(
                    f"expired:{event.id}".encode()
                ).hexdigest()
            run.status = CollectionStatus.SUCCEEDED
            run.finished_at = now
            run.result_details = candidates
            run.updated_count = candidates["general_summaries"]
            run.duplicate_count = candidates["duplicate_evidence"]
            self.session.flush()
        except Exception:
            self.session.rollback()
            raise
        return RetentionResult(status="SUCCEEDED", **candidates)

    def _candidates(self, now: datetime) -> dict[str, int]:
        def count(statement: object) -> int:
            return len(list(self.session.scalars(statement)))

        log_cutoff = now - timedelta(days=self.settings.collection_log_retention_days)
        evidence_cutoff = now - timedelta(days=self.settings.duplicate_evidence_retention_days)
        summary_cutoff = now - timedelta(days=self.settings.general_summary_retention_days)
        fingerprint_cutoff = now - timedelta(
            days=self.settings.event_fingerprint_retention_days
        )
        briefing_cutoff = now - timedelta(days=self.settings.important_briefing_retention_days)
        expired_briefing_ids: list[str] = []
        expired_delivery_count = 0
        for briefing in self.session.scalars(
            select(BriefingRecord).where(BriefingRecord.updated_at < briefing_cutoff)
        ):
            items = list(
                self.session.scalars(
                    select(BriefingItemRecord).where(
                        BriefingItemRecord.briefing_id == briefing.id
                    )
                )
            )
            if any(
                item.category in {"CORRECTION", "DENIAL"}
                or bool(
                    (
                        self.session.get(
                            InformationEventRecord,
                            item.information_event_id,
                        )
                    ).pinned
                )
                for item in items
            ):
                continue
            expired_briefing_ids.append(briefing.id)
            expired_delivery_count += count(
                select(NotificationDeliveryRecord.id).where(
                    NotificationDeliveryRecord.briefing_id == briefing.id
                )
            )
        return {
            "temporary_documents": count(
                select(TemporaryDocumentRecord.id).where(
                    TemporaryDocumentRecord.expires_at <= now
                )
            ),
            "collection_logs": count(
                select(CollectionRunRecord.id).where(
                    CollectionRunRecord.created_at < log_cutoff
                )
            ),
            "duplicate_evidence": count(
                select(EvidenceItemRecord.id).where(
                    EvidenceItemRecord.duplicate.is_(True),
                    EvidenceItemRecord.pinned.is_(False),
                    EvidenceItemRecord.created_at < evidence_cutoff,
                )
            ),
            "general_summaries": count(
                select(DisclosureRecord.id).where(
                    DisclosureRecord.updated_at < summary_cutoff,
                    DisclosureRecord.pinned.is_(False),
                    DisclosureRecord.correction_of_id.is_(None),
                    or_(
                        DisclosureRecord.form_type.is_(None),
                        DisclosureRecord.form_type.not_in(IMPORTANT_FORMS),
                    ),
                    DisclosureRecord.summary.is_not(None),
                )
            ),
            "event_fingerprints": count(
                select(InformationEventRecord.id).where(
                    InformationEventRecord.updated_at < fingerprint_cutoff,
                    InformationEventRecord.pinned.is_(False),
                    InformationEventRecord.lifecycle_status.in_(
                        {LifecycleStatus.ARCHIVED, LifecycleStatus.STALE}
                    ),
                )
            ),
            "duplicate_news": count(
                select(NewsReferenceRecord.id).where(
                    NewsReferenceRecord.updated_at < evidence_cutoff,
                    NewsReferenceRecord.duplicate_of_id.is_not(None),
                    NewsReferenceRecord.pinned.is_(False),
                    NewsReferenceRecord.material_change.is_(False),
                )
            ),
            "general_news_summaries": count(
                select(NewsReferenceRecord.id).where(
                    NewsReferenceRecord.updated_at < summary_cutoff,
                    NewsReferenceRecord.short_summary.is_not(None),
                    NewsReferenceRecord.pinned.is_(False),
                    NewsReferenceRecord.material_change.is_(False),
                    NewsReferenceRecord.lifecycle_status.not_in(
                        {
                            LifecycleStatus.ACTIVE,
                            LifecycleStatus.CORRECTED,
                            LifecycleStatus.DENIED,
                        }
                    ),
                )
            ),
            "briefing_records": len(expired_briefing_ids),
            "notification_deliveries": expired_delivery_count,
            "quote_snapshots": count(
                select(QuoteSnapshotRecord.id).where(QuoteSnapshotRecord.expires_at <= now)
            ),
        }
