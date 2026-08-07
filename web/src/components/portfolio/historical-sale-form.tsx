"use client";

import { type FormEvent, useMemo, useState } from "react";
import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import { decimalCompare, decimalSum } from "@/lib/decimal-math";
import {
  assetTypeLabels,
  currencyLabels,
  getMarketLabel,
} from "@/lib/display-labels";
import {
  isNonNegativeDecimal,
  isPositiveDecimal,
  MARKET_OPTIONS,
} from "@/lib/portfolio-form";
import type {
  Currency,
  HistoricalPortfolioInput,
  HistoricalSaleInput,
  PortfolioAssetType,
} from "@/types/api";

type HistoricalRow = Omit<HistoricalSaleInput, "soldAt"> & { soldAt: string };

const inputClass =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 text-base";

function emptyRow(): HistoricalRow {
  return {
    soldAt: "",
    quantity: "",
    salePrice: "",
    feeAmount: "0",
    taxAmount: "0",
    notes: null,
  };
}

export function HistoricalSaleForm({
  onSubmit,
  onClose,
}: {
  onSubmit: (input: HistoricalPortfolioInput) => Promise<void>;
  onClose: () => void;
}) {
  const [assetType, setAssetType] = useState<PortfolioAssetType>("EQUITY");
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [market, setMarket] = useState("");
  const [currency, setCurrency] = useState<Currency>("KRW");
  const [averagePrice, setAveragePrice] = useState("");
  const [totalSoldQuantity, setTotalSoldQuantity] = useState("");
  const [rows, setRows] = useState<HistoricalRow[]>([emptyRow()]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const rowTotal = useMemo(() => {
    if (!rows.every((row) => isPositiveDecimal(row.quantity))) return null;
    try {
      return decimalSum(rows.map((row) => row.quantity));
    } catch {
      return null;
    }
  }, [rows]);

  const duplicateRows = useMemo(() => {
    const keys = rows.map((row) =>
      [
        row.soldAt,
        row.quantity,
        row.salePrice,
        row.feeAmount,
        row.taxAmount,
      ].join("|"),
    );
    return new Set(keys).size !== keys.length;
  }, [rows]);

  function updateRow(index: number, values: Partial<HistoricalRow>) {
    setRows((current) =>
      current.map((row, position) =>
        position === index ? { ...row, ...values } : row,
      ),
    );
  }

  function validate(): string {
    if (!name.trim() || !symbol.trim() || !market) {
      return "자산 종류, 종목명, 티커와 시장·거래소를 입력하세요.";
    }
    if (!isPositiveDecimal(averagePrice)) {
      return "0보다 큰 매수 평균단가를 입력하세요.";
    }
    if (!isPositiveDecimal(totalSoldQuantity)) {
      return "0보다 큰 총 매도수량을 입력하세요.";
    }
    if (
      rows.some(
        (row) =>
          !row.soldAt ||
          !isPositiveDecimal(row.quantity) ||
          !isPositiveDecimal(row.salePrice) ||
          !isNonNegativeDecimal(row.feeAmount) ||
          !isNonNegativeDecimal(row.taxAmount),
      )
    ) {
      return "각 매도 행의 날짜·수량·매도가·수수료·세금을 확인하세요.";
    }
    if (rows.some((row) => new Date(`${row.soldAt}T00:00:00`).getTime() > Date.now())) {
      return "미래 날짜의 매도 거래는 등록할 수 없습니다.";
    }
    if (!rowTotal || decimalCompare(rowTotal, totalSoldQuantity) !== 0) {
      return "매도내역 총수량이 입력한 총 매도수량과 일치해야 합니다.";
    }
    if (
      assetType === "CRYPTO" &&
      (totalSoldQuantity.split(".")[1]?.length ?? 0) > 8
    ) {
      return "암호자산 수량은 소수점 이하 8자리까지 입력할 수 있습니다.";
    }
    return "";
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const validation = validate();
    setError(validation);
    if (validation) return;
    setSaving(true);
    try {
      await onSubmit({
        assetType,
        name: name.trim(),
        symbol: symbol.trim().toUpperCase(),
        market,
        currency,
        averagePrice: averagePrice.trim(),
        totalSoldQuantity: totalSoldQuantity.trim(),
        investmentHorizon: "UNSET",
        strategy: "",
        targetAllocation: null,
        maxLossPercent: null,
        notes: null,
        sales: rows.map((row) => ({
          ...row,
          soldAt: new Date(`${row.soldAt}T00:00:00`).toISOString(),
          notes: row.notes?.trim() || null,
        })),
      });
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "과거 매도 기록을 저장하지 못했습니다.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      title="과거 매도 기록"
      description="이미 전량 매도한 종목과 실제 체결 내역을 사용자 입력으로 기록합니다."
      onRequestClose={() => {
        if (!saving) onClose();
      }}
    >
      <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-semibold">
              자산 종류
              <select
                data-autofocus="true"
                className={`${inputClass} mt-2`}
                value={assetType}
                onChange={(event) => {
                  const next = event.target.value as PortfolioAssetType;
                  setAssetType(next);
                  if (!MARKET_OPTIONS[next].includes(market)) setMarket("");
                }}
              >
                {Object.entries(assetTypeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              종목명
              <input
                className={`${inputClass} mt-2`}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="text-sm font-semibold">
              종목코드
              <input
                className={`${inputClass} mt-2 uppercase`}
                value={symbol}
                onChange={(event) => setSymbol(event.target.value)}
              />
            </label>
            <label className="text-sm font-semibold">
              {assetType === "CRYPTO" ? "거래소" : "시장"}
              <select
                className={`${inputClass} mt-2`}
                value={market}
                onChange={(event) => setMarket(event.target.value)}
              >
                <option value="">선택</option>
                {MARKET_OPTIONS[assetType].map((value) => (
                  <option key={value} value={value}>
                    {getMarketLabel(value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              기준 통화
              <select
                className={`${inputClass} mt-2`}
                value={currency}
                onChange={(event) =>
                  setCurrency(event.target.value as Currency)
                }
              >
                {Object.entries(currencyLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              매수 평균단가
              <input
                className={`${inputClass} mt-2`}
                inputMode="decimal"
                value={averagePrice}
                onChange={(event) => setAveragePrice(event.target.value)}
              />
            </label>
            <label className="text-sm font-semibold">
              총 매도수량
              <input
                className={`${inputClass} mt-2`}
                inputMode="decimal"
                value={totalSoldQuantity}
                onChange={(event) => setTotalSoldQuantity(event.target.value)}
              />
            </label>
          </div>

          <section className="mt-6 border-t border-border pt-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-bold">복수 매도내역</h3>
                <p className="mt-1 text-xs text-muted">
                  행 수량 합계: {rowTotal ?? "입력 전"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setRows((current) => [...current, emptyRow()])}
                className="min-h-11 rounded-xl border border-cyan/40 px-3 text-sm font-bold text-cyan"
              >
                매도내역 추가
              </button>
            </div>
            {duplicateRows ? (
              <p className="mt-3 text-sm text-yellow">
                동일한 날짜·수량·가격·비용의 반복 행이 있습니다. 실제 내역인지
                확인하세요.
              </p>
            ) : null}
            <div className="mt-4 space-y-4">
              {rows.map((row, index) => (
                <article
                  key={index}
                  className="rounded-2xl border border-border bg-card p-4"
                >
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold">매도 {index + 1}</h4>
                    <button
                      type="button"
                      disabled={rows.length === 1}
                      onClick={() =>
                        setRows((current) =>
                          current.filter((_, position) => position !== index),
                        )
                      }
                      className="min-h-9 rounded-lg border border-border px-3 text-xs disabled:opacity-40"
                    >
                      매도내역 제거
                    </button>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <label className="text-sm font-semibold">
                      매도일
                      <input
                        type="date"
                        className={`${inputClass} mt-2`}
                        value={row.soldAt}
                        onChange={(event) =>
                          updateRow(index, { soldAt: event.target.value })
                        }
                      />
                    </label>
                    <label className="text-sm font-semibold">
                      매도수량
                      <input
                        inputMode="decimal"
                        className={`${inputClass} mt-2`}
                        value={row.quantity}
                        onChange={(event) =>
                          updateRow(index, { quantity: event.target.value })
                        }
                      />
                    </label>
                    <label className="text-sm font-semibold">
                      매도가
                      <input
                        inputMode="decimal"
                        className={`${inputClass} mt-2`}
                        value={row.salePrice}
                        onChange={(event) =>
                          updateRow(index, { salePrice: event.target.value })
                        }
                      />
                    </label>
                    <label className="text-sm font-semibold">
                      수수료
                      <input
                        inputMode="decimal"
                        className={`${inputClass} mt-2`}
                        value={row.feeAmount}
                        onChange={(event) =>
                          updateRow(index, { feeAmount: event.target.value })
                        }
                      />
                    </label>
                    <label className="text-sm font-semibold">
                      세금
                      <input
                        inputMode="decimal"
                        className={`${inputClass} mt-2`}
                        value={row.taxAmount}
                        onChange={(event) =>
                          updateRow(index, { taxAmount: event.target.value })
                        }
                      />
                    </label>
                    <label className="text-sm font-semibold">
                      메모
                      <input
                        className={`${inputClass} mt-2`}
                        value={row.notes ?? ""}
                        onChange={(event) =>
                          updateRow(index, {
                            notes: event.target.value || null,
                          })
                        }
                      />
                    </label>
                  </div>
                </article>
              ))}
            </div>
          </section>
          <p className="mt-5 rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm leading-6 text-secondary">
            수수료·세금·매도가는 실제 내역을 보고 직접 입력합니다. 자동 세율,
            자동 수수료와 원화 환산은 적용하지 않습니다.
          </p>
          {error ? (
            <p className="mt-4 rounded-xl border border-red/40 bg-red/10 p-4 text-sm text-red">
              {error}
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
              {saving ? "저장 중…" : "과거 매도 종목 저장"}
            </button>
          </div>
        </footer>
      </form>
    </Dialog>
  );
}
