from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.errors import (
    portfolio_duplicate,
    portfolio_not_found,
    portfolio_restore_conflict,
    portfolio_validation,
)
from app.core.time import Clock, SystemClock, require_aware_utc
from app.models.database import (
    HoldingStatus,
    PortfolioItemRecord,
    PositionStatus,
    TrackingStatus,
)
from app.repositories.portfolio import PortfolioRepository
from app.schemas.portfolio import (
    PortfolioContextUpdate,
    PortfolioCreate,
    PortfolioUpdate,
)


class PortfolioService:
    def __init__(
        self,
        repository: PortfolioRepository,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or SystemClock()

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
        return self._repository.list(
            holding_status=holding_status,
            position_status=position_status,
            tracking_status=tracking_status,
            market=market,
            query=query,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

    def get(self, item_id: str) -> PortfolioItemRecord:
        item = self._repository.get_by_id(item_id)
        if item is None:
            raise portfolio_not_found()
        return item

    def create(self, payload: PortfolioCreate) -> PortfolioItemRecord:
        values = payload.model_dump()
        values.pop("initial_buy", None)
        tracking = values.pop("tracking_status", None)
        values["position_status"] = (
            PositionStatus.HOLDING
            if payload.holding_status is HoldingStatus.HOLDING
            else PositionStatus.CLOSED
            if payload.holding_status is HoldingStatus.SOLD
            else PositionStatus.EMPTY
        )
        values["tracking_status"] = tracking or (
            TrackingStatus.WATCHLIST
            if payload.holding_status is HoldingStatus.WATCHLIST
            else TrackingStatus.REENTRY_WATCH
            if payload.holding_status is HoldingStatus.REENTRY_WATCH
            else TrackingStatus.NONE
        )
        duplicate = self._repository.get_active_by_market_symbol(
            payload.market,
            payload.symbol,
        )
        if duplicate is not None:
            raise portfolio_duplicate(duplicate.id)
        try:
            return self._repository.create(values)
        except IntegrityError as exc:
            raise portfolio_duplicate() from exc

    def update_context(
        self,
        item_id: str,
        payload: PortfolioContextUpdate,
    ) -> PortfolioItemRecord:
        """Update the user's current analysis context without replaying the ledger."""
        item = self.get(item_id)
        fields = payload.model_fields_set
        if not fields:
            return item
        position_status = payload.position_status or item.position_status
        tracking_status = payload.tracking_status or item.tracking_status
        quantity = payload.current_quantity if "current_quantity" in fields else item.quantity
        average_price = payload.average_cost if "average_cost" in fields else item.average_price
        if position_status is PositionStatus.HOLDING:
            if quantity <= 0:
                raise portfolio_validation("HOLDING 상태의 현재 수량은 0보다 커야 합니다.")
            if average_price is None or average_price <= 0:
                raise portfolio_validation("HOLDING 상태의 평균단가는 0보다 커야 합니다.")
        if position_status is PositionStatus.CLOSED and quantity != 0:
            raise portfolio_validation("CLOSED 상태의 현재 수량은 0이어야 합니다.")
        if tracking_status is TrackingStatus.REENTRY_WATCH and quantity != 0:
            raise portfolio_validation("REENTRY_WATCH 상태의 현재 수량은 0이어야 합니다.")

        values: dict[str, Any] = {
            "position_status": position_status,
            "tracking_status": tracking_status,
            "quantity": quantity,
            "average_price": average_price,
            "holding_status": (
                HoldingStatus.HOLDING
                if position_status is PositionStatus.HOLDING
                else HoldingStatus.SOLD
                if position_status is PositionStatus.CLOSED
                else HoldingStatus.REENTRY_WATCH
                if tracking_status is TrackingStatus.REENTRY_WATCH
                else HoldingStatus.WATCHLIST
            ),
        }
        if "currency" in fields:
            values["currency"] = payload.currency
        if "investment_horizon" in fields:
            values["investment_horizon"] = payload.investment_horizon
        if "memo" in fields:
            values["notes"] = payload.memo
        return self._repository.update(item, values)

    def update(
        self,
        item_id: str,
        payload: PortfolioUpdate,
    ) -> PortfolioItemRecord:
        item = self.get(item_id)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return item
        derived_fields = {"holding_status", "quantity", "average_price"}
        changed_derived = any(
            key in changes and changes[key] != getattr(item, key) for key in derived_fields
        )
        if changed_derived and self._repository.has_position_transactions(item.id):
            raise portfolio_validation(
                "거래원장이 있는 종목의 상태·수량·평균단가는 "
                "거래 기록으로만 변경할 수 있습니다."
            )
        if (
            item.holding_status is HoldingStatus.HOLDING
            and changes.get("holding_status") is HoldingStatus.SOLD
        ):
            raise portfolio_validation(
                "보유 종목을 매도 완료로 변경하려면 전용 매도 처리를 사용해 주세요."
            )

        merged = self._record_values(item)
        merged.update(changes)
        try:
            validated = PortfolioCreate.model_validate(merged)
        except ValidationError as exc:
            message = exc.errors(include_input=False)[0]["msg"]
            raise portfolio_validation(message) from exc

        normalized = validated.model_dump()
        normalized.pop("initial_buy", None)
        normalized_tracking = normalized.pop("tracking_status", None)
        if normalized_tracking is not None:
            normalized["tracking_status"] = normalized_tracking
        update_values = {key: normalized[key] for key in changes}
        if "tracking_status" in changes and item.position_status is PositionStatus.EMPTY:
            update_values["holding_status"] = (
                HoldingStatus.REENTRY_WATCH
                if normalized["tracking_status"] is TrackingStatus.REENTRY_WATCH
                else HoldingStatus.WATCHLIST
            )
        if item.archived_at is None:
            duplicate = self._repository.get_active_by_market_symbol(
                normalized["market"],
                normalized["symbol"],
            )
            if duplicate is not None and duplicate.id != item.id:
                raise portfolio_duplicate(duplicate.id)
        try:
            return self._repository.update(item, update_values)
        except IntegrityError as exc:
            raise portfolio_duplicate() from exc

    def archive(self, item_id: str) -> None:
        item = self.get(item_id)
        archived_at = require_aware_utc(self._clock.now())
        self._repository.archive(item, archived_at)

    def restore(self, item_id: str) -> PortfolioItemRecord:
        item = self.get(item_id)
        if item.archived_at is None:
            return item
        duplicate = self._repository.get_active_by_market_symbol(
            item.market,
            item.symbol,
        )
        if duplicate is not None and duplicate.id != item.id:
            raise portfolio_restore_conflict()
        try:
            return self._repository.restore(item)
        except IntegrityError as exc:
            raise portfolio_restore_conflict() from exc

    @staticmethod
    def _record_values(item: PortfolioItemRecord) -> dict[str, Any]:
        return {
            "asset_type": item.asset_type,
            "symbol": item.symbol,
            "name": item.name,
            "market": item.market,
            "currency": item.currency,
            "holding_status": item.holding_status,
            "tracking_status": item.tracking_status,
            "quantity": item.quantity,
            "average_price": item.average_price,
            "investment_horizon": item.investment_horizon,
            "strategy": item.strategy,
            "target_allocation": item.target_allocation,
            "max_loss_percent": item.max_loss_percent,
            "notes": item.notes,
            "initial_buy": None,
        }
