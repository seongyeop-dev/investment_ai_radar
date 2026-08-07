from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import (
    SaleTransactionRecord,
    SaleTransactionStatus,
    SaleTransactionType,
)


class SaleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_portfolio(self, portfolio_id: str) -> list[SaleTransactionRecord]:
        statement = (
            select(SaleTransactionRecord)
            .where(SaleTransactionRecord.portfolio_item_id == portfolio_id)
            .order_by(
                SaleTransactionRecord.sold_at.desc(),
                SaleTransactionRecord.created_at.desc(),
                SaleTransactionRecord.id.desc(),
            )
        )
        return list(self._session.scalars(statement))

    def get(
        self,
        portfolio_id: str,
        sale_id: str,
        *,
        for_update: bool = False,
    ) -> SaleTransactionRecord | None:
        statement = select(SaleTransactionRecord).where(
            SaleTransactionRecord.id == sale_id,
            SaleTransactionRecord.portfolio_item_id == portfolio_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def active_for_portfolios(
        self,
        portfolio_ids: Iterable[str],
    ) -> list[SaleTransactionRecord]:
        identifiers = list(portfolio_ids)
        if not identifiers:
            return []
        statement = (
            select(SaleTransactionRecord)
            .where(
                SaleTransactionRecord.portfolio_item_id.in_(identifiers),
                SaleTransactionRecord.status == SaleTransactionStatus.ACTIVE,
            )
            .order_by(
                SaleTransactionRecord.portfolio_item_id,
                SaleTransactionRecord.sold_at,
                SaleTransactionRecord.created_at,
                SaleTransactionRecord.id,
            )
        )
        return list(self._session.scalars(statement))

    def latest_active_current_sale(
        self,
        portfolio_id: str,
    ) -> SaleTransactionRecord | None:
        statement = (
            select(SaleTransactionRecord)
            .where(
                SaleTransactionRecord.portfolio_item_id == portfolio_id,
                SaleTransactionRecord.status == SaleTransactionStatus.ACTIVE,
                SaleTransactionRecord.transaction_type != SaleTransactionType.HISTORICAL_SALE,
            )
            .order_by(
                SaleTransactionRecord.created_at.desc(),
                SaleTransactionRecord.id.desc(),
            )
            .limit(1)
            .with_for_update()
        )
        return self._session.scalar(statement)

    def create(self, values: Mapping[str, Any]) -> SaleTransactionRecord:
        sale = SaleTransactionRecord(**values)
        self._session.add(sale)
        self._session.flush()
        self._session.refresh(sale)
        return sale

    def update(
        self,
        sale: SaleTransactionRecord,
        values: Mapping[str, Any],
    ) -> SaleTransactionRecord:
        for key, value in values.items():
            setattr(sale, key, value)
        self._session.flush()
        self._session.refresh(sale)
        return sale
