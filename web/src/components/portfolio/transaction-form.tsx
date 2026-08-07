"use client";

import { type FormEvent, useMemo, useState } from "react";
import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import {
  decimalCompare,
  decimalDivide,
  decimalMultiply,
  decimalPercentage,
  decimalSubtract,
  decimalSum,
} from "@/lib/decimal-math";
import {
  isNonNegativeDecimal,
  isPositiveDecimal,
} from "@/lib/portfolio-form";
import {
  formatPortfolioPrice,
  formatPortfolioQuantity,
  formatRealizedPnl,
  formatSignedPercent,
} from "@/lib/portfolio-format";
import type {
  PortfolioItem,
  PositionTransactionInput,
  TransactionSide,
} from "@/types/api";

const inputClass =
  "mt-2 min-h-12 w-full rounded-xl border border-border bg-card px-3 text-base text-foreground focus:border-cyan";

function localDateTime(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function FieldError({ message }: { message?: string }) {
  return message ? (
    <p className="mt-1 text-xs text-red" role="alert">
      {message}
    </p>
  ) : null;
}

export function TransactionForm({
  item,
  side,
  onSubmit,
  onClose,
}: {
  item: PortfolioItem;
  side: TransactionSide;
  onSubmit: (input: PositionTransactionInput) => Promise<void>;
  onClose: () => void;
}) {
  const buy = side === "BUY";
  const [quantity, setQuantity] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [tradedAt, setTradedAt] = useState(localDateTime);
  const [feeAmount, setFeeAmount] = useState("0");
  const [taxAmount, setTaxAmount] = useState("0");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverMessage, setServerMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const preview = useMemo(() => {
    if (!isPositiveDecimal(quantity) || !isPositiveDecimal(unitPrice)) {
      return null;
    }
    try {
      const gross = decimalMultiply(quantity, unitPrice);
      const quantityAfter = buy
        ? decimalSum([item.quantity, quantity])
        : decimalSubtract(item.quantity, quantity);
      const currentCost = decimalMultiply(
        item.quantity,
        item.averagePrice ?? "0",
      );
      const costBasis = decimalMultiply(
        quantity,
        item.averagePrice ?? "0",
      );
      const pnl = buy
        ? null
        : decimalSubtract(gross, costBasis, feeAmount, taxAmount);
      return {
        gross,
        quantityAfter,
        averageAfter: buy
          ? decimalDivide(decimalSum([currentCost, gross]), quantityAfter)
          : item.averagePrice,
        costBasis: buy ? null : costBasis,
        pnl,
        returnPercent:
          !buy && pnl ? decimalPercentage(pnl, costBasis) : null,
      };
    } catch {
      return null;
    }
  }, [
    buy,
    feeAmount,
    item.averagePrice,
    item.quantity,
    quantity,
    taxAmount,
    unitPrice,
  ]);

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};
    if (!isPositiveDecimal(quantity)) {
      next.quantity = "0보다 큰 거래수량을 입력하세요.";
    }
    if (!isPositiveDecimal(unitPrice)) {
      next.unitPrice = "0보다 큰 체결단가를 입력하세요.";
    }
    if (!isNonNegativeDecimal(feeAmount)) {
      next.feeAmount = "수수료는 0 이상이어야 합니다.";
    }
    if (!isNonNegativeDecimal(taxAmount)) {
      next.taxAmount = "세금은 0 이상이어야 합니다.";
    }
    if (
      isPositiveDecimal(quantity) &&
      item.assetType === "CRYPTO" &&
      (quantity.split(".")[1]?.length ?? 0) > 8
    ) {
      next.quantity = "암호자산 수량은 소수점 이하 8자리까지 입력할 수 있습니다.";
    }
    if (!buy && isPositiveDecimal(quantity)) {
      try {
        if (decimalCompare(quantity, item.quantity) > 0) {
          next.quantity = "매도수량이 현재 보유수량을 초과합니다.";
        }
      } catch {
        next.quantity = "매도수량을 확인해 주세요.";
      }
    }
    const date = new Date(tradedAt);
    if (!tradedAt || Number.isNaN(date.getTime())) {
      next.tradedAt = "거래일시를 입력하세요.";
    } else if (date.getTime() > Date.now()) {
      next.tradedAt = "미래 시각의 거래는 등록할 수 없습니다.";
    }
    return next;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const next = validate();
    setErrors(next);
    setServerMessage("");
    if (Object.keys(next).length) return;
    setSaving(true);
    try {
      await onSubmit({
        tradedAt: new Date(tradedAt).toISOString(),
        quantity: quantity.trim(),
        unitPrice: unitPrice.trim(),
        feeAmount: feeAmount.trim(),
        taxAmount: taxAmount.trim(),
        notes: notes.trim() || null,
      });
    } catch (reason) {
      setServerMessage(
        reason instanceof ApiClientError
          ? reason.message
          : `${buy ? "매수" : "매도"} 거래를 저장하지 못했습니다.`,
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={buy ? "추가 매수" : "분할·전량 매도"}
      description="실제 주문은 전송하지 않으며 사용자가 입력한 체결 기록만 저장합니다."
      onRequestClose={() => {
        if (!saving) onClose();
      }}
    >
      <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          <div className="grid gap-3 rounded-xl border border-border bg-card p-4 text-sm sm:grid-cols-2">
            <p>
              현재 수량{" "}
              <strong className="whitespace-nowrap">
                {formatPortfolioQuantity(
                  item.quantity,
                  item.assetType,
                  item.symbol,
                )}
              </strong>
            </p>
            <p>
              현재 평균단가{" "}
              <strong className="whitespace-nowrap">
                {formatPortfolioPrice(item.averagePrice, item.currency)}
              </strong>
            </p>
          </div>

          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <label className="text-sm font-semibold">
              {buy ? "매수수량" : "매도수량"}
              <input
                data-autofocus="true"
                className={inputClass}
                inputMode="decimal"
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
              />
              <FieldError message={errors.quantity} />
            </label>
            <label className="text-sm font-semibold">
              체결단가
              <input
                className={inputClass}
                inputMode="decimal"
                value={unitPrice}
                onChange={(event) => setUnitPrice(event.target.value)}
              />
              <FieldError message={errors.unitPrice} />
            </label>
            <label className="text-sm font-semibold">
              거래일시
              <input
                className={inputClass}
                type="datetime-local"
                value={tradedAt}
                onChange={(event) => setTradedAt(event.target.value)}
              />
              <FieldError message={errors.tradedAt} />
            </label>
            <label className="text-sm font-semibold">
              수수료
              <input
                className={inputClass}
                inputMode="decimal"
                value={feeAmount}
                onChange={(event) => setFeeAmount(event.target.value)}
              />
              <FieldError message={errors.feeAmount} />
            </label>
            <label className="text-sm font-semibold">
              세금
              <input
                className={inputClass}
                inputMode="decimal"
                value={taxAmount}
                onChange={(event) => setTaxAmount(event.target.value)}
              />
              <FieldError message={errors.taxAmount} />
            </label>
            <label className="text-sm font-semibold sm:col-span-2">
              메모
              <textarea
                className={`${inputClass} min-h-24 py-3`}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
          </div>

          <section className="mt-5 rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-bold">계산 미리보기</h3>
            {preview ? (
              <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-muted">체결금액</dt>
                  <dd className="whitespace-nowrap font-bold">
                    {formatPortfolioPrice(preview.gross, item.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">
                    {buy ? "매수 후 수량" : "매도 후 잔여수량"}
                  </dt>
                  <dd className="whitespace-nowrap font-bold">
                    {formatPortfolioQuantity(
                      preview.quantityAfter,
                      item.assetType,
                      item.symbol,
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">
                    {buy ? "매수 후 평균단가" : "잔여 평균단가"}
                  </dt>
                  <dd className="whitespace-nowrap font-bold">
                    {formatPortfolioPrice(
                      preview.averageAfter,
                      item.currency,
                    )}
                  </dd>
                </div>
                {!buy && preview.costBasis && preview.pnl ? (
                  <>
                    <div>
                      <dt className="text-muted">예상 원가</dt>
                      <dd className="whitespace-nowrap font-bold">
                        {formatPortfolioPrice(
                          preview.costBasis,
                          item.currency,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">예상 실현손익</dt>
                      <dd className="whitespace-nowrap font-bold">
                        {formatRealizedPnl(preview.pnl, item.currency)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">예상 실현수익률</dt>
                      <dd className="whitespace-nowrap font-bold">
                        {formatSignedPercent(preview.returnPercent)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">매도 구분</dt>
                      <dd className="font-bold">
                        {decimalCompare(preview.quantityAfter, "0") === 0
                          ? "전량 매도"
                          : "부분 매도"}
                      </dd>
                    </div>
                  </>
                ) : null}
              </dl>
            ) : (
              <p className="mt-3 text-sm text-muted">
                수량과 체결단가를 입력하면 표시됩니다.
              </p>
            )}
            <p className="mt-3 text-xs leading-5 text-muted">
              평균단가와 실현손익은 서버가 Decimal 거래원장을 시간순으로 재계산합니다.
              수수료·세금·환율은 추정하지 않습니다.
            </p>
          </section>

          {serverMessage ? (
            <p className="mt-5 rounded-xl border border-red/40 bg-red/10 p-4 text-sm text-red">
              {serverMessage}
            </p>
          ) : null}
        </div>
        <footer className="sticky bottom-0 border-t border-border bg-surface px-5 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6">
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="min-h-12 rounded-xl border border-border px-5 font-semibold"
            >
              닫기
            </button>
            <button
              type="submit"
              disabled={saving}
              className="min-h-12 rounded-xl bg-cyan px-5 font-bold text-background disabled:opacity-50"
            >
              {saving ? "저장 중…" : `${buy ? "매수" : "매도"} 거래 저장`}
            </button>
          </div>
        </footer>
      </form>
    </Dialog>
  );
}
