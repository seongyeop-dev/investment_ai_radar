"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { getSystemInfo } from "@/lib/api/system";
import {
  availabilityLabels,
  operatingModeLabels,
} from "@/lib/operations";
import type { SystemInfo as SystemInfoContract } from "@/types/api";

function readiness(value: boolean): string {
  return value ? "설정됨" : "미설정";
}

function statusLabel(value: string): string {
  const labels: Record<string, string> = {
    NOT_CONFIGURED: "미설정",
    READY: "준비 완료",
    RUNNING: "실행 중",
    RATE_LIMITED: "사용량 제한",
    ERROR: "오류",
    PAUSED: "중지",
  };
  return labels[value] ?? value;
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("ko-KR", {
        dateStyle: "medium",
        timeStyle: "long",
      }).format(date);
}

type Row = [label: string, value: string, code?: string];

function StatusGroup({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <Card title={title}>
      <dl className="divide-y divide-border rounded-xl border border-border bg-surface">
        {rows.map(([label, value, code]) => (
          <div
            key={label}
            className="grid min-w-0 gap-1 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] sm:gap-4"
          >
            <dt className="text-sm font-semibold text-secondary">{label}</dt>
            <dd className="break-words text-sm font-bold sm:text-right">
              {value}
              {code ? (
                <span className="ml-2 text-[10px] font-normal text-muted">
                  {code}
                </span>
              ) : null}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export function SystemInfo() {
  const [info, setInfo] = useState<SystemInfoContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getSystemInfo(controller.signal)
      .then(setInfo)
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") {
          return;
        }
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "시스템 정보를 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refreshKey]);

  if (loading) {
    return (
      <Card>
        <p className="py-12 text-center text-sm font-semibold text-secondary">
          시스템 정보를 불러오는 중…
        </p>
      </Card>
    );
  }
  if (error || !info) {
    return (
      <Card>
        <div className="rounded-xl border border-red/40 bg-red/10 p-5" role="alert">
          <p className="font-semibold text-red">
            {error || "시스템 정보가 없습니다."}
          </p>
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
      </Card>
    );
  }

  const groups: { title: string; rows: Row[] }[] = [
    {
      title: "기본 서버",
      rows: [
        ["실행 환경", info.environment === "development" ? "개발 환경" : info.environment === "production" ? "운영 환경" : info.environment, "환경"],
        ["데이터베이스 설정", readiness(info.databaseConfigured)],
        [
          "데이터베이스 연결",
          info.databaseReachable ? "연결됨" : "연결 안 됨",
        ],
        [
          "데이터베이스 종류",
          statusLabel(info.databaseType),
          info.databaseType,
        ],
        ["버전", info.version],
        ["서버 시각", formatTime(info.time)],
      ],
    },
    {
      title: "데이터 제공자",
      rows: [
        [
          "뉴스·IR",
          statusLabel(info.newsProviderStatus),
          info.newsProviderStatus,
        ],
        [
          "공식 공시",
          info.openDartConfigured || info.secConfigured
            ? `OpenDART ${statusLabel(info.openDartStatus)} · SEC ${statusLabel(info.secStatus)}`
            : "미설정",
        ],
        ["경제·기업 일정", info.eventCount > 0 ? "수집 데이터 있음" : "미설정"],
        ["가격 데이터", "사용 안 함"],
        [
          "시장 일정",
          info.marketCalendarConfigured ? "설정됨" : "미설정",
        ],
        ["KRX 일정", statusLabel(info.krxCalendarStatus)],
        ["NASDAQ 일정", statusLabel(info.nasdaqCalendarStatus)],
        ["활성 뉴스 출처", `${info.enabledNewsSourceCount}개`],
      ],
    },
    {
      title: "브리핑·자동화",
      rows: [
        [
          "이메일",
          statusLabel(info.emailProviderStatus),
          info.emailProviderStatus,
        ],
        ["스케줄러", readiness(info.schedulerConfigured)],
        [
          "마지막 이메일",
          info.lastEmailSentAt ? formatTime(info.lastEmailSentAt) : "없음",
        ],
        [
          "마지막 자동 수집",
          info.lastRadarCycleAt ? formatTime(info.lastRadarCycleAt) : "없음",
        ],
        [
          "다음 시장 브리핑",
          info.nextMarketBriefing
            ? formatTime(info.nextMarketBriefing)
            : "계산된 일정 없음",
        ],
        ["활성 시장 브리핑", `${info.enabledMarketBriefingCount}개`],
        [
          "마지막 KRX 브리핑",
          info.lastKrxBriefing ? formatTime(info.lastKrxBriefing) : "없음",
        ],
        [
          "마지막 NASDAQ 브리핑",
          info.lastNasdaqBriefing
            ? formatTime(info.lastNasdaqBriefing)
            : "없음",
        ],
        [
          "위험 설정",
          info.riskProfileConfigured ? "설정됨" : "미설정",
        ],
        [
          "위험 자동 제안",
          info.riskRecommendationAvailable
            ? `사용 가능 · 신뢰도 ${
                info.riskRecommendationConfidence ?? "미확인"
              }`
            : "사용 불가",
        ],
        [
          "위험 설정 재검토",
          info.riskRecommendationStale ||
          info.portfolioFingerprintChanged
            ? "등록 종목 변경 · 확인 필요"
            : "최신 상태",
        ],
        ["AI 자동 분석", info.aiAutomationEnabled ? "활성" : "비활성"],
        [
          "자동 주문 기능",
          info.automaticTradingEnabled ? "활성" : "비활성 · 지원하지 않음",
        ],
      ],
    },
    {
      title: "저장·운영",
      rows: [
        [
          "데이터베이스 용량",
          `${availabilityLabels[info.databaseBytesAvailability]} · ${
            info.databaseBytes === null
              ? "--"
              : `${Math.ceil(info.databaseBytes / 1024)} KiB`
          }`,
        ],
        ["운영 모드", operatingModeLabels[info.operatingMode]],
        ["무료 예산", readiness(info.budgetConfigured)],
        ["자료 보관·정리", readiness(info.retentionCleanupEnabled), "보관 정책"],
        [
          "마지막 정리",
          info.lastCleanupAt ? formatTime(info.lastCleanupAt) : "없음",
        ],
        [
          "GitHub Actions 사용량",
          info.githubActionsUsageConnected ? "연결됨" : "미설정",
        ],
      ],
    },
  ];

  groups.push({
    title: "종목 연결 상태",
    rows: [
      ["검증된 연결", `${info.verifiedMappingCount}개`],
      ["확인 필요 연결", `${info.unresolvedMappingCount}개`],
      ["오래된 연결", `${info.staleMappingCount}개`],
      [
        "최근 데이터 제공자 성공",
        info.lastProviderSyncAt ? formatTime(info.lastProviderSyncAt) : "없음",
      ],
    ],
  });
  groups.push({
    title: "비활성 호환 기능",
    rows: [
      ["공개 시세 데이터 제공자", "비활성"],
      ["자동 시세 수집", "사용 안 함"],
    ],
  });

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {groups.map((group) => (
        <StatusGroup key={group.title} {...group} />
      ))}
    </div>
  );
}
