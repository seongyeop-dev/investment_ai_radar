"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import {
  listSales,
  updateSale,
  voidSale,
} from "@/lib/api/portfolio";
import {
  formatPortfolioPrice,
  formatPortfolioQuantity,
  formatRealizedPnl,
  formatSignedPercent,
} from "@/lib/portfolio-format";
import type {
  PortfolioItem,
  SaleTransaction,
  SaleUpdateInput,
} from "@/types/api";

const inputClass =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 text-base";

function dateTimeLocal(value: string): string {
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function SaleHistory({
  item,
  onChanged,
  onClose,
}: {
  item: PortfolioItem;
  onChanged: () => void;
  onClose: () => void;
}) {
  const [sales, setSales] = useState<SaleTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [editing, setEditing] = useState<SaleTransaction | null>(null);
  const [editValues, setEditValues] = useState<SaleUpdateInput>({});
  const [voidTarget, setVoidTarget] = useState<SaleTransaction | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    listSales(item.id, controller.signal)
      .then((value) => {
        setSales(value.items);
        setError("");
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "매도 내역을 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [item.id, refreshKey]);

  function reload() {
    setLoading(true);
    setRefreshKey((value) => value + 1);
  }

  const latestCurrentSaleId = useMemo(
    () =>
      [...sales]
        .filter(
          (sale) =>
            sale.status === "ACTIVE" &&
            sale.transactionType !== "HISTORICAL_SALE",
        )
        .sort(
          (left, right) =>
            new Date(right.createdAt).getTime() -
            new Date(left.createdAt).getTime(),
        )[0]?.id,
    [sales],
  );

  function beginEdit(sale: SaleTransaction) {
    setEditing(sale);
    setEditValues({
      soldAt: dateTimeLocal(sale.soldAt),
      salePrice: sale.salePrice,
      feeAmount: sale.feeAmount,
      taxAmount: sale.taxAmount,
      notes: sale.notes,
    });
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || pending) return;
    setPending(true);
    setError("");
    try {
      await updateSale(item.id, editing.id, {
        ...editValues,
        soldAt: editValues.soldAt
          ? new Date(editValues.soldAt).toISOString()
          : undefined,
      });
      setEditing(null);
      reload();
      onChanged();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "매도 거래를 수정하지 못했습니다.",
      );
    } finally {
      setPending(false);
    }
  }

  async function confirmVoid() {
    if (!voidTarget || !voidReason.trim() || pending) return;
    setPending(true);
    setError("");
    try {
      await voidSale(item.id, voidTarget.id, voidReason.trim());
      setVoidTarget(null);
      setVoidReason("");
      reload();
      onChanged();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "매도 거래를 취소하지 못했습니다.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      title="매도 내역"
      description="Portfolio 전용 사용자 거래 기록이며 실제 주문 내역을 자동 조회하지 않습니다."
      onRequestClose={() => {
        if (!pending) onClose();
      }}
    >
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
        {error ? (
          <p className="mb-4 rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red">
            {error}
          </p>
        ) : null}
        {loading ? (
          <p className="py-12 text-center text-sm text-secondary">
            매도 내역을 불러오는 중…
          </p>
        ) : sales.length === 0 ? (
          <p className="py-12 text-center text-sm text-secondary">
            저장된 매도 거래가 없습니다.
          </p>
        ) : (
          <ol className="space-y-4">
            {sales.map((sale) => {
              const canVoid =
                sale.status === "ACTIVE" &&
                (sale.historicalImport || sale.id === latestCurrentSaleId);
              return (
                <li
                  key={sale.id}
                  className="rounded-2xl border border-border bg-card p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold">
                        {new Date(sale.soldAt).toLocaleString("ko-KR")}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {sale.transactionType === "PARTIAL_SALE"
                          ? "부분 매도"
                          : sale.transactionType === "FULL_SALE"
                            ? "전량 매도"
                            : "과거 매도 기록"}
                      </p>
                    </div>
                    <span className="rounded-full border border-border px-2.5 py-1 text-xs font-bold">
                      {sale.status === "ACTIVE" ? "활성" : "취소됨"}
                    </span>
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <dt className="text-muted">수량</dt>
                      <dd className="font-bold">
                        {formatPortfolioQuantity(
                          sale.quantity,
                          item.assetType,
                          item.symbol,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">매도가</dt>
                      <dd className="font-bold">
                        {formatPortfolioPrice(sale.salePrice, sale.currency)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">총 매도금액</dt>
                      <dd className="font-bold">
                        {formatPortfolioPrice(
                          sale.grossProceeds,
                          sale.currency,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">실현손익</dt>
                      <dd className="font-bold">
                        {formatRealizedPnl(sale.realizedPnl, sale.currency)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">실현수익률</dt>
                      <dd className="font-bold">
                        {formatSignedPercent(sale.realizedReturnPercent)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">수수료 · 세금</dt>
                      <dd className="font-bold">
                        {formatPortfolioPrice(sale.feeAmount, sale.currency)} ·{" "}
                        {formatPortfolioPrice(sale.taxAmount, sale.currency)}
                      </dd>
                    </div>
                  </dl>
                  {sale.notes ? (
                    <p className="mt-3 text-sm text-secondary">{sale.notes}</p>
                  ) : null}
                  {sale.voidReason ? (
                    <p className="mt-3 text-xs text-muted">
                      취소 사유: {sale.voidReason}
                    </p>
                  ) : null}
                  {sale.status === "ACTIVE" ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => beginEdit(sale)}
                        className="min-h-10 rounded-lg border border-border px-3 text-sm font-semibold"
                      >
                        수정
                      </button>
                      {canVoid ? (
                        <button
                          type="button"
                          onClick={() => setVoidTarget(sale)}
                          className="min-h-10 rounded-lg border border-yellow/40 px-3 text-sm font-bold text-yellow"
                        >
                          거래 취소
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ol>
        )}

        {editing ? (
          <form
            onSubmit={saveEdit}
            className="mt-5 rounded-2xl border border-cyan/40 bg-card p-4"
          >
            <h3 className="font-bold">매도 거래 수정</h3>
            <p className="mt-1 text-xs text-muted">
              매도수량은 수정할 수 없습니다.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                매도일시
                <input
                  type="datetime-local"
                  className={`${inputClass} mt-2`}
                  value={editValues.soldAt ?? ""}
                  onChange={(event) =>
                    setEditValues((value) => ({
                      ...value,
                      soldAt: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="text-sm font-semibold">
                매도가
                <input
                  inputMode="decimal"
                  className={`${inputClass} mt-2`}
                  value={editValues.salePrice ?? ""}
                  onChange={(event) =>
                    setEditValues((value) => ({
                      ...value,
                      salePrice: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="text-sm font-semibold">
                수수료
                <input
                  inputMode="decimal"
                  className={`${inputClass} mt-2`}
                  value={editValues.feeAmount ?? ""}
                  onChange={(event) =>
                    setEditValues((value) => ({
                      ...value,
                      feeAmount: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="text-sm font-semibold">
                세금
                <input
                  inputMode="decimal"
                  className={`${inputClass} mt-2`}
                  value={editValues.taxAmount ?? ""}
                  onChange={(event) =>
                    setEditValues((value) => ({
                      ...value,
                      taxAmount: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="text-sm font-semibold sm:col-span-2">
                메모
                <textarea
                  className={`${inputClass} mt-2 min-h-20 py-3`}
                  value={editValues.notes ?? ""}
                  onChange={(event) =>
                    setEditValues((value) => ({
                      ...value,
                      notes: event.target.value || null,
                    }))
                  }
                />
              </label>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="submit"
                disabled={pending}
                className="min-h-11 rounded-xl bg-cyan px-4 font-bold text-background disabled:opacity-50"
              >
                재계산 후 저장
              </button>
              <button
                type="button"
                onClick={() => setEditing(null)}
                className="min-h-11 rounded-xl border border-border px-4"
              >
                취소
              </button>
            </div>
          </form>
        ) : null}

        {voidTarget ? (
          <section className="mt-5 rounded-2xl border border-yellow/40 bg-yellow/10 p-4">
            <h3 className="font-bold">거래 취소</h3>
            <p className="mt-1 text-sm text-secondary">
              Hard delete하지 않으며 취소 사유와 시각을 보존합니다.
            </p>
            <label className="mt-4 block text-sm font-semibold">
              취소 사유
              <textarea
                className={`${inputClass} mt-2 min-h-20 py-3`}
                value={voidReason}
                onChange={(event) => setVoidReason(event.target.value)}
              />
            </label>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={confirmVoid}
                disabled={pending || !voidReason.trim()}
                className="min-h-11 rounded-xl bg-yellow px-4 font-bold text-background disabled:opacity-50"
              >
                취소 기록 저장
              </button>
              <button
                type="button"
                onClick={() => setVoidTarget(null)}
                className="min-h-11 rounded-xl border border-border px-4"
              >
                돌아가기
              </button>
            </div>
          </section>
        ) : null}
      </div>
      <footer className="sticky bottom-0 border-t border-border bg-surface px-5 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6">
        <button
          type="button"
          onClick={onClose}
          disabled={pending}
          className="min-h-12 w-full rounded-xl border border-border px-5 font-bold sm:w-auto"
        >
          닫기
        </button>
      </footer>
    </Dialog>
  );
}
