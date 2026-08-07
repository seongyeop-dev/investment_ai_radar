"use client";

import { useEffect, useState } from "react";

import { Card, EmptyState, PageHeader } from "@/components/common/ui";
import { EconomicEventImportDialog } from "@/components/macro/economic-event-import-dialog";
import { getEconomicEvents } from "@/lib/api/analysis";
import { ApiClientError } from "@/lib/api/client";
import type { EconomicEvent } from "@/types/api";

const K = {
  title: "경제·기업 일정",
  description:
    "공식 발표 예정 시각과 등록 종목의 영향 경로를 확인합니다. 시장 가격·차트는 수집하거나 표시하지 않습니다.",
  loading: "일정 확인 중…",
  loadError: "경제·기업 일정을 불러오지 못했습니다.",
  emptyTitle: "등록된 공식 일정이 없습니다.",
  emptyDetail:
    "공식 원문과 발표 예정 시각을 직접 확인한 일정만 웹에서 등록합니다.",
  impactRequired: "영향 경로 확인 필요",
} as const;

const eventTypeLabels: Record<string, string> = {
  COMPANY_EARNINGS: "기업 실적 발표",
  MACRO_INDICATOR: "경제지표 발표",
  SHAREHOLDER_MEETING: "주주총회·기업 행사",
  DIVIDEND: "배당 일정",
  OTHER: "기타 공식 일정",
};

export default function MacroPage() {
  const [items, setItems] = useState<EconomicEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    getEconomicEvents(false, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setItems(response);
        setError("");
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") {
          return;
        }
        if (controller.signal.aborted) return;
        setError(
          reason instanceof ApiClientError ? reason.message : K.loadError,
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [refresh]);

  return (
    <div>
      <PageHeader
        eyebrow="경제·기업 일정"
        title={K.title}
        description={K.description}
      />

      <div className="mb-4 flex justify-end">
        <button
          type="button"
          onClick={() => setImportOpen(true)}
          className="min-h-11 rounded-xl bg-cyan px-5 font-bold text-background"
        >
          공식 일정 등록
        </button>
      </div>

      <Card>
        {loading ? (
          <p className="py-20 text-center text-secondary">{K.loading}</p>
        ) : error ? (
          <EmptyState title={K.loadError} detail={error} />
        ) : items.length === 0 ? (
          <EmptyState title={K.emptyTitle} detail={K.emptyDetail} />
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <article
                key={item.id}
                className="rounded-xl border border-border bg-surface p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-semibold text-cyan">
                      {eventTypeLabels[item.eventType] ?? "공식 일정"}
                    </p>
                    <h2 className="mt-1 font-bold">{item.title}</h2>
                  </div>
                  <time className="text-xs text-muted">
                    {new Date(item.scheduledAt).toLocaleString("ko-KR")}
                  </time>
                </div>

                <p className="mt-3 text-sm leading-6 text-secondary">
                  {item.expectedImpactPath.join(" → ") || K.impactRequired}
                </p>

                {item.preReleaseChecks.length ? (
                  <div className="mt-3 rounded-xl border border-border p-3">
                    <p className="text-xs font-semibold text-muted">
                      발표 전 확인
                    </p>
                    <ul className="mt-2 space-y-1 text-sm text-secondary">
                      {item.preReleaseChecks.map((check) => (
                        <li key={check}>· {check}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <a
                  href={item.officialSourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-block text-sm text-cyan underline"
                >
                  {item.officialSourceName}
                </a>
              </article>
            ))}
          </div>
        )}
      </Card>

      {importOpen ? (
        <EconomicEventImportDialog
          onClose={() => setImportOpen(false)}
          onCompleted={() => {
            setLoading(true);
            setError("");
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </div>
  );
}
