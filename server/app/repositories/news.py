from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.contracts import VerificationStatus
from app.models.database import SourceGrade
from app.models.disclosures import (
    LifecycleStatus,
    NewsClaimRecord,
    NewsProviderType,
    NewsReferenceRecord,
)

MAX_NEWS_LIMIT = 100


class NewsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, reference_id: str) -> NewsReferenceRecord | None:
        return self.session.get(NewsReferenceRecord, reference_id)

    def by_provider_item(
        self, provider: NewsProviderType, item_id: str
    ) -> NewsReferenceRecord | None:
        return self.session.scalar(
            select(NewsReferenceRecord).where(
                NewsReferenceRecord.provider == provider,
                NewsReferenceRecord.provider_item_id == item_id,
            )
        )

    def by_url_hash(self, url_hash: str) -> NewsReferenceRecord | None:
        return self.session.scalar(
            select(NewsReferenceRecord).where(
                NewsReferenceRecord.canonical_url_hash == url_hash
            )
        )

    def event_references(self, event_id: str) -> list[NewsReferenceRecord]:
        return list(
            self.session.scalars(
                select(NewsReferenceRecord)
                .where(NewsReferenceRecord.information_event_id == event_id)
                .order_by(NewsReferenceRecord.published_at.asc())
            )
        )

    def create(self, record: NewsReferenceRecord) -> NewsReferenceRecord:
        self.session.add(record)
        self.session.flush()
        return record

    def create_claim(self, record: NewsClaimRecord) -> NewsClaimRecord:
        self.session.add(record)
        self.session.flush()
        return record

    def list(
        self,
        *,
        instrument_id: str | None = None,
        portfolio_item_id: str | None = None,
        source_grade: SourceGrade | None = None,
        verification_status: VerificationStatus | None = None,
        lifecycle_status: LifecycleStatus | None = None,
        material_change: bool | None = None,
        stale_reused: bool | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[NewsReferenceRecord], int]:
        filters = []
        if instrument_id:
            filters.append(NewsReferenceRecord.instrument_id == instrument_id)
        if portfolio_item_id:
            filters.append(NewsReferenceRecord.portfolio_item_id == portfolio_item_id)
        if source_grade:
            filters.append(NewsReferenceRecord.source_grade == source_grade)
        if verification_status:
            filters.append(NewsReferenceRecord.verification_status == verification_status)
        if lifecycle_status:
            filters.append(NewsReferenceRecord.lifecycle_status == lifecycle_status)
        if material_change is not None:
            filters.append(NewsReferenceRecord.material_change.is_(material_change))
        if stale_reused is not None:
            filters.append(NewsReferenceRecord.stale_reused.is_(stale_reused))
        if published_from:
            filters.append(NewsReferenceRecord.published_at >= published_from)
        if published_to:
            filters.append(NewsReferenceRecord.published_at <= published_to)
        if query and query.strip():
            term = query.strip()
            filters.append(
                or_(
                    NewsReferenceRecord.title.contains(term, autoescape=True),
                    NewsReferenceRecord.primary_claim.contains(term, autoescape=True),
                    NewsReferenceRecord.source_name.contains(term, autoescape=True),
                )
            )
        total = self.session.scalar(
            select(func.count()).select_from(NewsReferenceRecord).where(*filters)
        )
        rows = self.session.scalars(
            select(NewsReferenceRecord)
            .where(*filters)
            .order_by(
                NewsReferenceRecord.material_change.desc(),
                NewsReferenceRecord.published_at.desc(),
                NewsReferenceRecord.id,
            )
            .limit(min(max(limit, 1), MAX_NEWS_LIMIT))
            .offset(max(offset, 0))
        )
        return list(rows), int(total or 0)
