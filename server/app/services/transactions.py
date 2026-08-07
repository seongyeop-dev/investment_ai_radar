from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    buy_validation,
    insufficient_position_quantity,
    ledger_replay_failed,
    portfolio_not_found,
    position_needs_review,
    sell_validation,
    transaction_not_found,
    transaction_quantity_immutable,
    transaction_void_breaks_ledger,
)
from app.core.time import Clock, SystemClock, require_aware_utc
from app.models.database import (
    AssetType,
    HoldingStatus,
    PortfolioItemRecord,
    PositionStatus,
    PositionTransactionRecord,
    PositionTransactionStatus,
    PositionTransactionType,
    SaleTransactionRecord,
    SaleTransactionStatus,
    SaleTransactionType,
    TrackingStatus,
    TransactionSide,
    TransactionSourceType,
)
from app.repositories.portfolio import PortfolioRepository
from app.repositories.transactions import PositionTransactionRepository
from app.schemas.transactions import (
    BuyCreate,
    HistoricalTransactionImport,
    PositionSummary,
    SellCreate,
    TransactionCreate,
    TransactionUpdate,
    TransactionVoid,
)

STORAGE_QUANTUM = Decimal("0.000000000000000001")


def _round(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 80
        return value.quantize(STORAGE_QUANTUM, rounding=ROUND_HALF_EVEN)


def _compact(value: Decimal) -> Decimal:
    if value == 0:
        return Decimal(0)
    return Decimal(format(value.normalize(), "f"))


class PositionTransactionService:
    def __init__(
        self,
        session: Session,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.session = session
        self.portfolios = PortfolioRepository(session)
        self.transactions = PositionTransactionRepository(session)
        self.clock = clock or SystemClock()

    def list(
        self,
        portfolio_id: str,
        *,
        include_voided: bool = True,
    ) -> list[PositionTransactionRecord]:
        self._item(portfolio_id)
        return self.transactions.list_for_portfolio(
            portfolio_id,
            include_voided=include_voided,
        )

    def get(
        self,
        portfolio_id: str,
        transaction_id: str,
    ) -> PositionTransactionRecord:
        self._item(portfolio_id)
        record = self.transactions.get(portfolio_id, transaction_id)
        if record is None:
            raise transaction_not_found()
        return record

    def create_buy(
        self,
        portfolio_id: str,
        payload: BuyCreate,
    ) -> PositionTransactionRecord:
        return self._create(
            portfolio_id,
            payload,
            side=TransactionSide.BUY,
            transaction_type=PositionTransactionType.NORMAL,
            source_type=TransactionSourceType.USER_ENTRY,
        )

    def create_sell(
        self,
        portfolio_id: str,
        payload: SellCreate,
    ) -> PositionTransactionRecord:
        record = self._create(
            portfolio_id,
            payload,
            side=TransactionSide.SELL,
            transaction_type=PositionTransactionType.NORMAL,
            source_type=TransactionSourceType.USER_ENTRY,
        )
        self._create_compatibility_sale(record)
        self.session.flush()
        return record

    def update(
        self,
        portfolio_id: str,
        transaction_id: str,
        payload: TransactionUpdate,
    ) -> PositionTransactionRecord:
        item = self._item(portfolio_id, for_update=True)
        record = self.transactions.get(
            portfolio_id,
            transaction_id,
            for_update=True,
        )
        if record is None:
            raise transaction_not_found()
        if "quantity" in payload.model_fields_set:
            raise transaction_quantity_immutable()
        if record.status is PositionTransactionStatus.VOIDED:
            raise ledger_replay_failed("취소된 거래는 수정할 수 없습니다.")
        changes = payload.model_dump(exclude_unset=True)
        if "traded_at" in changes:
            self._validate_traded_at(changes["traded_at"], record.transaction_side)
        for key, value in changes.items():
            setattr(record, key, value)
        try:
            self._replay(item)
        except Exception:
            raise
        self.session.flush()
        return record

    def void(
        self,
        portfolio_id: str,
        transaction_id: str,
        payload: TransactionVoid,
    ) -> PositionTransactionRecord:
        item = self._item(portfolio_id, for_update=True)
        record = self.transactions.get(
            portfolio_id,
            transaction_id,
            for_update=True,
        )
        if record is None:
            raise transaction_not_found()
        if record.status is PositionTransactionStatus.VOIDED:
            return record
        record.status = PositionTransactionStatus.VOIDED
        record.voided_at = require_aware_utc(self.clock.now())
        record.void_reason = payload.reason.strip()
        try:
            self._replay(item)
        except Exception as exc:
            failing = (
                exc.details.get("transactionId", transaction_id)
                if hasattr(exc, "details")
                else transaction_id
            )
            raise transaction_void_breaks_ledger(str(failing)) from exc
        self.session.flush()
        return record

    def historical_import(
        self,
        portfolio_id: str,
        payload: HistoricalTransactionImport,
    ) -> list[PositionTransactionRecord]:
        item = self._item(portfolio_id, for_update=True)
        if item.position_status is PositionStatus.NEEDS_REVIEW:
            raise position_needs_review(item.id)
        created: list[PositionTransactionRecord] = []
        for index, entry in enumerate(payload.items, start=1):
            self._validate_traded_at(entry.traded_at, entry.transaction_side)
            self._validate_quantity_precision(
                item.asset_type,
                entry.quantity,
                entry.transaction_side,
            )
            key = entry.idempotency_key or (f"HISTORICAL_IMPORT:{uuid4()}:{index}")
            existing = self.transactions.get_by_idempotency(item.id, key)
            if existing is not None:
                created.append(existing)
                continue
            created.append(
                self.transactions.create(
                    self._new_values(
                        item,
                        entry,
                        side=entry.transaction_side,
                        transaction_type=PositionTransactionType.HISTORICAL_IMPORT,
                        source_type=TransactionSourceType.HISTORICAL_IMPORT,
                        idempotency_key=key,
                    )
                )
            )
        self._replay(item)
        for record in created:
            if record.transaction_side is TransactionSide.SELL:
                self._create_compatibility_sale(record)
        self.session.flush()
        return created

    def summary(self, portfolio_id: str) -> PositionSummary:
        item = self._item(portfolio_id)
        active = self.transactions.list_for_portfolio(
            portfolio_id,
            include_voided=False,
        )
        buys = [record for record in active if record.transaction_side is TransactionSide.BUY]
        sells = [record for record in active if record.transaction_side is TransactionSide.SELL]
        total_bought = _round(sum((record.quantity for record in buys), Decimal(0)))
        total_sold = _round(sum((record.quantity for record in sells), Decimal(0)))
        total_gross = _round(sum((record.gross_amount for record in sells), Decimal(0)))
        total_pnl = _round(
            sum((record.realized_pnl or Decimal(0) for record in sells), Decimal(0))
        )
        total_cost = _round(
            sum(
                (
                    record.gross_amount
                    - (record.realized_pnl or Decimal(0))
                    - record.fee_amount
                    - record.tax_amount
                    for record in sells
                ),
                Decimal(0),
            )
        )
        return PositionSummary(
            portfolio_item_id=item.id,
            position_status=item.position_status,
            tracking_status=item.tracking_status,
            current_quantity=item.quantity,
            current_average_price=item.average_price,
            total_bought_quantity=total_bought,
            total_sold_quantity=total_sold,
            weighted_average_sale_price=(
                _round(total_gross / total_sold) if total_sold > 0 else None
            ),
            total_realized_pnl=total_pnl,
            total_realized_return_percent=(
                _round(total_pnl / total_cost * Decimal(100)) if total_cost > 0 else None
            ),
            active_transaction_count=len(active),
            buy_count=len(buys),
            sell_count=len(sells),
            first_traded_at=active[0].traded_at if active else None,
            last_traded_at=active[-1].traded_at if active else None,
        )

    def compatibility_sale(
        self,
        portfolio_id: str,
        ledger_transaction_id: str,
    ) -> SaleTransactionRecord:
        sale = self.session.scalar(
            select(SaleTransactionRecord).where(
                SaleTransactionRecord.portfolio_item_id == portfolio_id,
                SaleTransactionRecord.ledger_transaction_id == ledger_transaction_id,
            )
        )
        if sale is None:
            raise transaction_not_found()
        return sale

    def _create(
        self,
        portfolio_id: str,
        payload: TransactionCreate,
        *,
        side: TransactionSide,
        transaction_type: PositionTransactionType,
        source_type: TransactionSourceType,
    ) -> PositionTransactionRecord:
        item = self._item(portfolio_id, for_update=True)
        if item.archived_at is not None:
            raise ledger_replay_failed("보관된 종목에는 거래를 추가할 수 없습니다.")
        if item.position_status is PositionStatus.NEEDS_REVIEW:
            raise position_needs_review(item.id)
        self._ensure_opening_balance(item, before_at=payload.traded_at)
        self._validate_traded_at(payload.traded_at, side)
        self._validate_quantity_precision(item.asset_type, payload.quantity, side)
        key = payload.idempotency_key or f"USER_ENTRY:{uuid4()}"
        existing = self.transactions.get_by_idempotency(item.id, key)
        if existing is not None:
            return existing
        record = self.transactions.create(
            self._new_values(
                item,
                payload,
                side=side,
                transaction_type=transaction_type,
                source_type=source_type,
                idempotency_key=key,
            )
        )
        self._replay(item)
        self.session.flush()
        return record

    def _ensure_opening_balance(
        self,
        item: PortfolioItemRecord,
        *,
        before_at: datetime,
    ) -> None:
        if self.transactions.list_for_portfolio(
            item.id,
            include_voided=True,
        ):
            return
        if item.quantity <= 0:
            return
        if item.average_price is None or item.average_price <= 0:
            raise position_needs_review(item.id)
        self.transactions.create(
            {
                "portfolio_item_id": item.id,
                "transaction_side": TransactionSide.BUY,
                "transaction_type": PositionTransactionType.OPENING_BALANCE,
                "traded_at": min(
                    require_aware_utc(item.created_at),
                    require_aware_utc(before_at) - timedelta(microseconds=1),
                ),
                "quantity": item.quantity,
                "unit_price": item.average_price,
                "currency": item.currency,
                "fee_amount": Decimal(0),
                "tax_amount": Decimal(0),
                "gross_amount": _round(item.quantity * item.average_price),
                "quantity_before": Decimal(0),
                "quantity_after": item.quantity,
                "average_price_before": None,
                "average_price_after": item.average_price,
                "realized_pnl": None,
                "realized_return_percent": None,
                "sequence_number": 1,
                "source_type": TransactionSourceType.MIGRATED_SNAPSHOT,
                "status": PositionTransactionStatus.ACTIVE,
                "voided_at": None,
                "void_reason": None,
                "notes": "기존 Portfolio 현재 수량·평단 보존용 Opening Balance",
                "idempotency_key": f"MIGRATED_SNAPSHOT:{item.id}",
            }
        )

    @staticmethod
    def _new_values(
        item: PortfolioItemRecord,
        payload: TransactionCreate,
        *,
        side: TransactionSide,
        transaction_type: PositionTransactionType,
        source_type: TransactionSourceType,
        idempotency_key: str,
    ) -> dict[str, object]:
        return {
            "portfolio_item_id": item.id,
            "transaction_side": side,
            "transaction_type": transaction_type,
            "traded_at": payload.traded_at,
            "quantity": payload.quantity,
            "unit_price": payload.unit_price,
            "currency": item.currency,
            "fee_amount": payload.fee_amount,
            "tax_amount": payload.tax_amount,
            "gross_amount": _round(payload.quantity * payload.unit_price),
            "quantity_before": Decimal(0),
            "quantity_after": Decimal(0),
            "average_price_before": None,
            "average_price_after": None,
            "realized_pnl": None,
            "realized_return_percent": None,
            "sequence_number": 1,
            "source_type": source_type,
            "status": PositionTransactionStatus.ACTIVE,
            "voided_at": None,
            "void_reason": None,
            "notes": payload.notes,
            "idempotency_key": idempotency_key,
        }

    def _replay(self, item: PortfolioItemRecord) -> None:
        records = self.transactions.list_for_portfolio(
            item.id,
            include_voided=True,
            for_update=True,
        )
        quantity = Decimal(0)
        average: Decimal | None = None
        active_count = 0
        for sequence, record in enumerate(records, start=1):
            record.sequence_number = sequence
            if record.status is PositionTransactionStatus.VOIDED:
                self._sync_compatibility_sale(record)
                continue
            active_count += 1
            before = quantity
            average_before = average
            gross = _round(record.quantity * record.unit_price)
            if record.transaction_side is TransactionSide.BUY:
                after = _round(before + record.quantity)
                with localcontext() as context:
                    context.prec = 80
                    new_average = _round(
                        (before * (average or Decimal(0)) + record.quantity * record.unit_price)
                        / after
                    )
                realized_pnl = None
                realized_return = None
                average = new_average
            else:
                if record.quantity > before:
                    raise insufficient_position_quantity(
                        record.id,
                        format(before, "f"),
                        format(record.quantity, "f"),
                    )
                if average is None or average <= 0:
                    raise ledger_replay_failed(
                        f"거래 {record.id}의 매수 평균단가를 계산할 수 없습니다."
                    )
                after = _round(before - record.quantity)
                cost_basis = _round(record.quantity * average)
                realized_pnl = _round(
                    gross - cost_basis - record.fee_amount - record.tax_amount
                )
                realized_return = (
                    _round(realized_pnl / cost_basis * Decimal(100)) if cost_basis > 0 else None
                )
                new_average = average
            record.gross_amount = gross
            record.quantity_before = before
            record.quantity_after = after
            record.average_price_before = average_before
            record.average_price_after = new_average
            record.realized_pnl = realized_pnl
            record.realized_return_percent = realized_return
            quantity = after
            self._sync_compatibility_sale(record)
        item.quantity = quantity
        item.average_price = average if active_count else None
        item.position_status = (
            PositionStatus.HOLDING
            if quantity > 0
            else PositionStatus.CLOSED
            if active_count
            else PositionStatus.EMPTY
        )
        item.holding_status = (
            HoldingStatus.HOLDING
            if quantity > 0
            else HoldingStatus.SOLD
            if active_count
            else HoldingStatus.REENTRY_WATCH
            if item.tracking_status is TrackingStatus.REENTRY_WATCH
            else HoldingStatus.WATCHLIST
        )
        self.session.flush()

    def _create_compatibility_sale(
        self,
        record: PositionTransactionRecord,
    ) -> SaleTransactionRecord:
        existing = self.session.scalar(
            select(SaleTransactionRecord).where(
                SaleTransactionRecord.ledger_transaction_id == record.id
            )
        )
        if existing is not None:
            self._sync_compatibility_sale(record)
            return existing
        transaction_type = (
            SaleTransactionType.HISTORICAL_SALE
            if record.transaction_type is PositionTransactionType.HISTORICAL_IMPORT
            else SaleTransactionType.FULL_SALE
            if record.quantity_after == 0
            else SaleTransactionType.PARTIAL_SALE
        )
        average = record.average_price_before
        if average is None:
            raise sell_validation("매도 시점 평균 매수단가가 없습니다.")
        cost_basis = _round(record.quantity * average)
        sale = SaleTransactionRecord(
            portfolio_item_id=record.portfolio_item_id,
            ledger_transaction_id=record.id,
            transaction_type=transaction_type,
            sold_at=record.traded_at,
            quantity=record.quantity,
            sale_price=record.unit_price,
            purchase_average_price_snapshot=_compact(average),
            currency=record.currency,
            fee_amount=record.fee_amount,
            tax_amount=record.tax_amount,
            gross_proceeds=record.gross_amount,
            cost_basis=cost_basis,
            realized_pnl=record.realized_pnl or Decimal(0),
            realized_return_percent=record.realized_return_percent,
            quantity_before=_compact(record.quantity_before),
            quantity_after=record.quantity_after,
            historical_import=(
                record.transaction_type is PositionTransactionType.HISTORICAL_IMPORT
            ),
            notes=record.notes,
            status=SaleTransactionStatus.ACTIVE,
            voided_at=None,
            void_reason=None,
        )
        self.session.add(sale)
        self.session.flush()
        return sale

    def _sync_compatibility_sale(
        self,
        record: PositionTransactionRecord,
    ) -> None:
        if record.transaction_side is not TransactionSide.SELL:
            return
        sale = self.session.scalar(
            select(SaleTransactionRecord).where(
                SaleTransactionRecord.ledger_transaction_id == record.id
            )
        )
        if sale is None:
            return
        average = record.average_price_before
        if average is None:
            return
        sale.transaction_type = (
            SaleTransactionType.HISTORICAL_SALE
            if record.transaction_type is PositionTransactionType.HISTORICAL_IMPORT
            else SaleTransactionType.FULL_SALE
            if record.quantity_after == 0
            else SaleTransactionType.PARTIAL_SALE
        )
        sale.sold_at = record.traded_at
        sale.sale_price = record.unit_price
        sale.purchase_average_price_snapshot = _compact(average)
        sale.fee_amount = record.fee_amount
        sale.tax_amount = record.tax_amount
        sale.gross_proceeds = record.gross_amount
        sale.cost_basis = _round(record.quantity * average)
        sale.realized_pnl = record.realized_pnl or Decimal(0)
        sale.realized_return_percent = record.realized_return_percent
        sale.quantity_before = _compact(record.quantity_before)
        sale.quantity_after = record.quantity_after
        sale.notes = record.notes
        sale.status = (
            SaleTransactionStatus.ACTIVE
            if record.status is PositionTransactionStatus.ACTIVE
            else SaleTransactionStatus.VOIDED
        )
        sale.voided_at = record.voided_at
        sale.void_reason = record.void_reason

    def _item(
        self,
        portfolio_id: str,
        *,
        for_update: bool = False,
    ) -> PortfolioItemRecord:
        item = (
            self.portfolios.get_by_id_for_update(portfolio_id)
            if for_update
            else self.portfolios.get_by_id(portfolio_id)
        )
        if item is None:
            raise portfolio_not_found()
        return item

    def _validate_traded_at(
        self,
        traded_at: datetime,
        side: TransactionSide,
    ) -> None:
        if traded_at > require_aware_utc(self.clock.now()):
            error = buy_validation if side is TransactionSide.BUY else sell_validation
            raise error("미래 시각의 거래는 등록할 수 없습니다.")

    @staticmethod
    def _validate_quantity_precision(
        asset_type: AssetType,
        quantity: Decimal,
        side: TransactionSide,
    ) -> None:
        if asset_type is AssetType.CRYPTO and max(-quantity.as_tuple().exponent, 0) > 8:
            error = buy_validation if side is TransactionSide.BUY else sell_validation
            raise error("암호자산 거래수량은 소수점 이하 8자리까지 입력할 수 있습니다.")
