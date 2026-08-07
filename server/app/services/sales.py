from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from app.core.errors import (
    historical_sale_quantity_mismatch,
    portfolio_not_found,
    portfolio_not_holding,
    sale_already_voided,
    sale_not_found,
    sale_quantity_exceeds_holding,
    sale_quantity_immutable,
    sale_validation,
    sale_void_not_latest,
)
from app.core.time import Clock, SystemClock, require_aware_utc
from app.models.database import (
    AssetType,
    HoldingStatus,
    SaleTransactionRecord,
    SaleTransactionStatus,
    SaleTransactionType,
)
from app.repositories.portfolio import PortfolioRepository
from app.repositories.sales import SaleRepository
from app.schemas.portfolio import PortfolioCreate
from app.schemas.sales import (
    HistoricalPortfolioCreate,
    SaleCreate,
    SaleSummary,
    SaleUpdate,
    SaleVoid,
)
from app.services.portfolio import PortfolioService

STORAGE_QUANTUM = Decimal("0.000000000000000001")


def round_for_storage(value: Decimal) -> Decimal:
    """Round computed values to NUMERIC(38, 18) using bankers' rounding."""
    with localcontext() as context:
        context.prec = 80
        return value.quantize(STORAGE_QUANTUM, rounding=ROUND_HALF_EVEN)


def calculate_sale_values(
    *,
    quantity: Decimal,
    sale_price: Decimal,
    purchase_average_price: Decimal,
    fee_amount: Decimal,
    tax_amount: Decimal,
) -> dict[str, Decimal | None]:
    with localcontext() as context:
        context.prec = 80
        gross_proceeds = round_for_storage(quantity * sale_price)
        cost_basis = round_for_storage(quantity * purchase_average_price)
        realized_pnl = round_for_storage(gross_proceeds - cost_basis - fee_amount - tax_amount)
        realized_return_percent = (
            round_for_storage(realized_pnl / cost_basis * Decimal(100))
            if cost_basis > 0
            else None
        )
    return {
        "gross_proceeds": gross_proceeds,
        "cost_basis": cost_basis,
        "realized_pnl": realized_pnl,
        "realized_return_percent": realized_return_percent,
    }


def summarize_sales(sales: Iterable[SaleTransactionRecord]) -> SaleSummary:
    active = [sale for sale in sales if sale.status is SaleTransactionStatus.ACTIVE]
    if not active:
        return SaleSummary(
            active_sale_count=0,
            total_sold_quantity=Decimal(0),
            total_gross_proceeds=Decimal(0),
            total_fee_amount=Decimal(0),
            total_tax_amount=Decimal(0),
            total_cost_basis=Decimal(0),
            total_realized_pnl=Decimal(0),
            total_realized_return_percent=None,
            weighted_average_sale_price=None,
            first_sold_at=None,
            last_sold_at=None,
        )
    total_quantity = round_for_storage(sum((sale.quantity for sale in active), Decimal(0)))
    total_gross = round_for_storage(sum((sale.gross_proceeds for sale in active), Decimal(0)))
    total_cost = round_for_storage(sum((sale.cost_basis for sale in active), Decimal(0)))
    total_pnl = round_for_storage(sum((sale.realized_pnl for sale in active), Decimal(0)))
    return SaleSummary(
        active_sale_count=len(active),
        total_sold_quantity=total_quantity,
        total_gross_proceeds=total_gross,
        total_fee_amount=round_for_storage(
            sum((sale.fee_amount for sale in active), Decimal(0))
        ),
        total_tax_amount=round_for_storage(
            sum((sale.tax_amount for sale in active), Decimal(0))
        ),
        total_cost_basis=total_cost,
        total_realized_pnl=total_pnl,
        total_realized_return_percent=(
            round_for_storage(total_pnl / total_cost * Decimal(100)) if total_cost > 0 else None
        ),
        weighted_average_sale_price=(
            round_for_storage(total_gross / total_quantity) if total_quantity > 0 else None
        ),
        first_sold_at=min(sale.sold_at for sale in active),
        last_sold_at=max(sale.sold_at for sale in active),
    )


class SaleService:
    def __init__(
        self,
        portfolios: PortfolioRepository,
        sales: SaleRepository,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.portfolios = portfolios
        self.sales = sales
        self.clock = clock or SystemClock()

    def list(self, portfolio_id: str) -> list[SaleTransactionRecord]:
        self._portfolio(portfolio_id)
        return self.sales.list_for_portfolio(portfolio_id)

    def get(self, portfolio_id: str, sale_id: str) -> SaleTransactionRecord:
        self._portfolio(portfolio_id)
        sale = self.sales.get(portfolio_id, sale_id)
        if sale is None:
            raise sale_not_found()
        return sale

    def create(
        self,
        portfolio_id: str,
        payload: SaleCreate,
    ) -> SaleTransactionRecord:
        item = self.portfolios.get_by_id_for_update(portfolio_id)
        if (
            item is None
            or item.archived_at is not None
            or item.holding_status is not HoldingStatus.HOLDING
            or item.quantity <= 0
            or item.average_price is None
            or item.average_price <= 0
        ):
            if item is None:
                raise portfolio_not_found()
            raise portfolio_not_holding()
        self._validate_sold_at(payload.sold_at)
        self._validate_quantity_precision(item.asset_type, payload.quantity)
        if payload.quantity > item.quantity:
            raise sale_quantity_exceeds_holding()

        quantity_before = item.quantity
        quantity_after = round_for_storage(quantity_before - payload.quantity)
        transaction_type = (
            SaleTransactionType.FULL_SALE
            if quantity_after == 0
            else SaleTransactionType.PARTIAL_SALE
        )
        calculations = calculate_sale_values(
            quantity=payload.quantity,
            sale_price=payload.sale_price,
            purchase_average_price=item.average_price,
            fee_amount=payload.fee_amount,
            tax_amount=payload.tax_amount,
        )
        item.quantity = quantity_after
        item.holding_status = (
            HoldingStatus.SOLD if quantity_after == 0 else HoldingStatus.HOLDING
        )
        sale = self.sales.create(
            {
                "portfolio_item_id": item.id,
                "transaction_type": transaction_type,
                "sold_at": payload.sold_at,
                "quantity": payload.quantity,
                "sale_price": payload.sale_price,
                "purchase_average_price_snapshot": item.average_price,
                "currency": item.currency,
                "fee_amount": payload.fee_amount,
                "tax_amount": payload.tax_amount,
                **calculations,
                "quantity_before": quantity_before,
                "quantity_after": quantity_after,
                "historical_import": False,
                "notes": payload.notes,
                "status": SaleTransactionStatus.ACTIVE,
                "voided_at": None,
                "void_reason": None,
            }
        )
        self.portfolios.update(
            item,
            {
                "quantity": item.quantity,
                "holding_status": item.holding_status,
            },
        )
        return sale

    def update(
        self,
        portfolio_id: str,
        sale_id: str,
        payload: SaleUpdate,
    ) -> SaleTransactionRecord:
        self._portfolio(portfolio_id)
        sale = self.sales.get(portfolio_id, sale_id, for_update=True)
        if sale is None:
            raise sale_not_found()
        if sale.status is SaleTransactionStatus.VOIDED:
            raise sale_already_voided()
        if "quantity" in payload.model_fields_set:
            raise sale_quantity_immutable()
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return sale
        if "sold_at" in changes:
            self._validate_sold_at(changes["sold_at"])
        sale_price = changes.get("sale_price", sale.sale_price)
        fee_amount = changes.get("fee_amount", sale.fee_amount)
        tax_amount = changes.get("tax_amount", sale.tax_amount)
        changes.update(
            calculate_sale_values(
                quantity=sale.quantity,
                sale_price=sale_price,
                purchase_average_price=sale.purchase_average_price_snapshot,
                fee_amount=fee_amount,
                tax_amount=tax_amount,
            )
        )
        return self.sales.update(sale, changes)

    def create_historical_sale(
        self,
        portfolio_id: str,
        payload: SaleCreate,
    ) -> SaleTransactionRecord:
        item = self.portfolios.get_by_id_for_update(portfolio_id)
        if item is None:
            raise portfolio_not_found()
        if (
            item.archived_at is not None
            or item.holding_status is not HoldingStatus.SOLD
            or item.quantity != 0
            or item.average_price is None
            or item.average_price <= 0
        ):
            raise sale_validation(
                "수량이 0인 매도 완료 종목에만 과거 매도 기록을 보완할 수 있습니다."
            )
        self._validate_sold_at(payload.sold_at)
        self._validate_quantity_precision(item.asset_type, payload.quantity)
        calculations = calculate_sale_values(
            quantity=payload.quantity,
            sale_price=payload.sale_price,
            purchase_average_price=item.average_price,
            fee_amount=payload.fee_amount,
            tax_amount=payload.tax_amount,
        )
        return self.sales.create(
            {
                "portfolio_item_id": item.id,
                "transaction_type": SaleTransactionType.HISTORICAL_SALE,
                "sold_at": payload.sold_at,
                "quantity": payload.quantity,
                "sale_price": payload.sale_price,
                "purchase_average_price_snapshot": item.average_price,
                "currency": item.currency,
                "fee_amount": payload.fee_amount,
                "tax_amount": payload.tax_amount,
                **calculations,
                "quantity_before": payload.quantity,
                "quantity_after": Decimal(0),
                "historical_import": True,
                "notes": payload.notes,
                "status": SaleTransactionStatus.ACTIVE,
                "voided_at": None,
                "void_reason": None,
            }
        )

    def void(
        self,
        portfolio_id: str,
        sale_id: str,
        payload: SaleVoid,
    ) -> SaleTransactionRecord:
        item = self.portfolios.get_by_id_for_update(portfolio_id)
        if item is None:
            raise portfolio_not_found()
        sale = self.sales.get(portfolio_id, sale_id, for_update=True)
        if sale is None:
            raise sale_not_found()
        if sale.status is SaleTransactionStatus.VOIDED:
            raise sale_already_voided()
        if sale.transaction_type is not SaleTransactionType.HISTORICAL_SALE:
            latest = self.sales.latest_active_current_sale(portfolio_id)
            if latest is None or latest.id != sale.id:
                raise sale_void_not_latest()
            item.quantity = round_for_storage(item.quantity + sale.quantity)
            item.holding_status = (
                HoldingStatus.HOLDING if item.quantity > 0 else HoldingStatus.SOLD
            )
            self.portfolios.update(
                item,
                {
                    "quantity": item.quantity,
                    "holding_status": item.holding_status,
                },
            )
        return self.sales.update(
            sale,
            {
                "status": SaleTransactionStatus.VOIDED,
                "voided_at": require_aware_utc(self.clock.now()),
                "void_reason": payload.reason.strip(),
            },
        )

    def summary(self, portfolio_id: str) -> SaleSummary:
        self._portfolio(portfolio_id)
        active = self.sales.active_for_portfolios([portfolio_id])
        return summarize_sales(active)

    def summaries(self, portfolio_ids: Iterable[str]) -> dict[str, SaleSummary]:
        identifiers = list(portfolio_ids)
        grouped: dict[str, list[SaleTransactionRecord]] = defaultdict(list)
        for sale in self.sales.active_for_portfolios(identifiers):
            grouped[sale.portfolio_item_id].append(sale)
        return {
            portfolio_id: summarize_sales(grouped[portfolio_id]) for portfolio_id in identifiers
        }

    def create_historical(
        self,
        payload: HistoricalPortfolioCreate,
    ) -> tuple[object, list[SaleTransactionRecord], SaleSummary]:
        total = sum((sale.quantity for sale in payload.sales), Decimal(0))
        if total != payload.total_sold_quantity:
            raise historical_sale_quantity_mismatch()
        self._validate_quantity_precision(payload.asset_type, total)
        for entry in payload.sales:
            self._validate_sold_at(entry.sold_at)
            self._validate_quantity_precision(payload.asset_type, entry.quantity)

        portfolio = PortfolioService(self.portfolios).create(
            PortfolioCreate(
                asset_type=payload.asset_type,
                symbol=payload.symbol,
                name=payload.name,
                market=payload.market,
                currency=payload.currency,
                holding_status=HoldingStatus.SOLD,
                quantity=Decimal(0),
                average_price=payload.average_price,
                investment_horizon=payload.investment_horizon,
                strategy=payload.strategy,
                target_allocation=payload.target_allocation,
                max_loss_percent=payload.max_loss_percent,
                notes=payload.notes,
            )
        )
        remaining = payload.total_sold_quantity
        records: list[SaleTransactionRecord] = []
        for entry in sorted(payload.sales, key=lambda value: value.sold_at):
            before = remaining
            after = round_for_storage(before - entry.quantity)
            calculations = calculate_sale_values(
                quantity=entry.quantity,
                sale_price=entry.sale_price,
                purchase_average_price=payload.average_price,
                fee_amount=entry.fee_amount,
                tax_amount=entry.tax_amount,
            )
            records.append(
                self.sales.create(
                    {
                        "portfolio_item_id": portfolio.id,
                        "transaction_type": SaleTransactionType.HISTORICAL_SALE,
                        "sold_at": entry.sold_at,
                        "quantity": entry.quantity,
                        "sale_price": entry.sale_price,
                        "purchase_average_price_snapshot": payload.average_price,
                        "currency": payload.currency,
                        "fee_amount": entry.fee_amount,
                        "tax_amount": entry.tax_amount,
                        **calculations,
                        "quantity_before": before,
                        "quantity_after": after,
                        "historical_import": True,
                        "notes": entry.notes,
                        "status": SaleTransactionStatus.ACTIVE,
                        "voided_at": None,
                        "void_reason": None,
                    }
                )
            )
            remaining = after
        return portfolio, records, summarize_sales(records)

    def _portfolio(self, portfolio_id: str) -> object:
        item = self.portfolios.get_by_id(portfolio_id)
        if item is None:
            raise portfolio_not_found()
        return item

    def _validate_sold_at(self, sold_at: datetime) -> None:
        if sold_at > require_aware_utc(self.clock.now()):
            raise sale_validation("미래 시각의 매도 거래는 등록할 수 없습니다.")

    @staticmethod
    def _validate_quantity_precision(asset_type: AssetType, quantity: Decimal) -> None:
        if asset_type is AssetType.CRYPTO and max(-quantity.as_tuple().exponent, 0) > 8:
            raise sale_validation(
                "암호자산 매도수량은 소수점 이하 8자리까지 입력할 수 있습니다."
            )
