from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import (
    HoldingStatus,
    PortfolioItemRecord,
    PositionStatus,
    PositionTransactionRecord,
    TrackingStatus,
)

MAX_LIST_LIMIT = 100


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        *,
        holding_status: HoldingStatus | None = None,
        position_status: PositionStatus | None = None,
        tracking_status: TrackingStatus | None = None,
        market: str | None = None,
        query: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PortfolioItemRecord], int]:
        filters = []
        if not include_archived:
            filters.append(PortfolioItemRecord.archived_at.is_(None))
        if holding_status is not None:
            filters.append(PortfolioItemRecord.holding_status == holding_status)
        if position_status is not None:
            filters.append(PortfolioItemRecord.position_status == position_status)
        if tracking_status is not None:
            filters.append(PortfolioItemRecord.tracking_status == tracking_status)
        if market:
            filters.append(PortfolioItemRecord.market == market.strip().upper())
        if query and query.strip():
            normalized_query = query.strip().upper()
            filters.append(
                func.upper(PortfolioItemRecord.symbol).contains(
                    normalized_query,
                    autoescape=True,
                )
                | func.upper(PortfolioItemRecord.name).contains(
                    normalized_query,
                    autoescape=True,
                )
            )

        safe_limit = min(max(limit, 1), MAX_LIST_LIMIT)
        safe_offset = max(offset, 0)
        total = self._session.scalar(
            select(func.count()).select_from(PortfolioItemRecord).where(*filters)
        )
        statement = (
            select(PortfolioItemRecord)
            .where(*filters)
            .order_by(
                PortfolioItemRecord.created_at.desc(),
                PortfolioItemRecord.id.asc(),
            )
            .limit(safe_limit)
            .offset(safe_offset)
        )
        items = list(self._session.scalars(statement))
        return items, int(total or 0)

    def get_by_id(self, item_id: str) -> PortfolioItemRecord | None:
        return self._session.get(PortfolioItemRecord, item_id)

    def get_by_id_for_update(self, item_id: str) -> PortfolioItemRecord | None:
        statement = (
            select(PortfolioItemRecord)
            .where(PortfolioItemRecord.id == item_id)
            .with_for_update()
        )
        return self._session.scalar(statement)

    def has_position_transactions(self, item_id: str) -> bool:
        statement = (
            select(PositionTransactionRecord.id)
            .where(PositionTransactionRecord.portfolio_item_id == item_id)
            .limit(1)
        )
        return self._session.scalar(statement) is not None

    def get_active_by_market_symbol(
        self,
        market: str,
        symbol: str,
    ) -> PortfolioItemRecord | None:
        statement = select(PortfolioItemRecord).where(
            PortfolioItemRecord.market == market.strip().upper(),
            PortfolioItemRecord.symbol == symbol.strip().upper(),
            PortfolioItemRecord.archived_at.is_(None),
        )
        return self._session.scalar(statement)

    def create(self, values: Mapping[str, Any]) -> PortfolioItemRecord:
        item = PortfolioItemRecord(**values)
        self._session.add(item)
        self._session.flush()
        self._session.refresh(item)
        return item

    def update(
        self,
        item: PortfolioItemRecord,
        values: Mapping[str, Any],
    ) -> PortfolioItemRecord:
        for key, value in values.items():
            setattr(item, key, value)
        self._session.flush()
        self._session.refresh(item)
        return item

    def archive(
        self,
        item: PortfolioItemRecord,
        archived_at: datetime,
    ) -> PortfolioItemRecord:
        if item.archived_at is None:
            item.archived_at = archived_at
            self._session.flush()
            self._session.refresh(item)
        return item

    def restore(self, item: PortfolioItemRecord) -> PortfolioItemRecord:
        if item.archived_at is not None:
            item.archived_at = None
            self._session.flush()
            self._session.refresh(item)
        return item

    def count_active_by_holding_status(self, holding_status: HoldingStatus) -> int:
        statement = (
            select(func.count())
            .select_from(PortfolioItemRecord)
            .where(
                PortfolioItemRecord.holding_status == holding_status,
                PortfolioItemRecord.archived_at.is_(None),
            )
        )
        return int(self._session.scalar(statement) or 0)

    def count_active_by_position_status(self, position_status: PositionStatus) -> int:
        statement = (
            select(func.count())
            .select_from(PortfolioItemRecord)
            .where(
                PortfolioItemRecord.position_status == position_status,
                PortfolioItemRecord.archived_at.is_(None),
            )
        )
        return int(self._session.scalar(statement) or 0)

    def count_active_by_tracking_status(self, tracking_status: TrackingStatus) -> int:
        statement = (
            select(func.count())
            .select_from(PortfolioItemRecord)
            .where(
                PortfolioItemRecord.tracking_status == tracking_status,
                PortfolioItemRecord.archived_at.is_(None),
            )
        )
        return int(self._session.scalar(statement) or 0)

    def count_active(self) -> int:
        statement = (
            select(func.count())
            .select_from(PortfolioItemRecord)
            .where(PortfolioItemRecord.archived_at.is_(None))
        )
        return int(self._session.scalar(statement) or 0)
