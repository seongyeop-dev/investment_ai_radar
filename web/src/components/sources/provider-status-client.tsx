"use client";

import { useEffect, useState } from "react";
import { Card, EmptyState } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { getProviderStatus } from "@/lib/api/providers";
import type { ProviderStatusList } from "@/types/api";

const providerLabels: Record<string, string> = {
  OPENDART: "OpenDART 공식 공시",
  SEC_EDGAR: "SEC EDGAR 공식 공시",
  KRX_CALENDAR: "KRX 시장 캘린더",
  NASDAQ_CALENDAR: "NASDAQ 시장 캘린더",
};
const hiddenQuoteProviders = new Set(["UPBIT", "BINANCE"]);

const statusLabels: Record<string, string> = {
  READY: "준비됨",
  CONFIGURED: "설정됨 · Smoke 필요",
  SUCCEEDED: "최근 수집 성공",
  PARTIAL: "일부 수집 성공",
  NOT_CONFIGURED: "미설정",
  NOT_APPLICABLE: "대상 종목 없음",
  NETWORK_UNAVAILABLE: "네트워크 연결 불가",
  RATE_LIMITED: "호출 제한",
  FAILED: "응답 검증 실패",
  ERROR: "오류",
};

function formatTime(value: string | null): string {
  if (!value) return "성공 기록 없음";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ProviderStatusClient() {
  const [data, setData] = useState<ProviderStatusList | null>(null);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getProviderStatus(controller.signal)
      .then(setData)
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") {
          return;
        }
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "데이터 제공자 상태를 불러오지 못했습니다.",
        );
      });
    return () => controller.abort();
  }, [refreshKey]);

  if (error) {
    return (
      <Card>
        <EmptyState detail={error} />
        <button
          type="button"
          onClick={() => {
            setError("");
            setData(null);
            setRefreshKey((value) => value + 1);
          }}
          className="mt-4 min-h-11 rounded-xl border border-border px-4 text-sm font-bold"
        >
          다시 확인
        </button>
      </Card>
    );
  }
  if (!data) {
    return (
      <Card>
        <p className="py-10 text-center text-secondary">데이터 제공자 상태 확인 중…</p>
      </Card>
    );
  }

  const visibleProviders = data.items.filter(
    (item) => !hiddenQuoteProviders.has(item.provider),
  );

  return (
    <div className="space-y-4">
      <Card>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <p><span className="text-xs text-muted">검증된 연결</span><strong className="mt-1 block text-xl">{data.verifiedMappingCount}</strong></p>
          <p><span className="text-xs text-muted">확인 필요 연결</span><strong className="mt-1 block text-xl">{data.unresolvedMappingCount}</strong></p>
          <p><span className="text-xs text-muted">충돌 연결</span><strong className="mt-1 block text-xl">{data.conflictingMappingCount}</strong></p>
          <p><span className="text-xs text-muted">오래된 연결</span><strong className="mt-1 block text-xl">{data.staleMappingCount}</strong></p>
          <p><span className="text-xs text-muted">최근 30일 공식 공시</span><strong className="mt-1 block text-xl">{data.recentDisclosureCount}</strong></p>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        {visibleProviders.map((item) => (
          <Card key={`${item.provider}-${item.capability}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-bold">
                  {providerLabels[item.provider] ?? "알 수 없는 제공자"}
                </h2>
                <p className="mt-1 text-xs text-muted">{item.capability}</p>
              </div>
              <span className="rounded-full border border-border px-2.5 py-1 text-xs font-bold">
                {statusLabels[item.status] ?? "상태 확인 필요"}
              </span>
            </div>
            <dl className="mt-4 grid gap-2 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-muted">최근 성공</dt><dd className="text-right">{formatTime(item.lastSuccessAt)}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">연속 실패</dt><dd>{item.consecutiveFailures}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">실제 요청 수</dt><dd>{item.requestCount}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">최근 오류</dt><dd className="break-all text-right">{item.lastErrorCode ?? "없음"}</dd></div>
            </dl>
          </Card>
        ))}
      </div>
    </div>
  );
}
