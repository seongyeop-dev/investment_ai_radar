"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, EmptyState, PageHeader } from "@/components/common/ui";
import { TransactionHistory } from "@/components/portfolio/transaction-history";
import {
  confidenceLabels,
  directionLabels,
  formatAnalysisTime,
  selectEvidence,
  selectWatchIssues,
  thesisStatusLabels,
} from "@/lib/analysis-display";
import {
  acknowledgeDecisionReview,
  getAnalysisPacket,
  getDecisionReview,
  getEconomicEvents,
  getImpacts,
  refreshDecisionReview,
} from "@/lib/api/analysis";
import { ApiClientError } from "@/lib/api/client";
import { getPortfolio } from "@/lib/api/portfolio";
import { getPortfolioMappings } from "@/lib/api/providers";
import { getSystemInfo } from "@/lib/api/system";
import {
  getAssetTypeLabel,
  getInvestmentHorizonLabel,
  getMarketLabel,
  getPositionStatusLabel,
  getTrackingStatusLabel,
} from "@/lib/display-labels";
import { verificationLabels } from "@/lib/news";
import {
  formatPortfolioPrice,
  formatPortfolioQuantity,
} from "@/lib/portfolio-format";
import type {
  AnalysisPacket,
  DecisionReview,
  EconomicEvent,
  InstrumentMapping,
  PortfolioImpact,
  PortfolioItem,
  SystemInfo,
} from "@/types/api";

const mappingStatusLabels: Record<string, string> = {
  VERIFIED: "검증 완료",
  CANDIDATE: "후보 확인 필요",
  UNRESOLVED: "미확인",
  CONFLICTING: "충돌 확인 필요",
  UNSUPPORTED: "지원하지 않음",
  STALE: "재검증 필요",
};

const providerLabels: Record<string, string> = {
  OPENDART: "OpenDART",
  SEC_EDGAR: "SEC",
};

function SourceLinks({ impact }: { impact: PortfolioImpact }) {
  const links = Array.from(
    new Map(impact.sourceLinks.map((link) => [link.url, link])).values(),
  );
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {links.map((link) => (
        <a
          key={link.url}
          href={link.url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-cyan underline"
        >
          {link.title}
        </a>
      ))}
    </div>
  );
}

function EvidenceList({
  title,
  items,
}: {
  title: string;
  items: PortfolioImpact[];
}) {
  return (
    <section>
      <h3 className="text-sm font-bold">{title}</h3>
      <div className="mt-2 space-y-2">
        {items.map((impact) => (
          <article
            key={impact.id}
            className="rounded-xl border border-border bg-surface p-3"
          >
            <p className="font-semibold">{impact.oneLineSummary}</p>
            <p className="mt-1 text-xs text-muted">
              {verificationLabels[impact.verificationStatus]} · 근거 강도{" "}
              {confidenceLabels[impact.evidenceStrength]}
            </p>
            <SourceLinks impact={impact} />
          </article>
        ))}
      </div>
    </section>
  );
}

export function PortfolioDetailClient() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [item, setItem] = useState<PortfolioItem | null>(null);
  const [impacts, setImpacts] = useState<PortfolioImpact[]>([]);
  const [review, setReview] = useState<DecisionReview | null>(null);
  const [packet, setPacket] = useState<AnalysisPacket | null>(null);
  const [events, setEvents] = useState<EconomicEvent[]>([]);
  const [mappings, setMappings] = useState<InstrumentMapping[]>([]);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getPortfolio(id, controller.signal),
      getImpacts(id, controller.signal),
      getDecisionReview(id, controller.signal),
      getAnalysisPacket(id, controller.signal),
      getEconomicEvents(true, controller.signal),
      getSystemInfo(controller.signal),
      getPortfolioMappings(id, controller.signal),
    ])
      .then(
        ([
          portfolio,
          currentImpacts,
          currentReview,
          currentPacket,
          economicEvents,
          systemInfo,
          portfolioMappings,
        ]) => {
          setItem(portfolio);
          setImpacts(currentImpacts);
          setReview(currentReview);
          setPacket(currentPacket);
          setEvents(
            economicEvents.filter((event) =>
              event.relatedPortfolioItemIds.includes(id),
            ),
          );
          setSystem(systemInfo);
          setMappings(portfolioMappings);
          setError("");
        },
      )
      .catch((reason) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setError("종목 분석 정보를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [id]);

  async function refreshReview() {
    setRefreshing(true);
    setActionMessage("");
    try {
      const next = await refreshDecisionReview(id);
      const [nextImpacts, nextPacket] = await Promise.all([
        getImpacts(id),
        getAnalysisPacket(id),
      ]);
      setReview(next);
      setImpacts(nextImpacts);
      setPacket(nextPacket);
      setActionMessage(
        next.id === review?.id
          ? "새 검증 정보가 없어 기존 분석을 유지했습니다."
          : "저장된 검증 정보로 분석을 갱신했습니다.",
      );
    } catch {
      setActionMessage("분석을 갱신하지 못했습니다.");
    } finally {
      setRefreshing(false);
    }
  }

  async function acknowledge() {
    const next = await acknowledgeDecisionReview(
      id,
      "사용자가 규칙 기반 검토 결과를 확인함",
    );
    setReview(next);
    setActionMessage("사용자 확인을 기록했습니다.");
  }

  async function copyPacket() {
    if (!packet) return;
    let localized = packet.copyText
      .replace(
        `상태: ${packet.positionStatus} / ${packet.trackingStatus}`,
        `상태: ${getPositionStatusLabel(packet.positionStatus)} / ${getTrackingStatusLabel(packet.trackingStatus)}`,
      )
      .replace(
        `보유수량: ${packet.quantity}`,
        `보유수량: ${formatPortfolioQuantity(
          packet.quantity,
          item?.assetType ?? "OTHER",
          packet.symbol,
        )}`,
      )
      .replace(
        `평균단가: ${packet.averageCost ?? "미입력"} ${item?.currency ?? ""}`.trim(),
        `평균단가: ${formatPortfolioPrice(
          packet.averageCost,
          item?.currency ?? "OTHER",
        )}`,
      )
      .replace(
        `투자기간: ${packet.investmentHorizon}`,
        `투자기간: ${getInvestmentHorizonLabel(packet.investmentHorizon)}`,
      )
      .replace(
        `자동 분석 상태: ${packet.decisionReview.thesisStatus}`,
        `자동 분석 상태: ${thesisStatusLabels[packet.decisionReview.thesisStatus]}`,
      )
      .replace(
        `현재 규칙 기반 방향: ${packet.decisionReview.direction}`,
        `현재 규칙 기반 방향: ${directionLabels[packet.decisionReview.direction]}`,
      );
    for (const [value, label] of Object.entries(verificationLabels)) {
      localized = localized.replaceAll(`[${value}]`, `[${label}]`);
    }
    await navigator.clipboard.writeText(localized);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  if (loading) return <p className="py-24 text-center">분석 정보 불러오는 중…</p>;
  if (error || !item || !review || !packet || !system) {
    return <EmptyState title="분석 정보를 열 수 없습니다." detail={error} />;
  }

  const positiveEvidence = selectEvidence(impacts, "positive");
  const negativeEvidence = selectEvidence(impacts, "negative");
  const watchIssues = selectWatchIssues(impacts);
  const currentImpacts = impacts.filter(
    (impact) => impact.verificationStatus !== "STALE_REUSED",
  );
  const emptyAnalysis =
    review.direction === "INSUFFICIENT_DATA" &&
    positiveEvidence.length === 0 &&
    negativeEvidence.length === 0 &&
    watchIssues.length === 0 &&
    events.length === 0;
  const lastCollection =
    system.lastProviderSyncAt ?? system.lastSuccessfulNewsSyncAt;
  const hasEvidence =
    positiveEvidence.length > 0 || negativeEvidence.length > 0;
  const visibleSectionKeys = [
    "status",
    "summary",
    ...(hasEvidence ? ["evidence"] : []),
    ...(watchIssues.length ? ["watch"] : []),
    ...(events.length ? ["schedule"] : []),
    "timeline",
    ...(packet.officialSourceLinks.length ? ["sources"] : []),
    "copy",
    "ledger",
  ];
  const sectionTitle = (key: string, label: string) =>
    `${visibleSectionKeys.indexOf(key) + 1}. ${label}`;
  const analysisVerification = currentImpacts.length
    ? verificationLabels[currentImpacts[0].verificationStatus]
    : "검증 자료 없음";
  const mappingSummary = mappings.length
    ? mappings
        .map(
          (mapping) =>
            `${providerLabels[mapping.provider] ?? mapping.provider} ${
              mappingStatusLabels[mapping.mappingStatus] ?? "상태 확인 필요"
            }`,
        )
        .join(" · ")
    : "미확인";

  return (
    <>
      <PageHeader
        eyebrow="종목 분석"
        title={item.name}
        description={`${item.symbol} · ${getMarketLabel(item.market)} · ${getAssetTypeLabel(item.assetType)}. 공개된 검증 자료의 규칙 기반 초안이며 최종 판단과 주문은 사용자가 별도 금융 앱에서 수행합니다.`}
      />
      <div className="mb-5 flex flex-wrap gap-2">
        <Link
          href="/portfolio"
          className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-sm font-semibold"
        >
          ← 분석 종목
        </Link>
        <Link
          href="/portfolio"
          className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-sm font-semibold"
        >
          보유정보 수정
        </Link>
      </div>
      <div className="space-y-5">
        <Card title={sectionTitle("status", "현재 관리 상태")}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["포지션", getPositionStatusLabel(item.positionStatus)],
              ["추적", getTrackingStatusLabel(item.trackingStatus)],
              [
                "보유수량",
                formatPortfolioQuantity(item.quantity, item.assetType, item.symbol),
              ],
              [
                "평균단가",
                formatPortfolioPrice(item.averagePrice, item.currency),
              ],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-border bg-surface p-3"
              >
                <p className="text-xs text-muted">{label}</p>
                <p className="mt-1 font-semibold">{value}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card title={sectionTitle("summary", "자동 분석 요약")}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-cyan/30 bg-cyan/5 p-4 sm:col-span-2">
              <p className="text-xs font-semibold text-cyan">현재 관리 방향</p>
              <p className="mt-2 text-2xl font-bold">
                {directionLabels[review.direction]}
              </p>
              <p className="mt-2 text-sm leading-6 text-secondary">
                {review.whyNow}
              </p>
            </div>
            {[
              ["투자근거 상태", thesisStatusLabels[review.thesisStatus]],
              ["분석 신뢰도", confidenceLabels[review.confidence]],
              ["근거 강도", confidenceLabels[review.evidenceStrength]],
              ["검증 상태", analysisVerification],
              [
                "마지막 분석 시각",
                review.id ? formatAnalysisTime(review.generatedAt) : "분석 기록 없음",
              ],
              ["분석 유효기간", formatAnalysisTime(review.validUntil)],
              ["자동화 방식", "규칙 기반"],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-border bg-surface p-3"
              >
                <p className="text-xs text-muted">{label}</p>
                <p className="mt-1 font-semibold">{value}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted">
            사용자 최종 확인 필요 · 현재가·목표가·주문 정보는 생성하지 않습니다.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={refreshing}
              onClick={() => void refreshReview()}
              className="min-h-11 rounded-xl border border-border px-4 text-sm font-semibold disabled:opacity-50"
            >
              {refreshing ? "분석 중…" : "분석 새로고침"}
            </button>
            <button
              type="button"
              onClick={() => void acknowledge()}
              className="min-h-11 rounded-xl border border-border px-4 text-sm font-semibold"
            >
              사용자 확인 기록
            </button>
            {actionMessage ? (
              <p className="text-sm text-secondary">{actionMessage}</p>
            ) : null}
          </div>
        </Card>

        {emptyAnalysis ? (
          <Card>
            <div className="rounded-2xl border border-dashed border-border p-5">
              <h2 className="text-lg font-bold">
                아직 분석할 검증 정보가 없습니다.
              </h2>
              <p className="mt-2 text-sm leading-6 text-secondary">
                공식 공시와 검증 뉴스가 연결되면 이 종목의 관리 방향, 긍정·부정
                근거와 주시할 이슈를 자동으로 정리합니다.
              </p>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
                <div>
                  <dt className="text-xs text-muted">OpenDART</dt>
                  <dd className="mt-1">
                    {system.openDartConfigured ? "설정됨" : "미설정"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">SEC</dt>
                  <dd className="mt-1">
                    {system.secConfigured ? "설정됨" : "미설정"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">뉴스·IR 데이터 제공자</dt>
                  <dd className="mt-1">
                    {system.newsProvidersConfigured ? "설정됨" : "미설정"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">종목 연결 상태</dt>
                  <dd className="mt-1">{mappingSummary}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">최근 수집 시각</dt>
                  <dd className="mt-1">{formatAnalysisTime(lastCollection)}</dd>
                </div>
              </dl>
            </div>
          </Card>
        ) : null}

        {hasEvidence ? (
          <Card title={sectionTitle("evidence", "핵심 근거")}>
            <div className="grid gap-4 lg:grid-cols-2">
              {positiveEvidence.length ? (
                <EvidenceList title="긍정 근거" items={positiveEvidence} />
              ) : null}
              {negativeEvidence.length ? (
                <EvidenceList title="부정 근거" items={negativeEvidence} />
              ) : null}
            </div>
          </Card>
        ) : null}

        {watchIssues.length ? (
          <Card title={sectionTitle("watch", "주시할 이슈")}>
            <div className="grid gap-3 lg:grid-cols-2">
              {watchIssues.map((impact) => (
                <article
                  key={impact.id}
                  className="rounded-xl border border-border bg-surface p-4"
                >
                  <p className="font-bold">{impact.oneLineSummary}</p>
                  <p className="mt-2 text-sm leading-6 text-secondary">
                    {impact.conditionsToWatch[0] ??
                      "공식 자료의 후속 변경을 확인해야 합니다."}
                  </p>
                  <p className="mt-2 text-xs text-muted">
                    {verificationLabels[impact.verificationStatus]} · 중요도{" "}
                    {confidenceLabels[impact.impactStrength]} · 기준{" "}
                    {formatAnalysisTime(impact.generatedAt)}
                  </p>
                  <SourceLinks impact={impact} />
                </article>
              ))}
            </div>
          </Card>
        ) : null}

        {events.length ? (
          <Card title={sectionTitle("schedule", "다음 확인 일정")}>
            <div className="space-y-3">
              {events.slice(0, 3).map((event) => (
                <article
                  key={event.id}
                  className="rounded-xl border border-border bg-surface p-4"
                >
                  <p className="font-bold">{event.title}</p>
                  <p className="mt-1 text-sm text-secondary">
                    {formatAnalysisTime(event.scheduledAt)} ·{" "}
                    {event.officialSourceName}
                  </p>
                  <a
                    href={event.officialSourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-block text-xs text-cyan underline"
                  >
                    공식 일정 원문
                  </a>
                </article>
              ))}
            </div>
          </Card>
        ) : null}

        <Card title={sectionTitle("timeline", "정보 타임라인")}>
          <div id="timeline" className="space-y-3">
            {currentImpacts.length ? (
              currentImpacts.slice(0, 10).map((impact) => (
                <div key={impact.id} className="border-l-2 border-cyan/40 pl-4">
                  <time className="text-xs text-muted">
                    {formatAnalysisTime(impact.generatedAt)}
                  </time>
                  <p className="mt-1 text-sm">{impact.oneLineSummary}</p>
                  <p className="mt-1 text-xs text-muted">
                    {verificationLabels[impact.verificationStatus]} · 규칙 기반
                  </p>
                  <SourceLinks impact={impact} />
                </div>
              ))
            ) : (
              <p className="text-sm text-secondary">
                연결된 최신 검증 사건이 없습니다.
              </p>
            )}
          </div>
        </Card>

        {packet.officialSourceLinks.length ? (
          <Card title={sectionTitle("sources", "공식 원문")}>
            <div className="flex flex-wrap gap-2">
              {packet.officialSourceLinks.map((link) => (
                <a
                  key={link.url}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-xl border border-border px-3 py-2 text-sm text-cyan underline"
                >
                  {link.title}
                </a>
              ))}
            </div>
          </Card>
        ) : null}

        <Card title={sectionTitle("copy", "분석용 복사")}>
          <p className="text-sm leading-6 text-secondary">
            공개 정보·구조화 요약·원문 링크만 복사합니다. 기사·공시 전문과
            가격 차트는 포함하지 않습니다.
          </p>
          <button
            type="button"
            onClick={() => void copyPacket()}
            className="mt-4 min-h-11 rounded-xl bg-cyan px-4 font-bold text-background"
          >
            {copied ? "복사됨" : "ChatGPT 심층 분석용 복사"}
          </button>
        </Card>

        <Card title={sectionTitle("ledger", "고급 거래 기록")}>
          <details>
            <summary className="cursor-pointer font-semibold">
              기존 감사 원장 펼치기
            </summary>
            <p className="mt-2 text-sm leading-6 text-secondary">
              자동 분석값과 동기화하지 않습니다. 과거 거래 감사가 필요할 때만
              사용하세요.
            </p>
            <button
              type="button"
              onClick={() => setHistoryOpen(true)}
              className="mt-3 min-h-11 rounded-xl border border-border px-4 text-sm font-semibold"
            >
              고급 기록 열기
            </button>
          </details>
        </Card>
      </div>
      {historyOpen ? (
        <TransactionHistory
          item={item}
          onChanged={() => undefined}
          onClose={() => setHistoryOpen(false)}
        />
      ) : null}
    </>
  );
}
