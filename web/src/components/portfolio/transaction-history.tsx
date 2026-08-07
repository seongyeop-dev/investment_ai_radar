"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import {
  importHistoricalTransactions,
  listPositionTransactions,
  updatePositionTransaction,
  voidPositionTransaction,
} from "@/lib/api/portfolio";
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
  HistoricalTransactionInput,
  PortfolioItem,
  PositionTransaction,
  PositionTransactionUpdateInput,
  TransactionSide,
} from "@/types/api";

const inputClass =
  "mt-2 min-h-11 w-full rounded-xl border border-border bg-card px-3 text-base";

type ImportRow = HistoricalTransactionInput & { key: string };

function localDateTime(value?: string): string {
  const date = value ? new Date(value) : new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function emptyImportRow(key: string): ImportRow {
  return {
    key,
    transactionSide: "BUY",
    tradedAt: localDateTime(),
    quantity: "",
    unitPrice: "",
    feeAmount: "0",
    taxAmount: "0",
    notes: null,
  };
}

export function TransactionHistory({
  item,
  onChanged,
  onClose,
}: {
  item: PortfolioItem;
  onChanged: () => void;
  onClose: () => void;
}) {
  const [transactions, setTransactions] = useState<PositionTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [includeVoided, setIncludeVoided] = useState(false);
  const [editing, setEditing] = useState<PositionTransaction | null>(null);
  const [editValues, setEditValues] =
    useState<PositionTransactionUpdateInput>({});
  const [voidTarget, setVoidTarget] = useState<PositionTransaction | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const rowSequence = useRef(1);
  const [importRows, setImportRows] = useState<ImportRow[]>([
    emptyImportRow("row-1"),
  ]);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    listPositionTransactions(item.id, includeVoided, controller.signal)
      .then((value) => {
        setTransactions(value.items);
        setError("");
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") {
          return;
        }
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "거래내역을 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [includeVoided, item.id, refreshKey]);

  const ordinal = useMemo(() => {
    const counts: Record<TransactionSide, number> = { BUY: 0, SELL: 0 };
    return new Map(
      [...transactions]
        .sort(
          (left, right) =>
            new Date(left.tradedAt).getTime() -
              new Date(right.tradedAt).getTime() ||
            left.sequenceNumber - right.sequenceNumber,
        )
        .map((transaction) => {
          if (
            transaction.status === "ACTIVE" &&
            transaction.transactionType !== "OPENING_BALANCE"
          ) {
            counts[transaction.transactionSide] += 1;
          }
          return [
            transaction.id,
            transaction.status === "ACTIVE"
              ? `${counts[transaction.transactionSide]}차 ${
                  transaction.transactionSide === "BUY" ? "매수" : "매도"
                }`
              : `취소된 ${
                  transaction.transactionSide === "BUY" ? "매수" : "매도"
                }`,
          ];
        }),
    );
  }, [transactions]);

  function reload() {
    setLoading(true);
    setRefreshKey((value) => value + 1);
    onChanged();
  }

  function beginEdit(transaction: PositionTransaction) {
    setEditing(transaction);
    setEditValues({
      tradedAt: localDateTime(transaction.tradedAt),
      unitPrice: transaction.unitPrice,
      feeAmount: transaction.feeAmount,
      taxAmount: transaction.taxAmount,
      notes: transaction.notes,
    });
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || pending) return;
    setPending(true);
    setError("");
    try {
      await updatePositionTransaction(item.id, editing.id, {
        ...editValues,
        tradedAt: editValues.tradedAt
          ? new Date(editValues.tradedAt).toISOString()
          : undefined,
      });
      setEditing(null);
      reload();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "거래를 수정하지 못했습니다.",
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
      await voidPositionTransaction(
        item.id,
        voidTarget.id,
        voidReason.trim(),
      );
      setVoidTarget(null);
      setVoidReason("");
      reload();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "거래를 취소하지 못했습니다.",
      );
    } finally {
      setPending(false);
    }
  }

  function updateImportRow(
    key: string,
    field: keyof HistoricalTransactionInput,
    value: string,
  ) {
    setImportRows((rows) =>
      rows.map((row) =>
        row.key === key
          ? {
              ...row,
              [field]:
                field === "notes"
                  ? value || null
                  : field === "transactionSide"
                    ? (value as TransactionSide)
                    : value,
            }
          : row,
      ),
    );
  }

  function addImportRow(side: TransactionSide) {
    rowSequence.current += 1;
    setImportRows((rows) => [
      ...rows,
      {
        ...emptyImportRow(`row-${rowSequence.current}`),
        transactionSide: side,
      },
    ]);
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const invalid = importRows.some(
      (row) =>
        !isPositiveDecimal(row.quantity) ||
        !isPositiveDecimal(row.unitPrice) ||
        !isNonNegativeDecimal(row.feeAmount) ||
        !isNonNegativeDecimal(row.taxAmount) ||
        Number.isNaN(new Date(row.tradedAt).getTime()),
    );
    if (invalid) {
      setError("과거 거래의 수량·단가·일시·비용을 확인해 주세요.");
      return;
    }
    setPending(true);
    setError("");
    try {
      await importHistoricalTransactions(
        item.id,
        importRows.map((row) => ({
          transactionSide: row.transactionSide,
          tradedAt: new Date(row.tradedAt).toISOString(),
          quantity: row.quantity,
          unitPrice: row.unitPrice,
          feeAmount: row.feeAmount,
          taxAmount: row.taxAmount,
          notes: row.notes,
        })),
      );
      setImportRows([emptyImportRow("row-1")]);
      rowSequence.current = 1;
      setImportOpen(false);
      reload();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "과거 거래 묶음을 저장하지 못했습니다.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      title={`${item.name} 통합 거래내역`}
      description="매수·매도를 한 원장에서 시간순으로 재계산합니다. 실제 주문이나 환율 계산은 수행하지 않습니다."
      onRequestClose={() => {
        if (!pending) onClose();
      }}
    >
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <label className="flex min-h-10 items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={includeVoided}
              onChange={(event) => {
                setLoading(true);
                setIncludeVoided(event.target.checked);
              }}
              className="size-4 accent-cyan"
            />
            취소 거래 포함
          </label>
          <button
            type="button"
            onClick={() => setImportOpen((value) => !value)}
            className="min-h-10 rounded-lg border border-cyan/40 px-3 text-sm font-bold text-cyan"
          >
            {importOpen ? "과거 입력 닫기" : "+ 과거 거래 일괄 입력"}
          </button>
        </div>

        {error ? (
          <p className="mb-4 rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red">
            {error}
          </p>
        ) : null}

        {importOpen ? (
          <form
            onSubmit={submitImport}
            className="mb-5 rounded-2xl border border-cyan/40 bg-card p-4"
          >
            <h3 className="font-bold">과거 매수·매도 일괄 입력</h3>
            <p className="mt-1 text-xs leading-5 text-muted">
              입력 묶음 전체를 먼저 재생합니다. 중간에 잔고가 음수가 되면 전부
              저장하지 않습니다.
            </p>
            <div className="mt-4 space-y-4">
              {importRows.map((row, index) => (
                <fieldset
                  key={row.key}
                  className="rounded-xl border border-border p-3"
                >
                  <legend className="px-1 text-sm font-bold">
                    거래 {index + 1}
                  </legend>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="text-sm font-semibold">
                      구분
                      <select
                        className={inputClass}
                        value={row.transactionSide}
                        onChange={(event) =>
                          updateImportRow(
                            row.key,
                            "transactionSide",
                            event.target.value,
                          )
                        }
                      >
                        <option value="BUY">매수</option>
                        <option value="SELL">매도</option>
                      </select>
                    </label>
                    <label className="text-sm font-semibold">
                      거래일시
                      <input
                        type="datetime-local"
                        className={inputClass}
                        value={row.tradedAt}
                        onChange={(event) =>
                          updateImportRow(
                            row.key,
                            "tradedAt",
                            event.target.value,
                          )
                        }
                      />
                    </label>
                    {(
                      [
                        ["quantity", "수량"],
                        ["unitPrice", "체결단가"],
                        ["feeAmount", "수수료"],
                        ["taxAmount", "세금"],
                      ] as const
                    ).map(([field, label]) => (
                      <label key={field} className="text-sm font-semibold">
                        {label}
                        <input
                          inputMode="decimal"
                          className={inputClass}
                          value={row[field]}
                          onChange={(event) =>
                            updateImportRow(
                              row.key,
                              field,
                              event.target.value,
                            )
                          }
                        />
                      </label>
                    ))}
                    <label className="text-sm font-semibold sm:col-span-2">
                      메모
                      <input
                        className={inputClass}
                        value={row.notes ?? ""}
                        onChange={(event) =>
                          updateImportRow(
                            row.key,
                            "notes",
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  </div>
                  {importRows.length > 1 ? (
                    <button
                      type="button"
                      onClick={() =>
                        setImportRows((rows) =>
                          rows.filter((candidate) => candidate.key !== row.key),
                        )
                      }
                      className="mt-3 min-h-9 rounded-lg border border-yellow/40 px-3 text-xs font-bold text-yellow"
                    >
                      행 제거
                    </button>
                  ) : null}
                </fieldset>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => addImportRow("BUY")}
                className="min-h-10 rounded-lg border border-border px-3 text-sm font-semibold"
              >
                + 매수 행
              </button>
              <button
                type="button"
                onClick={() => addImportRow("SELL")}
                className="min-h-10 rounded-lg border border-border px-3 text-sm font-semibold"
              >
                + 매도 행
              </button>
              <button
                type="submit"
                disabled={pending}
                className="min-h-10 rounded-lg bg-cyan px-3 text-sm font-bold text-background disabled:opacity-50"
              >
                {pending ? "검증·저장 중…" : "묶음 검증 후 저장"}
              </button>
            </div>
          </form>
        ) : null}

        {loading ? (
          <p className="py-12 text-center text-sm text-secondary">
            거래내역을 불러오는 중…
          </p>
        ) : transactions.length === 0 ? (
          <p className="py-12 text-center text-sm text-secondary">
            저장된 거래가 없습니다.
          </p>
        ) : (
          <ol className="space-y-4">
            {transactions.map((transaction) => (
              <li
                key={transaction.id}
                className="rounded-2xl border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-bold">
                      {transaction.transactionType === "OPENING_BALANCE"
                        ? "기존 잔고"
                        : ordinal.get(transaction.id)}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {new Date(transaction.tradedAt).toLocaleString("ko-KR")}
                      {transaction.transactionType === "HISTORICAL_IMPORT"
                        ? " · 과거 입력"
                        : ""}
                    </p>
                  </div>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-xs font-bold ${
                      transaction.transactionSide === "BUY"
                        ? "border-green/40 text-green"
                        : "border-yellow/40 text-yellow"
                    }`}
                  >
                    {transaction.status === "VOIDED"
                      ? "취소됨"
                      : transaction.transactionSide === "BUY"
                        ? "매수"
                        : "매도"}
                  </span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-muted">수량</dt>
                    <dd className="whitespace-nowrap font-bold">
                      {formatPortfolioQuantity(
                        transaction.quantity,
                        item.assetType,
                        item.symbol,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">체결단가</dt>
                    <dd className="whitespace-nowrap font-bold">
                      {formatPortfolioPrice(
                        transaction.unitPrice,
                        transaction.currency,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">거래 후 수량</dt>
                    <dd className="whitespace-nowrap font-bold">
                      {formatPortfolioQuantity(
                        transaction.quantityAfter,
                        item.assetType,
                        item.symbol,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">거래 후 평균단가</dt>
                    <dd className="whitespace-nowrap font-bold">
                      {formatPortfolioPrice(
                        transaction.averagePriceAfter,
                        transaction.currency,
                      )}
                    </dd>
                  </div>
                  {transaction.transactionSide === "SELL" ? (
                    <>
                      <div>
                        <dt className="text-muted">실현손익</dt>
                        <dd className="whitespace-nowrap font-bold">
                          {formatRealizedPnl(
                            transaction.realizedPnl ?? "0",
                            transaction.currency,
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-muted">실현수익률</dt>
                        <dd className="whitespace-nowrap font-bold">
                          {formatSignedPercent(
                            transaction.realizedReturnPercent,
                          )}
                        </dd>
                      </div>
                    </>
                  ) : null}
                </dl>
                <p className="mt-3 text-xs text-muted">
                  수수료{" "}
                  {formatPortfolioPrice(
                    transaction.feeAmount,
                    transaction.currency,
                  )}{" "}
                  · 세금{" "}
                  {formatPortfolioPrice(
                    transaction.taxAmount,
                    transaction.currency,
                  )}
                </p>
                {transaction.notes ? (
                  <p className="mt-3 text-sm text-secondary">
                    {transaction.notes}
                  </p>
                ) : null}
                {transaction.voidReason ? (
                  <p className="mt-3 text-xs text-muted">
                    취소 사유: {transaction.voidReason}
                  </p>
                ) : null}
                {transaction.status === "ACTIVE" &&
                transaction.sourceType === "USER_ENTRY" ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => beginEdit(transaction)}
                      className="min-h-10 rounded-lg border border-border px-3 text-sm font-semibold"
                    >
                      수정
                    </button>
                    <button
                      type="button"
                      onClick={() => setVoidTarget(transaction)}
                      className="min-h-10 rounded-lg border border-yellow/40 px-3 text-sm font-bold text-yellow"
                    >
                      거래 취소
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        )}

        {editing ? (
          <form
            onSubmit={saveEdit}
            className="mt-5 rounded-2xl border border-cyan/40 bg-card p-4"
          >
            <h3 className="font-bold">거래 수정</h3>
            <p className="mt-1 text-xs text-muted">
              수량은 원장 안전을 위해 수정할 수 없습니다.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                거래일시
                <input
                  type="datetime-local"
                  className={inputClass}
                  value={editValues.tradedAt ?? ""}
                  onChange={(event) =>
                    setEditValues((value) => ({
                      ...value,
                      tradedAt: event.target.value,
                    }))
                  }
                />
              </label>
              {(
                [
                  ["unitPrice", "체결단가"],
                  ["feeAmount", "수수료"],
                  ["taxAmount", "세금"],
                ] as const
              ).map(([field, label]) => (
                <label key={field} className="text-sm font-semibold">
                  {label}
                  <input
                    inputMode="decimal"
                    className={inputClass}
                    value={editValues[field] ?? ""}
                    onChange={(event) =>
                      setEditValues((value) => ({
                        ...value,
                        [field]: event.target.value,
                      }))
                    }
                  />
                </label>
              ))}
              <label className="text-sm font-semibold sm:col-span-2">
                메모
                <textarea
                  className={`${inputClass} min-h-20 py-3`}
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
                className="min-h-10 rounded-lg bg-cyan px-3 text-sm font-bold text-background"
              >
                다시 계산하여 저장
              </button>
              <button
                type="button"
                onClick={() => setEditing(null)}
                className="min-h-10 rounded-lg border border-border px-3 text-sm font-semibold"
              >
                닫기
              </button>
            </div>
          </form>
        ) : null}
      </div>

      {voidTarget ? (
        <div className="border-t border-border bg-surface px-5 py-4 sm:px-6">
          <p className="font-bold">이 거래를 취소할까요?</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            이후 거래까지 다시 계산합니다. 잔고가 음수가 되면 취소되지 않습니다.
          </p>
          <input
            className={inputClass}
            placeholder="취소 사유"
            value={voidReason}
            onChange={(event) => setVoidReason(event.target.value)}
          />
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={confirmVoid}
              disabled={!voidReason.trim() || pending}
              className="min-h-10 rounded-lg border border-yellow/40 px-3 text-sm font-bold text-yellow disabled:opacity-50"
            >
              원장 검증 후 취소
            </button>
            <button
              type="button"
              onClick={() => {
                setVoidTarget(null);
                setVoidReason("");
              }}
              disabled={pending}
              className="min-h-10 rounded-lg border border-border px-3 text-sm font-semibold"
            >
              돌아가기
            </button>
          </div>
        </div>
      ) : null}
    </Dialog>
  );
}
