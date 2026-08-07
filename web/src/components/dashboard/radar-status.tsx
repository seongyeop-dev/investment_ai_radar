"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { getDecisionReviews } from "@/lib/api/analysis";
import { getSystemInfo } from "@/lib/api/system";
import { getNextMarketBriefings } from "@/lib/api/operations";
import { getPortfolioSummary } from "@/lib/api/portfolio";
import { operatingModeLabels } from "@/lib/operations";
import type {
  MarketBriefingType,
  NextMarketBriefing,
  PortfolioSummary,
  DecisionReview,
  SystemInfo,
} from "@/types/api";

function time(value: string | null): string {
  return value ? new Date(value).toLocaleString("ko-KR") : "없음";
}

function providerStatus(info: SystemInfo): string {
  const configured =
    info.newsProvidersConfigured ||
    info.openDartConfigured ||
    info.secConfigured ||
    info.marketCalendarConfigured;
  if (!configured) return "데이터 제공자 미설정";
  if (info.newsProviderStatus === "ERROR") return "일부 수집 오류";
  return "설정됨";
}

function riskStatus(info: SystemInfo): string {
  if (!info.riskProfileConfigured) {
    return info.riskRecommendationAvailable
      ? "자동 제안 확인 필요"
      : "위험 설정 미설정";
  }
  if (
    info.riskRecommendationStale ||
    info.portfolioFingerprintChanged
  ) {
    return "등록 종목 변경 · 재검토 필요";
  }
  return "사용자 확인 완료";
}

function MetricGroup({
  title,
  emphasis = false,
  values,
}: {
  title: string;
  emphasis?: boolean;
  values: Array<[string, string | number]>;
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-bold text-secondary">{title}</h2>
      <div className={`grid gap-3 ${emphasis ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
        {values.map(([label, value]) => (
          <Card key={label}>
            <p className="text-xs font-semibold text-muted">{label}</p>
            <p className={`${emphasis ? "text-2xl" : "text-xl"} mt-2 font-bold`}>
              {value}
            </p>
          </Card>
        ))}
      </div>
    </section>
  );
}

export function RadarStatus() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [marketSchedules, setMarketSchedules] = useState<
    NextMarketBriefing[]
  >([]);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [reviews, setReviews] = useState<DecisionReview[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getSystemInfo(controller.signal),
      getNextMarketBriefings(controller.signal),
      getPortfolioSummary(controller.signal),
      getDecisionReviews(controller.signal),
    ])
      .then(([system, schedules, summary, currentReviews]) => {
        setInfo(system);
        setMarketSchedules(schedules.items);
        setPortfolio(summary);
        setReviews(currentReviews);
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setError("실제 시스템 상태를 불러오지 못했습니다.");
      });
    return () => controller.abort();
  }, []);
  if (error) return <Card><p className="text-red">{error}</p></Card>;
  if (!info) return <Card><p className="py-12 text-center">상태 확인 중…</p></Card>;

  const configured =
    info.newsProvidersConfigured || info.openDartConfigured || info.secConfigured;
  const briefingTime = (type: MarketBriefingType): string => {
    const schedule = marketSchedules.find(
      (item) => item.briefingType === type,
    );
    return schedule?.scheduledAtKst
      ? time(schedule.scheduledAtKst)
      : schedule?.scheduleStatus === "CLOSED"
        ? "휴장"
        : "일정 미설정";
  };
  const directionCount = (direction: DecisionReview["direction"]) =>
    reviews.filter((review) => review.direction === direction).length;
  return (
    <div className="space-y-7">
      {!configured ? (
        <div className="rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm">
          <p className="font-bold text-yellow">데이터 제공자 미설정</p>
          <p className="mt-1 text-secondary">
            출처·검증 상태 또는 시스템 상태에서 다음 연결 항목을 확인하세요.
          </p>
        </div>
      ) : null}
      <MetricGroup
        title="오늘 확인할 정보"
        emphasis
        values={[
          ["새 중요 사건", "측정 항목 없음"],
          ["공식 확인", `${info.disclosureDatabaseCount}건의 공식 공시`],
          ["정정·부인", info.correctedNewsCount + info.deniedNewsCount],
          ["발송 대기 브리핑", "측정 항목 없음"],
        ]}
      />
      <MetricGroup
        title="종목별 관리 방향"
        values={[
          ["추가매수 검토", directionCount("ADD_REVIEW")],
          ["유지", directionCount("HOLD")],
          ["관망", directionCount("WAIT")],
          ["비중축소 검토", directionCount("REDUCE_REVIEW")],
          ["손절·청산 검토", directionCount("EXIT_REVIEW")],
          ["데이터 부족", directionCount("INSUFFICIENT_DATA")],
        ]}
      />
      <MetricGroup
        title="등록 종목 현황"
        values={[
          ["보유", portfolio?.holding ?? 0],
          ["관심", portfolio?.watchlist ?? 0],
          ["재진입 관심", portfolio?.reentryWatch ?? 0],
          ["청산 완료", portfolio?.closed ?? 0],
          ["투자근거 미설정", portfolio?.thesisNotSet ?? 0],
          ["재검토 필요", portfolio?.needsReview ?? 0],
        ]}
      />
      <MetricGroup
        title="시장 브리핑"
        values={[
          [
            "다음 국내장 개장 전",
            briefingTime("KRX_PRE_OPEN"),
          ],
          [
            "다음 국내장 마감 후",
            briefingTime("KRX_POST_CLOSE"),
          ],
          [
            "다음 나스닥 개장 전",
            briefingTime("NASDAQ_PRE_OPEN"),
          ],
          [
            "다음 나스닥 마감 후",
            briefingTime("NASDAQ_POST_CLOSE"),
          ],
          [
            "시장 일정 상태",
            info.marketCalendarConfigured ? "설정됨" : "미설정",
          ],
          ["이메일 제공자", info.emailConfigured ? "설정됨" : "미설정"],
        ]}
      />
      <MetricGroup
        title="수집 상태"
        values={[
          ["뉴스 참조", info.newsDatabaseCount],
          ["공식 공시", info.disclosureDatabaseCount],
          ["통합 사건", info.eventCount],
          ["재탕 제외", info.staleReusedCount],
        ]}
      />
      <MetricGroup
        title="운영 상태"
        values={[
          [
            "수집 성공률",
            info.collectionSuccessRate === null
              ? "측정 전"
              : `${info.collectionSuccessRate}%`,
          ],
          ["마지막 성공 조사", time(info.lastSuccessfulNewsSyncAt)],
          ["운영 모드", operatingModeLabels[info.operatingMode]],
          ["위험 설정 상태", riskStatus(info)],
          ["데이터 제공자 상태", providerStatus(info)],
          ["정리 상태", info.retentionCleanupEnabled ? "활성" : "비활성"],
        ]}
      />
    </div>
  );
}
