"use client";

import { type FormEvent, useMemo, useState } from "react";
import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import {
  decimalCompare,
  decimalMultiply,
  decimalPercentage,
  decimalSubtract,
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
  SaleCreateInput,
} from "@/types/api";

const inputClass =
  "min-h-12 w-full rounded-xl border border-border bg-card px-3 text-base text-foreground placeholder:text-muted focus:border-cyan";

function FieldError({ message }: { message?: string }) {
  return message ? (
    <p className="mt-1 text-xs text-red" role="alert">
      {message}
    </p>
  ) : null;
}

function localDateTime(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function SaleForm({
  item,
  historical = false,
  onSubmit,
  onClose,
}: {
  item: PortfolioItem;
  historical?: boolean;
  onSubmit: (input: SaleCreateInput) => Promise<void>;
  onClose: () => void;
}) {
  const [quantity, setQuantity] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [soldAt, setSoldAt] = useState(localDateTime);
  const [feeAmount, setFeeAmount] = useState("0");
  const [taxAmount, setTaxAmount] = useState("0");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverMessage, setServerMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const preview = useMemo(() => {
    if (
      !item.averagePrice ||
      !isPositiveDecimal(quantity) ||
      !isPositiveDecimal(salePrice) ||
      !isNonNegativeDecimal(feeAmount) ||
      !isNonNegativeDecimal(taxAmount)
    ) {
      return null;
    }
    try {
      const quantityAfter = historical
        ? "0.000000000000000000"
        : decimalSubtract(item.quantity, quantity);
      const gross = decimalMultiply(quantity, salePrice);
      const cost = decimalMultiply(quantity, item.averagePrice);
      const pnl = decimalSubtract(gross, cost, feeAmount, taxAmount);
      return {
        quantityAfter,
        gross,
        cost,
        pnl,
        returnPercent: decimalPercentage(pnl, cost),
      };
    } catch {
      return null;
    }
  }, [
    feeAmount,
    historical,
    item.averagePrice,
    item.quantity,
    quantity,
    salePrice,
    taxAmount,
  ]);

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};
    if (!isPositiveDecimal(quantity)) next.quantity = "0보다 큰 매도수량을 입력하세요.";
    if (!isPositiveDecimal(salePrice)) next.salePrice = "0보다 큰 매도가를 입력하세요.";
    if (!isNonNegativeDecimal(feeAmount)) next.feeAmount = "수수료는 0 이상이어야 합니다.";
    if (!isNonNegativeDecimal(taxAmount)) next.taxAmount = "세금은 0 이상이어야 합니다.";
    if (isPositiveDecimal(quantity)) {
      try {
        if (!historical && decimalCompare(quantity, item.quantity) > 0) {
          next.quantity = "매도수량이 현재 보유수량을 초과합니다.";
        }
        if (
          item.assetType === "CRYPTO" &&
          (quantity.split(".")[1]?.length ?? 0) > 8
        ) {
          next.quantity = "암호자산 수량은 소수점 이하 8자리까지 입력할 수 있습니다.";
        }
      } catch {
        next.quantity = "매도수량을 확인해 주세요.";
      }
    }
    const date = new Date(soldAt);
    if (!soldAt || Number.isNaN(date.getTime())) {
      next.soldAt = "매도일시를 입력하세요.";
    } else if (date.getTime() > Date.now()) {
      next.soldAt = "미래 시각의 매도 거래는 등록할 수 없습니다.";
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
        soldAt: new Date(soldAt).toISOString(),
        quantity: quantity.trim(),
        salePrice: salePrice.trim(),
        feeAmount: feeAmount.trim(),
        taxAmount: taxAmount.trim(),
        notes: notes.trim() || null,
      });
    } catch (reason) {
      setServerMessage(
        reason instanceof ApiClientError
          ? reason.message
          : "매도 거래를 저장하지 못했습니다.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={historical ? "매도 기록 보완" : "매도 처리"}
      description={
        historical
          ? "매도 완료 종목의 과거 체결 기록을 보완하며 현재 수량은 변경하지 않습니다."
          : "실제 주문을 전송하지 않으며 사용자가 입력한 체결 기록만 저장합니다."
      }
      onRequestClose={() => {
        if (!saving) onClose();
      }}
    >
      <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          <div className="grid gap-3 rounded-xl border border-border bg-card p-4 text-sm sm:grid-cols-2">
            <p>
              {historical ? "현재 상태" : "현재 보유수량"}{" "}
              <strong>
                {historical
                  ? "매도 완료"
                  : formatPortfolioQuantity(
                      item.quantity,
                      item.assetType,
                      item.symbol,
                    )}
              </strong>
            </p>
            <p>
              매수 평균단가{" "}
              <strong>{formatPortfolioPrice(item.averagePrice, item.currency)}</strong>
            </p>
          </div>

          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <label className="text-sm font-semibold">
              매도수량
              <input
                data-autofocus="true"
                className={`${inputClass} mt-2`}
                inputMode="decimal"
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
              />
              <FieldError message={errors.quantity} />
            </label>
            <label className="text-sm font-semibold">
              주당·단위당 매도가
              <input
                className={`${inputClass} mt-2`}
                inputMode="decimal"
                value={salePrice}
                onChange={(event) => setSalePrice(event.target.value)}
              />
              <FieldError message={errors.salePrice} />
            </label>
            <label className="text-sm font-semibold">
              매도일시
              <input
                className={`${inputClass} mt-2`}
                type="datetime-local"
                value={soldAt}
                onChange={(event) => setSoldAt(event.target.value)}
              />
              <FieldError message={errors.soldAt} />
            </label>
            <label className="text-sm font-semibold">
              수수료
              <input
                className={`${inputClass} mt-2`}
                inputMode="decimal"
                value={feeAmount}
                onChange={(event) => setFeeAmount(event.target.value)}
              />
              <FieldError message={errors.feeAmount} />
            </label>
            <label className="text-sm font-semibold">
              세금
              <input
                className={`${inputClass} mt-2`}
                inputMode="decimal"
                value={taxAmount}
                onChange={(event) => setTaxAmount(event.target.value)}
              />
              <FieldError message={errors.taxAmount} />
            </label>
            <label className="text-sm font-semibold sm:col-span-2">
              메모
              <textarea
                className={`${inputClass} mt-2 min-h-24 py-3`}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
          </div>

          <p className="mt-5 rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm leading-6 text-secondary">
            수수료와 세금은 증권사·거래소 내역을 확인해 직접 입력합니다.
            시스템이 세율이나 수수료를 추정하지 않습니다. 환율도 자동 적용하지
            않습니다.
          </p>

          <section className="mt-5 rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-bold">계산 미리보기</h3>
            <p className="mt-1 text-xs text-muted">
              저장 전 참고값이며 최종 계산은 서버에서 Decimal로 다시 수행합니다.
            </p>
            {preview ? (
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-muted">매도 후 수량</dt>
                  <dd className="font-bold">{preview.quantityAfter}</dd>
                </div>
                <div>
                  <dt className="text-muted">총 매도금액</dt>
                  <dd className="font-bold">
                    {formatPortfolioPrice(preview.gross, item.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">예상 원가</dt>
                  <dd className="font-bold">
                    {formatPortfolioPrice(preview.cost, item.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">예상 실현손익</dt>
                  <dd className="font-bold">
                    {formatRealizedPnl(preview.pnl, item.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">예상 실현수익률</dt>
                  <dd className="font-bold">
                    {formatSignedPercent(preview.returnPercent)}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="mt-4 text-sm text-muted">
                매도수량과 매도가를 입력하면 표시됩니다.
              </p>
            )}
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
              {saving
                ? "저장 중…"
                : historical
                  ? "과거 매도 기록 저장"
                  : "매도 거래 저장"}
            </button>
          </div>
        </footer>
      </form>
    </Dialog>
  );
}
