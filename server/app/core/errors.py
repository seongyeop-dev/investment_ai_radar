from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ApplicationError(Exception):
    code: str
    message: str
    status_code: int
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


def portfolio_not_found() -> ApplicationError:
    return ApplicationError(
        code="PORTFOLIO_NOT_FOUND",
        message="포트폴리오 항목을 찾을 수 없습니다.",
        status_code=404,
    )


def portfolio_duplicate(
    item_id: str | None = None,
    *,
    archived: bool = False,
) -> ApplicationError:
    return ApplicationError(
        code="PORTFOLIO_DUPLICATE",
        message=(
            "같은 시장과 종목 코드의 보관 항목이 이미 있습니다. 기존 종목을 복원해 주세요."
            if archived
            else "이미 등록된 종목입니다. 기존 종목에서 매수 또는 매도 기록을 추가해 주세요."
        ),
        status_code=409,
        details={
            "existingPortfolioId": item_id,
            "archived": archived,
        }
        if item_id is not None
        else {},
    )


def portfolio_validation(message: str) -> ApplicationError:
    return ApplicationError(
        code="PORTFOLIO_VALIDATION_ERROR",
        message=message,
        status_code=422,
    )


def portfolio_restore_conflict() -> ApplicationError:
    return ApplicationError(
        code="PORTFOLIO_RESTORE_CONFLICT",
        message="같은 시장과 종목 코드의 활성 항목이 있어 복원할 수 없습니다.",
        status_code=409,
    )


def sale_not_found() -> ApplicationError:
    return ApplicationError(
        code="SALE_NOT_FOUND",
        message="매도 거래를 찾을 수 없습니다.",
        status_code=404,
    )


def sale_validation(message: str) -> ApplicationError:
    return ApplicationError(
        code="SALE_VALIDATION_ERROR",
        message=message,
        status_code=422,
    )


def sale_quantity_exceeds_holding() -> ApplicationError:
    return ApplicationError(
        code="SALE_QUANTITY_EXCEEDS_HOLDING",
        message="매도수량이 현재 보유수량을 초과합니다.",
        status_code=422,
    )


def sale_quantity_immutable() -> ApplicationError:
    return ApplicationError(
        code="SALE_QUANTITY_IMMUTABLE",
        message="저장된 매도수량은 수정할 수 없습니다. 최신 거래를 취소한 뒤 다시 등록하세요.",
        status_code=409,
    )


def sale_void_not_latest() -> ApplicationError:
    return ApplicationError(
        code="SALE_VOID_NOT_LATEST",
        message="현재 보유에서 생성된 가장 최신 활성 매도 거래만 취소할 수 있습니다.",
        status_code=409,
    )


def sale_already_voided() -> ApplicationError:
    return ApplicationError(
        code="SALE_ALREADY_VOIDED",
        message="이미 취소된 매도 거래입니다.",
        status_code=409,
    )


def historical_sale_quantity_mismatch() -> ApplicationError:
    return ApplicationError(
        code="HISTORICAL_SALE_QUANTITY_MISMATCH",
        message="매도내역의 총수량이 입력한 총 매도수량과 일치하지 않습니다.",
        status_code=422,
    )


def portfolio_not_holding() -> ApplicationError:
    return ApplicationError(
        code="PORTFOLIO_NOT_HOLDING",
        message="현재 보유 중이며 수량이 0보다 큰 항목만 매도 처리할 수 있습니다.",
        status_code=409,
    )


def transaction_not_found() -> ApplicationError:
    return ApplicationError(
        code="TRANSACTION_NOT_FOUND",
        message="거래원장 항목을 찾을 수 없습니다.",
        status_code=404,
    )


def buy_validation(message: str) -> ApplicationError:
    return ApplicationError(
        code="BUY_VALIDATION_ERROR",
        message=message,
        status_code=422,
    )


def sell_validation(message: str) -> ApplicationError:
    return ApplicationError(
        code="SELL_VALIDATION_ERROR",
        message=message,
        status_code=422,
    )


def insufficient_position_quantity(
    transaction_id: str,
    available: str,
    requested: str,
) -> ApplicationError:
    return ApplicationError(
        code="INSUFFICIENT_POSITION_QUANTITY",
        message="거래 Replay 중 보유수량보다 많은 매도가 발견되었습니다.",
        status_code=422,
        details={
            "transactionId": transaction_id,
            "availableQuantity": available,
            "requestedQuantity": requested,
        },
    )


def transaction_quantity_immutable() -> ApplicationError:
    return ApplicationError(
        code="TRANSACTION_QUANTITY_IMMUTABLE",
        message="거래수량은 수정할 수 없습니다. 거래를 취소하고 다시 등록해 주세요.",
        status_code=409,
    )


def transaction_void_breaks_ledger(transaction_id: str) -> ApplicationError:
    return ApplicationError(
        code="TRANSACTION_VOID_BREAKS_LEDGER",
        message="이 거래를 취소하면 후속 거래의 보유수량이 부족해집니다.",
        status_code=409,
        details={"transactionId": transaction_id},
    )


def ledger_replay_failed(message: str) -> ApplicationError:
    return ApplicationError(
        code="LEDGER_REPLAY_FAILED",
        message=message,
        status_code=422,
    )


def position_needs_review(portfolio_id: str) -> ApplicationError:
    return ApplicationError(
        code="POSITION_NEEDS_REVIEW",
        message="기존 거래와 현재 상태가 일치하지 않아 먼저 거래 기록을 검토해야 합니다.",
        status_code=409,
        details={"portfolioId": portfolio_id},
    )


def database_error() -> ApplicationError:
    return ApplicationError(
        code="DATABASE_ERROR",
        message="데이터베이스 요청을 처리할 수 없습니다.",
        status_code=503,
    )


def risk_profile_validation(message: str) -> ApplicationError:
    return ApplicationError(
        code="RISK_PROFILE_VALIDATION_ERROR",
        message=message,
        status_code=422,
    )


def risk_recommendation_stale() -> ApplicationError:
    return ApplicationError(
        code="RISK_RECOMMENDATION_STALE",
        message=("포트폴리오가 변경되어 기존 제안을 적용할 수 없습니다. 다시 분석해 주세요."),
        status_code=409,
    )


def instrument_not_found() -> ApplicationError:
    return ApplicationError(
        code="INSTRUMENT_NOT_FOUND",
        message="Instrument was not found.",
        status_code=404,
    )


def instrument_market_mismatch() -> ApplicationError:
    return ApplicationError(
        code="INSTRUMENT_MARKET_MISMATCH",
        message="Portfolio item and instrument markets are not compatible.",
        status_code=422,
    )


def disclosure_not_found() -> ApplicationError:
    return ApplicationError(
        code="DISCLOSURE_NOT_FOUND",
        message="Disclosure was not found.",
        status_code=404,
    )


def information_event_not_found() -> ApplicationError:
    return ApplicationError(
        code="INFORMATION_EVENT_NOT_FOUND",
        message="Information event was not found.",
        status_code=404,
    )


def news_not_found() -> ApplicationError:
    return ApplicationError(
        code="NEWS_REFERENCE_NOT_FOUND",
        message="News reference was not found.",
        status_code=404,
    )


def briefing_not_found() -> ApplicationError:
    return ApplicationError(
        code="BRIEFING_NOT_FOUND",
        message="브리핑을 찾을 수 없습니다.",
        status_code=404,
    )


def notification_preference_validation(message: str) -> ApplicationError:
    return ApplicationError(
        code="NOTIFICATION_PREFERENCE_VALIDATION_ERROR",
        message=message,
        status_code=422,
    )


def briefing_generation_validation(
    message: str,
    *,
    status_code: int = 422,
) -> ApplicationError:
    return ApplicationError(
        code="BRIEFING_GENERATION_VALIDATION_ERROR",
        message=message,
        status_code=status_code,
    )
