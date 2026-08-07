from __future__ import annotations

from datetime import datetime

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.models.contracts import VerificationStatus
from app.models.disclosures import (
    DisclosureRecord,
    InformationEventRecord,
    InstrumentRecord,
    LifecycleStatus,
    ProviderName,
)

MAX_DISCLOSURE_LIMIT = 100


class DisclosureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_disclosure(self, record_id: str) -> DisclosureRecord | None:
        return self.session.get(DisclosureRecord, record_id)

    def get_event(self, event_id: str) -> InformationEventRecord | None:
        return self.session.get(InformationEventRecord, event_id)

    def get_event_by_key(self, event_key: str) -> InformationEventRecord | None:
        return self.session.scalar(
            select(InformationEventRecord).where(InformationEventRecord.event_key == event_key)
        )

    def find_duplicate(
        self,
        provider: ProviderName,
        document_id: str,
        official_url: str,
    ) -> DisclosureRecord | None:
        return self.session.scalar(
            select(DisclosureRecord).where(
                (DisclosureRecord.provider == provider)
                & (
                    (DisclosureRecord.provider_document_id == document_id)
                    | (DisclosureRecord.official_url == official_url)
                )
            )
        )

    def list_disclosures(
        self,
        *,
        instrument_id: str | None = None,
        portfolio_item_id: str | None = None,
        provider: ProviderName | None = None,
        form_type: str | None = None,
        verification_status: VerificationStatus | None = None,
        lifecycle_status: LifecycleStatus | None = None,
        material_change: bool | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DisclosureRecord], int]:
        filters = []
        if portfolio_item_id:
            from app.models.database import PortfolioItemRecord

            portfolio = self.session.get(PortfolioItemRecord, portfolio_item_id)
            if portfolio is None:
                filters.append(false())
            else:
                filters.append(
                    DisclosureRecord.instrument_id.in_(
                        select(InstrumentRecord.id).where(
                            InstrumentRecord.active.is_(True),
                            (
                                InstrumentRecord.id == portfolio.instrument_id
                                if portfolio.instrument_id
                                else (
                                    (InstrumentRecord.market == portfolio.market)
                                    & (InstrumentRecord.canonical_symbol == portfolio.symbol)
                                )
                            ),
                        )
                    )
                )
        if instrument_id:
            filters.append(DisclosureRecord.instrument_id == instrument_id)
        if provider:
            filters.append(DisclosureRecord.provider == provider)
        if form_type:
            filters.append(DisclosureRecord.form_type == form_type)
        if verification_status:
            filters.append(DisclosureRecord.verification_status == verification_status)
        if lifecycle_status:
            filters.append(DisclosureRecord.lifecycle_status == lifecycle_status)
        if material_change is not None:
            filters.append(DisclosureRecord.material_change.is_(material_change))
        if published_from:
            filters.append(DisclosureRecord.published_at >= published_from)
        if published_to:
            filters.append(DisclosureRecord.published_at <= published_to)
        total = self.session.scalar(
            select(func.count()).select_from(DisclosureRecord).where(*filters)
        )
        rows = self.session.scalars(
            select(DisclosureRecord)
            .where(*filters)
            .order_by(DisclosureRecord.published_at.desc(), DisclosureRecord.id)
            .limit(min(max(limit, 1), MAX_DISCLOSURE_LIMIT))
            .offset(max(offset, 0))
        )
        return list(rows), int(total or 0)

    def list_events(
        self,
        *,
        instrument_id: str | None = None,
        event_type: str | None = None,
        verification_status: VerificationStatus | None = None,
        lifecycle_status: LifecycleStatus | None = None,
        material_change_only: bool = False,
        first_seen_from: datetime | None = None,
        last_seen_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[InformationEventRecord], int]:
        filters = []
        if instrument_id:
            filters.append(InformationEventRecord.instrument_id == instrument_id)
        if event_type:
            filters.append(InformationEventRecord.event_type == event_type)
        if verification_status:
            filters.append(InformationEventRecord.verification_status == verification_status)
        if lifecycle_status:
            filters.append(InformationEventRecord.lifecycle_status == lifecycle_status)
        if material_change_only:
            filters.append(InformationEventRecord.material_change.is_(True))
        if first_seen_from:
            filters.append(InformationEventRecord.first_seen_at >= first_seen_from)
        if last_seen_to:
            filters.append(InformationEventRecord.last_seen_at <= last_seen_to)
        total = self.session.scalar(
            select(func.count()).select_from(InformationEventRecord).where(*filters)
        )
        rows = self.session.scalars(
            select(InformationEventRecord)
            .where(*filters)
            .order_by(InformationEventRecord.last_seen_at.desc(), InformationEventRecord.id)
            .limit(min(max(limit, 1), MAX_DISCLOSURE_LIMIT))
            .offset(max(offset, 0))
        )
        return list(rows), int(total or 0)
