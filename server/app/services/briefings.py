from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import briefing_not_found
from app.models.contracts import VerificationStatus
from app.models.disclosures import (
    DisclosureRecord,
    InformationEventRecord,
    LifecycleStatus,
    NewsReferenceRecord,
)
from app.models.operations import (
    BriefingItemRecord,
    BriefingRecord,
    BriefingStatus,
    BriefingType,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class BriefingGenerationResult:
    briefing: BriefingRecord
    items: tuple[BriefingItemRecord, ...]
    excluded_duplicates: int


class BriefingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, briefing_id: str) -> BriefingRecord:
        record = self.session.get(BriefingRecord, briefing_id)
        if record is None:
            raise briefing_not_found()
        return record

    def items(self, briefing_id: str) -> list[BriefingItemRecord]:
        return list(
            self.session.scalars(
                select(BriefingItemRecord)
                .where(BriefingItemRecord.briefing_id == briefing_id)
                .order_by(
                    BriefingItemRecord.priority.desc(),
                    BriefingItemRecord.published_at.desc(),
                )
            )
        )

    def generate(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
        now: datetime,
        briefing_type: BriefingType = BriefingType.CHANGE_BRIEFING,
        minimum_priority: int = 0,
        persist: bool = True,
        idempotency_key_override: str | None = None,
        preserve_briefing_type: bool = False,
        include_no_change: bool = False,
        provider_complete: bool = True,
    ) -> BriefingGenerationResult:
        events = list(
            self.session.scalars(
                select(InformationEventRecord)
                .where(
                    InformationEventRecord.last_seen_at >= period_start,
                    InformationEventRecord.last_seen_at <= period_end,
                )
                .order_by(InformationEventRecord.last_seen_at.desc())
            )
        )
        eligible_states: list[tuple[InformationEventRecord, int, str]] = []
        for event in events:
            priority = self._priority(event)
            if priority < minimum_priority or not self._eligible(event):
                continue
            fingerprint = self._state_fingerprint(event)
            eligible_states.append((event, priority, fingerprint))
        full_fingerprint = _hash(
            "|".join(sorted(fingerprint for _, _, fingerprint in eligible_states))
            or f"no-change|{period_start.isoformat()}|{period_end.isoformat()}"
        )
        full_key = idempotency_key_override or _hash(
            f"{briefing_type.value}|{full_fingerprint}"
        )
        exact_existing = self.session.scalar(
            select(BriefingRecord).where(BriefingRecord.idempotency_key == full_key)
        )
        if exact_existing is not None:
            return BriefingGenerationResult(
                exact_existing,
                tuple(self.items(exact_existing.id)),
                len(eligible_states),
            )

        candidates: list[tuple[InformationEventRecord, int, str]] = []
        excluded = 0
        for event, priority, fingerprint in eligible_states:
            if self.session.scalar(
                select(BriefingItemRecord.id).where(
                    BriefingItemRecord.state_fingerprint == fingerprint
                )
            ):
                excluded += 1
                continue
            candidates.append((event, priority, fingerprint))

        content_fingerprint = (
            full_fingerprint
            if candidates
            else _hash(f"no-new-state|{period_start.isoformat()}|{period_end.isoformat()}")
        )
        idempotency_key = idempotency_key_override or _hash(
            f"{briefing_type.value}|{content_fingerprint}"
        )
        existing = self.session.scalar(
            select(BriefingRecord).where(BriefingRecord.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return BriefingGenerationResult(existing, tuple(self.items(existing.id)), excluded)

        has_correction = any(
            event.lifecycle_status in {LifecycleStatus.CORRECTED, LifecycleStatus.DENIED}
            for event, _, _ in candidates
        )
        resolved_type = (
            briefing_type
            if preserve_briefing_type
            else BriefingType.CORRECTION_NOTICE
            if has_correction
            else briefing_type
        )
        status = (
            BriefingStatus.READY
            if candidates or include_no_change or not provider_complete
            else BriefingStatus.SKIPPED_NO_CHANGE
        )
        record = BriefingRecord(
            id=str(uuid4()),
            briefing_type=resolved_type,
            status=status,
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
            title=(
                f"중요 변경 브리핑 {len(candidates)}건"
                if candidates
                else "데이터 확인 불완전"
                if not provider_complete
                else "새로운 중요 변경 없음"
            ),
            compact_summary=(
                "새롭게 확인된 사실과 검증 상태 변경만 포함합니다."
                if candidates
                else "일부 데이터 제공자가 실패하여 완전한 확인이 불가능합니다."
                if not provider_complete
                else "재탕·중복 또는 중요 변경이 없는 사건은 발송 대상에서 제외했습니다."
            ),
            item_count=len(candidates),
            material_change_count=sum(int(event.material_change) for event, _, _ in candidates),
            correction_count=sum(
                int(event.lifecycle_status is LifecycleStatus.CORRECTED)
                for event, _, _ in candidates
            ),
            denial_count=sum(
                int(event.lifecycle_status is LifecycleStatus.DENIED)
                for event, _, _ in candidates
            ),
            official_confirmed_count=sum(
                int(event.verification_status is VerificationStatus.OFFICIAL_CONFIRMED)
                for event, _, _ in candidates
            ),
            needs_verification_count=sum(
                int(event.verification_status is VerificationStatus.NEEDS_VERIFICATION)
                for event, _, _ in candidates
            ),
            related_instrument_ids=sorted({event.instrument_id for event, _, _ in candidates}),
            content_fingerprint=content_fingerprint,
            idempotency_key=idempotency_key,
            valid_until=now + timedelta(days=7),
        )
        if persist:
            self.session.add(record)
            self.session.flush()
        items = tuple(
            self._item(record, event, priority, fingerprint)
            for event, priority, fingerprint in candidates
        )
        if persist:
            self.session.add_all(items)
            self.session.flush()
        return BriefingGenerationResult(record, items, excluded)

    @staticmethod
    def _eligible(event: InformationEventRecord) -> bool:
        if event.lifecycle_status in {
            LifecycleStatus.CORRECTED,
            LifecycleStatus.DENIED,
        }:
            return True
        if event.verification_status in {
            VerificationStatus.OFFICIAL_CONFIRMED,
            VerificationStatus.CONFLICTING,
            VerificationStatus.OFFICIALLY_DENIED,
            VerificationStatus.CORRECTED,
        }:
            return True
        return event.material_change

    @staticmethod
    def _priority(event: InformationEventRecord) -> int:
        if event.lifecycle_status in {
            LifecycleStatus.CORRECTED,
            LifecycleStatus.DENIED,
        }:
            return 100
        if event.verification_status is VerificationStatus.CONFLICTING:
            return 90
        if event.verification_status is VerificationStatus.OFFICIAL_CONFIRMED:
            return 80
        if event.material_change:
            return 70
        return 0

    @staticmethod
    def _state_fingerprint(event: InformationEventRecord) -> str:
        return _hash(
            json.dumps(
                {
                    "eventId": event.id,
                    "verification": event.verification_status.value,
                    "lifecycle": event.lifecycle_status.value,
                    "materialChange": event.material_change,
                    "changedFacts": event.changed_facts,
                    "latestMaterialChangeAt": (
                        event.latest_material_change_at.isoformat()
                        if event.latest_material_change_at
                        else None
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    def _item(
        self,
        briefing: BriefingRecord,
        event: InformationEventRecord,
        priority: int,
        fingerprint: str,
    ) -> BriefingItemRecord:
        news = list(
            self.session.scalars(
                select(NewsReferenceRecord)
                .where(NewsReferenceRecord.information_event_id == event.id)
                .order_by(NewsReferenceRecord.published_at.desc())
                .limit(5)
            )
        )
        official = list(
            self.session.scalars(
                select(DisclosureRecord)
                .where(DisclosureRecord.event_id == event.id)
                .order_by(DisclosureRecord.published_at.desc())
                .limit(5)
            )
        )
        changed = event.changed_facts or []
        changed_text = "; ".join(
            str(value.get("value") or value.get("field") or "변경 사실")
            for value in changed[:3]
        )
        summary = (
            f"새롭게 확인된 내용: {changed_text}"
            if changed_text
            else "공식 확인·정정·부인에 따른 검증 상태 변경입니다."
        )
        category = (
            "CORRECTION"
            if event.lifecycle_status is LifecycleStatus.CORRECTED
            else "DENIAL"
            if event.lifecycle_status is LifecycleStatus.DENIED
            else "MATERIAL_CHANGE"
        )
        return BriefingItemRecord(
            id=str(uuid4()),
            briefing_id=briefing.id,
            information_event_id=event.id,
            priority=priority,
            category=category,
            headline=(event.current_summary or event.normalized_claim)[:500],
            short_summary=summary[:1000],
            verification_status=event.verification_status,
            trust_score=max(
                [reference.trust_score for reference in news] + ([85] if official else [0])
            ),
            material_change=event.material_change,
            changed_facts=changed,
            source_links=[
                {"title": reference.title, "url": reference.canonical_url} for reference in news
            ],
            official_reference_links=[
                {"title": record.title, "url": record.official_url} for record in official
            ],
            published_at=event.last_seen_at,
            state_fingerprint=fingerprint,
        )
