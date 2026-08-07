"use client";

import Link from "next/link";
import {
  type FormEvent,
  useDeferredValue,
  useEffect,
  useState,
} from "react";
import { Dialog } from "@/components/common/dialog";
import { Card, EmptyState, PageHeader } from "@/components/common/ui";
import {
  confidenceLabels,
  countImportantInformation,
  directionLabels,
  formatAnalysisTime,
  selectWatchIssues,
} from "@/lib/analysis-display";
import {
  getAllImpacts,
  getDecisionReviews,
} from "@/lib/api/analysis";
import { ApiClientError } from "@/lib/api/client";
import {
  createPortfolio,
  getPortfolioSummary,
  listPortfolio,
  updatePortfolioContext,
} from "@/lib/api/portfolio";
import {
  assetTypeLabels,
  currencyLabels,
  getAssetTypeLabel,
  getMarketLabel,
  investmentHorizonLabels,
  positionStatusLabels,
  trackingStatusLabels,
} from "@/lib/display-labels";
import {
  applyMarketDefaults,
} from "@/lib/portfolio-defaults";
import {
  formatEditableDecimal,
  formatPortfolioPrice,
  formatPortfolioQuantity,
} from "@/lib/portfolio-format";
import type {
  Currency,
  DecisionReview,
  InvestmentHorizon,
  PortfolioAssetType,
  PortfolioImpact,
  PortfolioItem,
  PortfolioSummary,
  PositionStatus,
  TrackingStatus,
} from "@/types/api";

type StatusFilter = "ALL" | "HOLDING" | "WATCHLIST" | "REENTRY_WATCH" | "CLOSED";

const marketOptions = [
  "KRX",
  "NASDAQ",
  "NYSE",
  "AMEX",
  "UPBIT",
  "BINANCE",
  "OTHER",
];
const assetTypeOptions: PortfolioAssetType[] = [
  "EQUITY",
  "ETF",
  "ADR",
  "CRYPTO",
  "OTHER",
];
const currencyOptions: Currency[] = ["KRW", "USD", "USDT", "OTHER"];

interface ContextDraft {
  assetType: PortfolioAssetType;
  name: string;
  symbol: string;
  market: string;
  currency: Currency;
  positionStatus: PositionStatus;
  trackingStatus: TrackingStatus;
  quantity: string;
  averageCost: string;
  investmentHorizon: InvestmentHorizon;
  memo: string;
}

const emptyDraft: ContextDraft = {
  assetType: "EQUITY",
  name: "",
  symbol: "",
  market: "KRX",
  currency: "KRW",
  positionStatus: "EMPTY",
  trackingStatus: "WATCHLIST",
  quantity: "0",
  averageCost: "",
  investmentHorizon: "UNSET",
  memo: "",
};

function draftFrom(item: PortfolioItem): ContextDraft {
  return {
    assetType: item.assetType,
    name: item.name,
    symbol: item.symbol,
    market: item.market,
    currency: item.currency,
    positionStatus: item.positionStatus,
    trackingStatus: item.trackingStatus,
    quantity: formatEditableDecimal(item.quantity),
    averageCost: formatEditableDecimal(item.averagePrice),
    investmentHorizon: item.investmentHorizon,
    memo: item.notes ?? "",
  };
}

function ContextForm({
  item,
  onClose,
  onSaved,
}: {
  item: PortfolioItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<ContextDraft>(
    item ? draftFrom(item) : emptyDraft,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [overrides, setOverrides] = useState({
    assetType: false,
    currency: false,
  });

  function set<K extends keyof ContextDraft>(key: K, value: ContextDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (item) {
        await updatePortfolioContext(item.id, {
          positionStatus: draft.positionStatus,
          trackingStatus: draft.trackingStatus,
          currentQuantity: draft.quantity,
          averageCost: draft.averageCost || null,
          currency: draft.currency,
          investmentHorizon: draft.investmentHorizon,
          memo: draft.memo || null,
        });
      } else {
        const holdingStatus =
          draft.positionStatus === "HOLDING"
            ? "HOLDING"
            : draft.positionStatus === "CLOSED"
              ? "SOLD"
              : draft.trackingStatus === "REENTRY_WATCH"
                ? "REENTRY_WATCH"
                : "WATCHLIST";
        await createPortfolio({
          assetType: draft.assetType,
          name: draft.name,
          symbol: draft.symbol,
          market: draft.market,
          currency: draft.currency,
          holdingStatus,
          trackingStatus: draft.trackingStatus,
          quantity: draft.quantity,
          averagePrice: draft.averageCost || null,
          investmentHorizon: draft.investmentHorizon,
          strategy: "",
          targetAllocation: null,
          maxLossPercent: null,
          notes: draft.memo || null,
          initialBuy: null,
        });
      }
      onSaved();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "보유정보를 저장하지 못했습니다.",
      );
    } finally {
      setSaving(false);
    }
  }

  const input =
    "min-h-11 w-full rounded-xl border border-border bg-card px-3 text-sm";
  return (
    <Dialog
      title={item ? "보유정보 수정" : "분석 종목 등록"}
      description="금융 앱에서 확인한 현재 수량·평균단가를 분석 참조값으로 저장합니다. 거래원장은 생성하지 않습니다."
      onRequestClose={onClose}
    >
      <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
        <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            {!item ? (
              <>
                <label className="text-sm font-semibold">
                  종목명
                  <input
                    data-autofocus="true"
                    className={`${input} mt-1.5`}
                    value={draft.name}
                    onChange={(event) => set("name", event.target.value)}
                    placeholder="예: 삼성전자, 인텔, 로켓랩"
                    required
                  />
                </label>
                <label className="text-sm font-semibold">
                  종목코드
                  <input
                    className={`${input} mt-1.5 uppercase`}
                    value={draft.symbol}
                    onChange={(event) => set("symbol", event.target.value)}
                    placeholder="예: 005930, INTC, RKLB"
                    required
                  />
                </label>
                <label className="text-sm font-semibold">
                  시장
                  <select
                    className={`${input} mt-1.5 uppercase`}
                    value={draft.market}
                    onChange={(event) =>
                      setDraft((current) =>
                        applyMarketDefaults(
                          current,
                          event.target.value,
                          overrides,
                        ),
                      )
                    }
                    required
                  >
                    {marketOptions.map((value) => (
                      <option key={value} value={value}>
                        {getMarketLabel(value)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  자산 종류
                  <select
                    className={`${input} mt-1.5`}
                    value={draft.assetType}
                    onChange={(event) => {
                      setOverrides((current) => ({
                        ...current,
                        assetType: true,
                      }));
                      set(
                        "assetType",
                        event.target.value as PortfolioAssetType,
                      );
                    }}
                  >
                    {assetTypeOptions.map((value) => (
                      <option key={value} value={value}>
                        {assetTypeLabels[value]}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
            <label className="text-sm font-semibold">
              현재 상태
              <select
                data-autofocus={item ? "true" : undefined}
                className={`${input} mt-1.5`}
                value={draft.positionStatus}
                onChange={(event) =>
                  set("positionStatus", event.target.value as PositionStatus)
                }
              >
                {Object.entries(positionStatusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              추적 상태
              <select
                className={`${input} mt-1.5`}
                value={draft.trackingStatus}
                onChange={(event) =>
                  set("trackingStatus", event.target.value as TrackingStatus)
                }
              >
                {Object.entries(trackingStatusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              현재 보유수량
              <input
                type="number"
                step={draft.assetType === "CRYPTO" ? "0.00000001" : "any"}
                min="0"
                className={`${input} mt-1.5`}
                value={draft.quantity}
                onChange={(event) => set("quantity", event.target.value)}
              />
            </label>
            <label className="text-sm font-semibold">
              현재 평균단가
              <input
                type="number"
                step={
                  draft.currency === "KRW"
                    ? "1"
                    : draft.currency === "USD"
                      ? "0.01"
                      : "any"
                }
                min="0"
                className={`${input} mt-1.5`}
                value={draft.averageCost}
                onChange={(event) => set("averageCost", event.target.value)}
              />
            </label>
            <label className="text-sm font-semibold">
              통화
              <select
                className={`${input} mt-1.5`}
                value={draft.currency}
                onChange={(event) => {
                  setOverrides((current) => ({
                    ...current,
                    currency: true,
                  }));
                  set("currency", event.target.value as Currency)
                }}
              >
                {currencyOptions.map((value) => (
                  <option key={value} value={value}>
                    {currencyLabels[value]}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              투자 기간
              <select
                className={`${input} mt-1.5`}
                value={draft.investmentHorizon}
                onChange={(event) =>
                  set(
                    "investmentHorizon",
                    event.target.value as InvestmentHorizon,
                  )
                }
              >
                {Object.entries(investmentHorizonLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold sm:col-span-2">
              메모
              <textarea
                className={`${input} mt-1.5 min-h-24 py-3`}
                value={draft.memo}
                onChange={(event) => set("memo", event.target.value)}
              />
            </label>
          </div>
          {error ? <p className="mt-4 text-sm text-red">{error}</p> : null}
        </div>
        <footer className="flex justify-end gap-2 border-t border-border p-4">
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 rounded-xl border border-border px-4 font-semibold"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={saving}
            className="min-h-11 rounded-xl bg-cyan px-4 font-bold text-background disabled:opacity-50"
          >
            {saving ? "저장 중…" : "저장"}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}

export function PortfolioClient() {
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [reviews, setReviews] = useState<DecisionReview[]>([]);
  const [impacts, setImpacts] = useState<PortfolioImpact[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [formItem, setFormItem] = useState<PortfolioItem | "new" | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      listPortfolio(
        {
          positionStatus:
            filter === "HOLDING" || filter === "CLOSED" ? filter : "",
          trackingStatus:
            filter === "WATCHLIST" || filter === "REENTRY_WATCH" ? filter : "",
          query: deferredQuery,
          limit: 100,
        },
        controller.signal,
      ),
      getPortfolioSummary(controller.signal),
      getDecisionReviews(controller.signal),
      getAllImpacts(controller.signal),
    ])
      .then(([portfolio, counts, currentReviews, currentImpacts]) => {
        setItems(portfolio.items);
        setSummary(counts);
        setReviews(currentReviews);
        setImpacts(currentImpacts);
        setError("");
      })
      .catch((reason) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setSummary(null);
        setError("분석 종목을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [deferredQuery, filter, refreshKey]);

  function refresh() {
    setLoading(true);
    setSummary(null);
    setRefreshKey((value) => value + 1);
  }

  const countCards: Array<[StatusFilter, string, number | null]> = [
    ["HOLDING", "보유", summary?.holding ?? null],
    ["WATCHLIST", "관심", summary?.watchlist ?? null],
    ["REENTRY_WATCH", "재진입 관심", summary?.reentryWatch ?? null],
    ["CLOSED", "청산 완료", summary?.closed ?? null],
  ];
  const reviewsByPortfolio = new Map(
    reviews.map((review) => [review.portfolioItemId, review]),
  );

  return (
    <>
      <PageHeader
        eyebrow="분석 종목"
        title="분석 종목"
        description="보유 맥락과 공식·검증 정보를 기준으로 관리 방향을 검토합니다. 계좌 수익률·현재가·주문은 금융 앱에서 확인합니다."
      />
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {countCards.map(([value, label, count]) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(filter === value ? "ALL" : value)}
            className={`rounded-2xl border p-4 text-left ${
              filter === value
                ? "border-cyan bg-cyan/10"
                : "border-border bg-card"
            }`}
          >
            <span className="text-xs font-semibold text-secondary">{label}</span>
            <span className="mt-2 block text-2xl font-bold">
              {count ?? (loading ? "…" : "—")}
            </span>
            {count === null && !loading ? (
              <span className="mt-1 block text-xs text-red">집계 확인 실패</span>
            ) : null}
          </button>
        ))}
      </div>
      <Card>
        <div className="mb-5 flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <label
              htmlFor="portfolio-search"
              className="text-sm font-semibold"
            >
              종목명·종목코드 검색
            </label>
            <div className="mt-1.5 flex min-w-0 gap-2">
              <input
                id="portfolio-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="예: 삼성전자, 005930, INTC"
                className="min-h-11 min-w-0 flex-1 rounded-xl border border-border bg-surface px-3 sm:w-72"
              />
              {query ? (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="min-h-11 shrink-0 rounded-xl border border-border px-3 text-sm"
                  aria-label="검색어 지우기"
                >
                  지우기
                </button>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setFormItem("new")}
            className="min-h-11 rounded-xl bg-cyan px-4 font-bold text-background"
          >
            + 분석 종목 등록
          </button>
        </div>
        {loading ? (
          <p className="py-20 text-center text-secondary">분석 종목 불러오는 중…</p>
        ) : error ? (
          <div className="py-12 text-center">
            <p className="text-red">{error}</p>
            <button type="button" onClick={refresh} className="mt-4 underline">
              다시 시도
            </button>
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title="조건에 맞는 분석 종목이 없습니다."
            detail="분석 종목 등록에서 보유 또는 관심 대상을 추가하세요."
          />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {items.map((item) => {
              const itemReview = reviewsByPortfolio.get(item.id);
              const itemImpacts = impacts.filter(
                (impact) => impact.portfolioItemId === item.id,
              );
              const importantCount = countImportantInformation(itemImpacts);
              const watchCount = selectWatchIssues(itemImpacts).length;
              return (
                <article
                key={item.id}
                className="min-w-0 rounded-2xl border border-border bg-surface p-4 sm:p-5"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold">{item.name}</h2>
                    <p className="mt-1 text-sm text-secondary">
                      {item.symbol} · {getMarketLabel(item.market)} ·{" "}
                      {getAssetTypeLabel(item.assetType)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="rounded-full border border-border px-2.5 py-1 text-xs">
                      {positionStatusLabels[item.positionStatus]}
                    </span>
                    {item.trackingStatus !== "NONE" ? (
                      <span className="rounded-full border border-cyan/40 px-2.5 py-1 text-xs text-cyan">
                        {trackingStatusLabels[item.trackingStatus]}
                      </span>
                    ) : null}
                  </div>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-muted">보유수량</dt>
                    <dd className="mt-1 font-semibold">
                      {formatPortfolioQuantity(
                        item.quantity,
                        item.assetType,
                        item.symbol,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">평균단가</dt>
                    <dd className="mt-1 font-semibold">
                      {item.averagePrice
                        ? formatPortfolioPrice(item.averagePrice, item.currency)
                        : "미입력"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">현재 관리 방향</dt>
                    <dd className="mt-1 font-semibold">
                      {itemReview
                        ? directionLabels[itemReview.direction]
                        : "데이터 부족"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">분석 신뢰도</dt>
                    <dd className="mt-1">
                      {itemReview
                        ? confidenceLabels[itemReview.confidence]
                        : "낮음"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">새 중요 정보</dt>
                    <dd className="mt-1">{importantCount}건</dd>
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <dt className="text-xs text-muted">마지막 분석 시각</dt>
                    <dd className="mt-1">
                      {itemReview?.id
                        ? formatAnalysisTime(itemReview.generatedAt)
                        : "분석 기록 없음"}
                    </dd>
                  </div>
                </dl>
                {watchCount > 0 ? (
                  <span className="mt-4 inline-flex rounded-full border border-amber-400/40 px-2.5 py-1 text-xs text-amber-300">
                    주시할 이슈 {watchCount}건
                  </span>
                ) : null}
                <div className="mt-5 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                  <Link
                    href={`/portfolio/${item.id}`}
                    className="inline-flex min-h-11 items-center justify-center rounded-xl bg-cyan px-4 text-sm font-bold text-background"
                  >
                    분석 보기
                  </Link>
                  <button
                    type="button"
                    onClick={() => setFormItem(item)}
                    className="min-h-11 rounded-xl border border-border px-4 text-sm font-semibold"
                  >
                    보유정보 수정
                  </button>
                </div>
              </article>
              );
            })}
          </div>
        )}
      </Card>
      {formItem ? (
        <ContextForm
          key={formItem === "new" ? "new" : formItem.id}
          item={formItem === "new" ? null : formItem}
          onClose={() => setFormItem(null)}
          onSaved={() => {
            setFormItem(null);
            refresh();
          }}
        />
      ) : null}
    </>
  );
}
