"use client";

import { type FormEvent, useMemo, useState } from "react";
import { Dialog } from "@/components/common/dialog";
import { ApiClientError, getFieldErrors } from "@/lib/api/client";
import {
  assetTypeLabels,
  currencyLabels,
  getMarketLabel,
} from "@/lib/display-labels";
import {
  applyPortfolioPreset,
  EMPTY_PORTFOLIO_FORM,
  MARKET_OPTIONS,
  portfolioToForm,
  toPortfolioInput,
  type PortfolioFormValues,
  type PortfolioPreset,
  validatePortfolioForm,
} from "@/lib/portfolio-form";
import type {
  PortfolioAssetType,
  PortfolioCreateInput,
  PortfolioItem,
} from "@/types/api";

function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-red" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1.5 text-xs leading-5 text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

const inputClass =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 text-sm text-foreground placeholder:text-muted focus:border-cyan disabled:opacity-60";

const quickPresets: { key: PortfolioPreset; label: string }[] = [
  { key: "KOREAN_EQUITY", label: "국내 주식" },
  { key: "US_EQUITY", label: "미국 주식" },
  { key: "UPBIT_BITCOIN", label: "비트코인 · 업비트" },
  { key: "BINANCE_BITCOIN", label: "비트코인 · 바이낸스" },
];

export function PortfolioForm({
  item,
  onSubmit,
  onDuplicate,
  onClose,
}: {
  item?: PortfolioItem | null;
  onSubmit: (input: PortfolioCreateInput) => Promise<void>;
  onDuplicate: (
    id: string,
    action: "view" | "buy" | "restore",
  ) => Promise<void>;
  onClose: () => void;
}) {
  const initialValues = useMemo(
    () => (item ? portfolioToForm(item) : EMPTY_PORTFOLIO_FORM),
    [item],
  );
  const [values, setValues] = useState<PortfolioFormValues>(initialValues);
  const [optionalOpen, setOptionalOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverMessage, setServerMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [duplicate, setDuplicate] = useState<{
    id: string;
    archived: boolean;
  } | null>(null);
  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);
  const crypto = values.assetType === "CRYPTO";

  function setValue<K extends keyof PortfolioFormValues>(
    key: K,
    value: PortfolioFormValues[K],
  ) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function setAssetType(assetType: PortfolioAssetType) {
    setValues((current) => ({
      ...current,
      assetType,
      market: MARKET_OPTIONS[assetType].includes(current.market)
        ? current.market
        : "",
    }));
    setErrors({});
  }

  function selectPreset(preset: PortfolioPreset) {
    setValues((current) => applyPortfolioPreset(current, preset));
    setErrors({});
  }

  function requestClose() {
    if (saving) return;
    if (dirty) {
      setConfirmDiscard(true);
      return;
    }
    onClose();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const validation = validatePortfolioForm(values, !item);
    setErrors(validation);
    setServerMessage("");
    setDuplicate(null);
    if (Object.keys(validation).length) return;
    setSaving(true);
    try {
      await onSubmit(toPortfolioInput(values, !item));
    } catch (error) {
      setErrors(getFieldErrors(error));
      if (
        error instanceof ApiClientError &&
        error.code === "PORTFOLIO_DUPLICATE" &&
        typeof error.details.existingPortfolioId === "string"
      ) {
        setDuplicate({
          id: error.details.existingPortfolioId,
          archived: error.details.archived === true,
        });
      }
      setServerMessage(
        error instanceof ApiClientError
          ? error.message
          : "저장하지 못했습니다. 다시 시도해 주세요.",
      );
    } finally {
      setSaving(false);
    }
  }

  const describedBy = (field: string) =>
    errors[field] ? `${field}-error` : undefined;

  return (
    <Dialog
      title={item ? "종목 정보 수정" : "종목 등록"}
      description="사용자가 입력한 보유 정보만 저장하며 현재가와 거래소 계정은 연결하지 않습니다."
      onRequestClose={requestClose}
    >
      <form
        className="flex min-h-0 flex-1 flex-col"
        onSubmit={handleSubmit}
        noValidate
      >
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          {!item ? (
            <section className="mb-6">
              <p className="text-sm font-bold">빠른 등록</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                기본 식별 정보만 채웁니다. 상태·수량·평균단가는 자동 입력하지
                않습니다.
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {quickPresets.map((preset) => (
                  <button
                    key={preset.key}
                    type="button"
                    onClick={() => selectPreset(preset.key)}
                    className="min-h-11 rounded-xl border border-border bg-card px-3 text-sm font-semibold hover:border-cyan"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          <section aria-labelledby="required-fields-title">
            <h3 id="required-fields-title" className="mb-4 text-sm font-bold">
              필수 정보
            </h3>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field id="assetType" label="자산 종류">
                <select
                  id="assetType"
                  data-autofocus="true"
                  className={inputClass}
                  value={values.assetType}
                  onChange={(event) =>
                    setAssetType(event.target.value as PortfolioAssetType)
                  }
                >
                  {Object.entries(assetTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field id="name" label="종목명" error={errors.name}>
                <input
                  id="name"
                  className={inputClass}
                  value={values.name}
                  onChange={(event) => setValue("name", event.target.value)}
                  aria-invalid={Boolean(errors.name)}
                  aria-describedby={describedBy("name")}
                  required
                />
              </Field>
              <Field
                id="symbol"
                label="종목코드"
                error={errors.symbol}
                hint={
                  crypto
                    ? "예: BTC, ETH"
                    : "한국 종목코드의 앞자리 0도 그대로 보존합니다."
                }
              >
                <input
                  id="symbol"
                  className={`${inputClass} uppercase`}
                  value={values.symbol}
                  onChange={(event) => setValue("symbol", event.target.value)}
                  placeholder="예: 005930, INTC, RKLB"
                  aria-invalid={Boolean(errors.symbol)}
                  aria-describedby={describedBy("symbol")}
                  autoCapitalize="characters"
                  required
                />
              </Field>
              <Field
                id="market"
                label={crypto ? "거래소" : "시장"}
                error={errors.market}
              >
                <select
                  id="market"
                  className={inputClass}
                  value={values.market}
                  onChange={(event) => setValue("market", event.target.value)}
                  aria-invalid={Boolean(errors.market)}
                  aria-describedby={describedBy("market")}
                  required
                >
                  <option value="">
                    {crypto ? "거래소 선택" : "시장 선택"}
                  </option>
                  {MARKET_OPTIONS[values.assetType].map((market) => (
                    <option key={market} value={market}>
                      {getMarketLabel(market)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field id="currency" label="기준 통화">
                <select
                  id="currency"
                  className={inputClass}
                  value={values.currency}
                  onChange={(event) =>
                    setValue(
                      "currency",
                      event.target.value as PortfolioFormValues["currency"],
                    )
                  }
                >
                  {Object.entries(currencyLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              {item ? (
                <>
                  <Field
                    id="positionStatus"
                    label="포지션 상태 (거래원장 자동 계산)"
                  >
                    <input
                      id="positionStatus"
                      className={inputClass}
                      value={
                        item.positionStatus === "HOLDING"
                          ? "보유"
                          : item.positionStatus === "CLOSED"
                            ? "청산 완료"
                            : item.positionStatus === "NEEDS_REVIEW"
                              ? "검토 필요"
                              : "거래 없음"
                      }
                      disabled
                    />
                  </Field>
                  <Field id="trackingStatus" label="추적 상태">
                    <select
                      id="trackingStatus"
                      className={inputClass}
                      value={values.trackingStatus}
                      onChange={(event) =>
                        setValue(
                          "trackingStatus",
                          event.target
                            .value as PortfolioFormValues["trackingStatus"],
                        )
                      }
                    >
                      <option value="NONE">추적 안 함</option>
                      <option value="WATCHLIST">관심</option>
                      <option value="REENTRY_WATCH">재진입 관심</option>
                    </select>
                  </Field>
                </>
              ) : (
                <Field id="holdingStatus" label="등록 유형">
                  <select
                    id="holdingStatus"
                    className={inputClass}
                    value={values.holdingStatus}
                    onChange={(event) => {
                      const status = event.target
                        .value as PortfolioFormValues["holdingStatus"];
                      setValue("holdingStatus", status);
                      setValue(
                        "trackingStatus",
                        status === "REENTRY_WATCH"
                          ? "REENTRY_WATCH"
                          : status === "WATCHLIST"
                            ? "WATCHLIST"
                            : "NONE",
                      );
                    }}
                  >
                    <option value="HOLDING">보유 종목 (최초 매수 포함)</option>
                    <option value="WATCHLIST">관심 종목</option>
                    <option value="REENTRY_WATCH">재진입 관심</option>
                  </select>
                </Field>
              )}
              <Field
                id="quantity"
                label={item ? "현재 수량 (거래원장 자동 계산)" : "최초 매수수량"}
                error={errors.quantity}
                hint={
                  crypto ? "암호자산 수량은 소수점 이하 8자리까지 입력합니다." : undefined
                }
              >
                <input
                  id="quantity"
                  type="text"
                  inputMode="decimal"
                  className={inputClass}
                  value={values.quantity}
                  onChange={(event) => setValue("quantity", event.target.value)}
                  disabled={Boolean(item) || values.holdingStatus !== "HOLDING"}
                  aria-invalid={Boolean(errors.quantity)}
                  aria-describedby={describedBy("quantity")}
                />
              </Field>
              <Field
                id="averagePrice"
                label={
                  item
                    ? "현재 평균단가 (거래원장 자동 계산)"
                    : "최초 매수단가"
                }
                error={errors.averagePrice}
              >
                <input
                  id="averagePrice"
                  type="text"
                  inputMode="decimal"
                  className={inputClass}
                  value={values.averagePrice}
                  onChange={(event) =>
                    setValue("averagePrice", event.target.value)
                  }
                  disabled={Boolean(item) || values.holdingStatus !== "HOLDING"}
                  aria-invalid={Boolean(errors.averagePrice)}
                  aria-describedby={describedBy("averagePrice")}
                />
              </Field>
              {!item && values.holdingStatus === "HOLDING" ? (
                <>
                  <Field
                    id="initialTradedAt"
                    label="최초 매수일시"
                    error={errors.initialTradedAt}
                  >
                    <input
                      id="initialTradedAt"
                      type="datetime-local"
                      className={inputClass}
                      value={values.initialTradedAt}
                      onChange={(event) =>
                        setValue("initialTradedAt", event.target.value)
                      }
                      aria-invalid={Boolean(errors.initialTradedAt)}
                    />
                  </Field>
                  <Field
                    id="initialFeeAmount"
                    label="최초 매수 수수료"
                    error={errors.initialFeeAmount}
                  >
                    <input
                      id="initialFeeAmount"
                      inputMode="decimal"
                      className={inputClass}
                      value={values.initialFeeAmount}
                      onChange={(event) =>
                        setValue("initialFeeAmount", event.target.value)
                      }
                    />
                  </Field>
                  <Field
                    id="initialTaxAmount"
                    label="최초 매수 세금"
                    error={errors.initialTaxAmount}
                  >
                    <input
                      id="initialTaxAmount"
                      inputMode="decimal"
                      className={inputClass}
                      value={values.initialTaxAmount}
                      onChange={(event) =>
                        setValue("initialTaxAmount", event.target.value)
                      }
                    />
                  </Field>
                </>
              ) : null}
            </div>
          </section>

          <section className="mt-6 border-t border-border pt-5">
            <button
              type="button"
              aria-expanded={optionalOpen}
              aria-controls="optional-portfolio-fields"
              onClick={() => setOptionalOpen((current) => !current)}
              className="flex min-h-11 w-full items-center justify-between rounded-xl border border-border bg-card px-4 text-sm font-bold"
            >
              선택 정보
              <span>{optionalOpen ? "접기" : "펼치기"}</span>
            </button>
            {optionalOpen ? (
              <div
                id="optional-portfolio-fields"
                className="mt-5 grid gap-5 sm:grid-cols-2"
              >
                <Field id="investmentHorizon" label="투자 기간">
                  <select
                    id="investmentHorizon"
                    className={inputClass}
                    value={values.investmentHorizon}
                    onChange={(event) =>
                      setValue(
                        "investmentHorizon",
                        event.target
                          .value as PortfolioFormValues["investmentHorizon"],
                      )
                    }
                  >
                    <option value="UNSET">미설정</option>
                    <option value="SCALP">단타</option>
                    <option value="SHORT">단기</option>
                    <option value="MEDIUM">중기</option>
                    <option value="LONG">장기</option>
                  </select>
                </Field>
                <Field
                  id="targetAllocation"
                  label="목표 비중 (%)"
                  error={errors.targetAllocation}
                >
                  <input
                    id="targetAllocation"
                    type="text"
                    inputMode="decimal"
                    className={inputClass}
                    value={values.targetAllocation}
                    onChange={(event) =>
                      setValue("targetAllocation", event.target.value)
                    }
                    aria-invalid={Boolean(errors.targetAllocation)}
                  />
                </Field>
                <Field
                  id="maxLossPercent"
                  label="최대 손실률 (%)"
                  error={errors.maxLossPercent}
                >
                  <input
                    id="maxLossPercent"
                    type="text"
                    inputMode="decimal"
                    className={inputClass}
                    value={values.maxLossPercent}
                    onChange={(event) =>
                      setValue("maxLossPercent", event.target.value)
                    }
                    aria-invalid={Boolean(errors.maxLossPercent)}
                  />
                </Field>
                <div className="sm:col-span-2">
                  <Field id="strategy" label="전략" error={errors.strategy}>
                    <textarea
                      id="strategy"
                      className={`${inputClass} min-h-24 py-3`}
                      value={values.strategy}
                      onChange={(event) =>
                        setValue("strategy", event.target.value)
                      }
                      aria-invalid={Boolean(errors.strategy)}
                    />
                  </Field>
                </div>
                <div className="sm:col-span-2">
                  <Field id="notes" label="메모" error={errors.notes}>
                    <textarea
                      id="notes"
                      className={`${inputClass} min-h-28 py-3`}
                      value={values.notes}
                      onChange={(event) => setValue("notes", event.target.value)}
                      aria-invalid={Boolean(errors.notes)}
                    />
                  </Field>
                </div>
              </div>
            ) : null}
          </section>

          {serverMessage ? (
            <p
              className="mt-5 rounded-xl border border-red/40 bg-red/10 px-4 py-3 text-sm text-red"
              role="alert"
            >
              {serverMessage}
            </p>
          ) : null}
          {duplicate ? (
            <div className="mt-3 rounded-xl border border-cyan/40 bg-cyan/10 p-4 text-sm">
              <p className="font-bold">
                {duplicate.archived
                  ? "같은 종목의 보관 카드가 있습니다."
                  : "이미 등록된 종목입니다."}
              </p>
              <p className="mt-1 text-secondary">
                새 카드를 만들지 않고 기존 종목을 사용합니다.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void onDuplicate(duplicate.id, "view")}
                  className="min-h-10 rounded-lg border border-border px-3 font-semibold"
                >
                  기존 종목으로 이동
                </button>
                <button
                  type="button"
                  onClick={() =>
                    void onDuplicate(
                      duplicate.id,
                      duplicate.archived ? "restore" : "buy",
                    )
                  }
                  className="min-h-10 rounded-lg bg-cyan px-3 font-bold text-background"
                >
                  {duplicate.archived ? "보관 종목 복원" : "매수 기록 추가"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDuplicate(null);
                    setServerMessage("");
                  }}
                  className="min-h-10 rounded-lg border border-border px-3 font-semibold"
                >
                  취소
                </button>
              </div>
            </div>
          ) : null}
        </div>
        <footer className="border-t border-border bg-surface px-5 py-4 sm:px-6">
          {confirmDiscard ? (
            <div className="mb-3 rounded-xl border border-yellow/40 bg-yellow/10 p-3 text-sm">
              <p className="font-semibold">저장하지 않은 변경이 있습니다.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmDiscard(false)}
                  className="min-h-10 rounded-lg border border-border px-3 font-semibold"
                >
                  계속 편집
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="min-h-10 rounded-lg bg-yellow px-3 font-bold text-background"
                >
                  변경 취소
                </button>
              </div>
            </div>
          ) : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={requestClose}
              disabled={saving}
              className="min-h-11 rounded-xl border border-border px-5 font-semibold text-secondary hover:text-foreground disabled:opacity-50"
            >
              닫기
            </button>
            <button
              type="submit"
              disabled={saving}
              className="min-h-11 rounded-xl bg-cyan px-5 font-bold text-background disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "저장 중…" : item ? "변경 저장" : "종목 등록"}
            </button>
          </div>
        </footer>
      </form>
    </Dialog>
  );
}
