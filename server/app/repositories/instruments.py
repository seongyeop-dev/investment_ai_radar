from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.disclosures import (
    AssetType,
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    ProviderName,
)

MAX_INSTRUMENT_LIMIT = 100


class InstrumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        *,
        query: str | None = None,
        market: str | None = None,
        country: str | None = None,
        asset_type: AssetType | None = None,
        verified_only: bool = False,
        limit: int = 50,
    ) -> tuple[list[InstrumentRecord], int]:
        filters = [InstrumentRecord.active.is_(True)]
        if query and query.strip():
            term = query.strip().upper()
            filters.append(
                or_(
                    func.upper(InstrumentRecord.canonical_symbol).contains(term),
                    func.upper(InstrumentRecord.display_name).contains(term),
                    func.upper(InstrumentRecord.local_name).contains(term),
                )
            )
        if market:
            filters.append(InstrumentRecord.market == market.strip().upper())
        if country:
            filters.append(InstrumentRecord.country == country.strip().upper())
        if asset_type:
            filters.append(InstrumentRecord.asset_type == asset_type)
        if verified_only:
            filters.append(
                InstrumentRecord.verification_status == InstrumentVerificationStatus.VERIFIED
            )
        total = self.session.scalar(
            select(func.count()).select_from(InstrumentRecord).where(*filters)
        )
        statement = (
            select(InstrumentRecord)
            .where(*filters)
            .order_by(InstrumentRecord.market, InstrumentRecord.canonical_symbol)
            .limit(min(max(limit, 1), MAX_INSTRUMENT_LIMIT))
        )
        return list(self.session.scalars(statement)), int(total or 0)

    def get(self, instrument_id: str) -> InstrumentRecord | None:
        return self.session.get(InstrumentRecord, instrument_id)

    def get_active(self, market: str, symbol: str) -> InstrumentRecord | None:
        return self.session.scalar(
            select(InstrumentRecord).where(
                InstrumentRecord.market == market.strip().upper(),
                InstrumentRecord.canonical_symbol == symbol.strip().upper(),
                InstrumentRecord.active.is_(True),
            )
        )

    def create(self, values: Mapping[str, Any]) -> InstrumentRecord:
        record = InstrumentRecord(**values)
        self.session.add(record)
        self.session.flush()
        return record

    def update(self, record: InstrumentRecord, values: Mapping[str, Any]) -> InstrumentRecord:
        for name, value in values.items():
            setattr(record, name, value)
        self.session.flush()
        return record

    def mappings(self, instrument_id: str) -> list[InstrumentProviderMappingRecord]:
        return list(
            self.session.scalars(
                select(InstrumentProviderMappingRecord).where(
                    InstrumentProviderMappingRecord.instrument_id == instrument_id,
                    InstrumentProviderMappingRecord.active.is_(True),
                )
            )
        )

    def mapping_by_company(
        self, provider: ProviderName, company_id: str
    ) -> InstrumentProviderMappingRecord | None:
        return self.session.scalar(
            select(InstrumentProviderMappingRecord).where(
                InstrumentProviderMappingRecord.provider == provider,
                InstrumentProviderMappingRecord.provider_company_id == company_id,
            )
        )

    def create_mapping(self, values: Mapping[str, Any]) -> InstrumentProviderMappingRecord:
        record = InstrumentProviderMappingRecord(**values)
        self.session.add(record)
        self.session.flush()
        return record

    def update_mapping(
        self,
        record: InstrumentProviderMappingRecord,
        values: Mapping[str, Any],
    ) -> InstrumentProviderMappingRecord:
        for name, value in values.items():
            setattr(record, name, value)
        self.session.flush()
        return record
