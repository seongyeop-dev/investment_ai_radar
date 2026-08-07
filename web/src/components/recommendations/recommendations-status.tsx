"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { listPortfolio } from "@/lib/api/portfolio";
import {
  getRiskProfile,
  getRiskRecommendation,
} from "@/lib/api/risk-profile";
import { getSystemInfo } from "@/lib/api/system";

interface Readiness {
  portfolioCount: number;
  riskConfigured: boolean;
  riskRecommendationAvailable: boolean;
  riskRecommendationConfidence: string;
  riskPortfolioChanged: boolean;
  newsCount: number;
  disclosureCount: number;
  newsConfigured: boolean;
  disclosureConfigured: boolean;
}

type ReadinessStatus =
  | "준비 완료"
  | "미설정"
  | "데이터 부족"
  | "비활성"
  | "자동 제안 확인 필요"
  | "사용자 확인 완료"
  | "등록 종목 변경으로 재검토 필요";


const recommendationConfidenceLabels: Record<string, string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

function recommendationConfidenceLabel(
  value: string | null | undefined,
): string {
  if (!value) return "미설정";
  return recommendationConfidenceLabels[value] ?? "확인 필요";
}


export function RecommendationsStatus() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      listPortfolio({ includeArchived: false, limit: 1 }, controller.signal),
      getRiskProfile(controller.signal),
      getRiskRecommendation(controller.signal),
      getSystemInfo(controller.signal),
    ])
      .then(([portfolio, risk, recommendation, system]) => {
        setReadiness({
          portfolioCount: portfolio.total,
          riskConfigured: risk.configured,
          riskRecommendationAvailable: true,
          riskRecommendationConfidence: recommendation.confidence,
          riskPortfolioChanged: recommendation.portfolioChanged,
          newsCount: system.newsDatabaseCount,
          disclosureCount: system.disclosureDatabaseCount,
          newsConfigured: system.newsProvidersConfigured,
          disclosureConfigured:
            system.openDartConfigured || system.secConfigured,
        });
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") {
          return;
        }
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "추천 준비 상태를 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refreshKey]);

  const dataStatus = (
    configured: boolean | undefined,
    count: number | undefined,
  ): ReadinessStatus =>
    !configured ? "미설정" : count && count > 0 ? "준비 완료" : "데이터 부족";

  const rows: Array<{
    label: string;
    status: ReadinessStatus;
    detail: string;
  }> = [
    {
      label: "등록 종목",
      status:
        readiness && readiness.portfolioCount > 0 ? "준비 완료" : "미설정",
      detail: readiness ? `활성 항목 ${readiness.portfolioCount}건` : "확인 전",
    },
    {
      label: "위험 설정",
      status: !readiness?.riskConfigured
        ? readiness?.riskRecommendationAvailable
          ? "자동 제안 확인 필요"
          : "미설정"
        : readiness.riskPortfolioChanged
          ? "등록 종목 변경으로 재검토 필요"
          : "사용자 확인 완료",
      detail: readiness
        ? `자동 제안 신뢰도 ${recommendationConfidenceLabel(readiness.riskRecommendationConfidence)}`
        : "사용자가 확인한 투자 위험 한도 기준",
    },
    {
      label: "종목 검증",
      status: "데이터 부족",
      detail: "추천 입력으로 사용할 검증 상태가 아직 집계되지 않았습니다.",
    },
    {
      label: "공식 공시",
      status: dataStatus(
        readiness?.disclosureConfigured,
        readiness?.disclosureCount,
      ),
      detail: readiness ? `${readiness.disclosureCount}건` : "확인 전",
    },
    {
      label: "뉴스 검증",
      status: dataStatus(readiness?.newsConfigured, readiness?.newsCount),
      detail: readiness ? `${readiness.newsCount}건` : "확인 전",
    },
    {
      label: "가격 데이터",
      status: "비활성",
      detail: "현재 제품에서는 가격 수집을 추천 입력으로 사용하지 않습니다.",
    },
    {
      label: "추천 엔진",
      status: "비활성",
      detail: "추천 생성 기능은 연결하지 않았습니다.",
    },
  ];

  return (
    <Card title="추천 준비 상태">
      {loading ? (
        <div className="grid min-h-48 place-items-center">
          <p className="text-sm font-semibold text-secondary">
            준비 상태를 확인하는 중…
          </p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red/40 bg-red/10 p-5" role="alert">
          <p className="font-semibold text-red">{error}</p>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              setError("");
              setRefreshKey((value) => value + 1);
            }}
            className="mt-4 min-h-10 rounded-lg border border-red/40 px-4 text-sm font-bold text-red"
          >
            다시 시도
          </button>
        </div>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            {rows.map((row) => (
              <div
                key={row.label}
                className="flex min-w-0 items-start gap-3 rounded-xl border border-border bg-surface p-4"
              >
                <span aria-hidden="true" className="mt-0.5 text-cyan">
                  {row.status === "준비 완료" ? "✓" : "○"}
                </span>
                <div>
                  <p className="text-sm font-bold">{row.label}</p>
                  <p className="mt-1 text-xs font-semibold text-secondary">
                    {row.status}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-muted">
                    {row.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
          {!readiness?.riskConfigured ? (
            <Link
              href="/settings"
              className="mt-5 inline-flex min-h-11 items-center rounded-xl border border-cyan/40 px-4 text-sm font-bold text-cyan"
            >
              개인 설정으로 이동
            </Link>
          ) : null}
          <p className="mt-5 rounded-xl border border-border bg-surface p-4 text-sm leading-6 text-secondary">
            {readiness?.riskConfigured
              ? "위험 기준은 준비되었지만 추천 엔진은 아직 활성화되지 않았습니다. "
              : "현재 단계에서는 자료 수집·검증 상태만 확인합니다. "}
            매수·매도·유지, 목표가, 손절가, 상승 확률을 생성하지 않으며 주문을
            만들거나 실행하지 않습니다.
          </p>
        </>
      )}
    </Card>
  );
}
