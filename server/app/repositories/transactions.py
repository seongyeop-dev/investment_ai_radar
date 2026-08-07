from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import (
    PositionTransactionRecord,
    PositionTransactionStatus,
)


class PositionTransactionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_portfolio(
        self,
        portfolio_id: str,
        *,
        include_voided: bool = True,
        for_update: bool = False,
    ) -> list[PositionTransactionRecord]:
        statement = select(PositionTransactionRecord).where(
            PositionTransactionRecord.portfolio_item_id == portfolio_id
        )
        if not include_voided:
            statement = statement.where(
                PositionTransactionRecord.status == PositionTransactionStatus.ACTIVE
            )
        statement = statement.order_by(
            PositionTransactionRecord.traded_at,
            PositionTransactionRecord.created_at,
            PositionTransactionRecord.id,
        )
        if for_update:
            statement = statement.with_for_update()
        return list(self.session.scalars(statement))

    def get(
        self,
        portfolio_id: str,
        transaction_id: str,
        *,
        for_update: bool = False,
    ) -> PositionTransactionRecord | None:
        statement = select(PositionTransactionRecord).where(
            PositionTransactionRecord.id == transaction_id,
            PositionTransactionRecord.portfolio_item_id == portfolio_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_by_idempotency(
        self,
        portfolio_id: str,
        idempotency_key: str,
    ) -> PositionTransactionRecord | None:
        return self.session.scalar(
            select(PositionTransactionRecord).where(
                PositionTransactionRecord.portfolio_item_id == portfolio_id,
                PositionTransactionRecord.idempotency_key == idempotency_key,
            )
        )

    def create(
        self,
        values: Mapping[str, Any],
    ) -> PositionTransactionRecord:
        record = PositionTransactionRecord(**values)
        self.session.add(record)
        self.session.flush()
        return record

    def flush(self) -> None:
        self.session.flush()
