"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BriefingGenerationDialog } from "@/components/briefings/briefing-generation-dialog";
import { Card, EmptyState } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { getBriefings } from "@/lib/api/operations";
import { briefingStatusLabels } from "@/lib/operations";
import type { BriefingListResponse } from "@/types/api";

const briefingVerificationLabels: Record<string, string> = {
  OFFICIAL_CONFIRMED: "공식 확인",
  MULTI_SOURCE_CONFIRMED: "복수 출처 확인",
  NEEDS_VERIFICATION: "추가 검증 필요",
  CONFLICTING: "내용 충돌",
  CORRECTED: "정정",
  OFFICIALLY_DENIED: "공식 부인",
  STALE_REUSED: "재사용 자료",
};

const briefingDirectionLabels: Record<string, string> = {
  ADD_REVIEW: "추가매수 검토",
  HOLD: "유지",
  WAIT: "대기",
  REDUCE_REVIEW: "비중 축소 검토",
  EXIT_REVIEW: "정리 검토",
  INSUFFICIENT_DATA: "데이터 부족",
};

const briefingThesisEffectLabels: Record<string, string> = {
  STRENGTHENS: "강화",
  SLIGHTLY_STRENGTHENS: "소폭 강화",
  NEUTRAL: "중립",
  SLIGHTLY_WEAKENS: "소폭 약화",
  WEAKENS: "약화",
  NONE: "영향 없음",
  UNKNOWN: "영향 확인 필요",
};

const briefingTypeLabels: Record<string, string> = {
  CHANGE_BRIEFING: "변경 기반 브리핑",
  CORRECTION_NOTICE: "정정·공식 부인 브리핑",
  KRX_PRE_OPEN: "국내장 개장 전 브리핑",
  KRX_POST_CLOSE: "국내장 마감 후 브리핑",
  NASDAQ_PRE_OPEN: "미국장 개장 전 브리핑",
  NASDAQ_POST_CLOSE: "미국장 마감 후 브리핑",
  DAILY_DIGEST: "일일 브리핑",
  PROVIDER_HEALTH_NOTICE: "수집 상태 안내",
  MANUAL_PREVIEW: "수동 미리보기",
};

function briefingVerificationText(value: string): string {
  return briefingVerificationLabels[value] ?? "검증 상태 확인 필요";
}

function briefingDirectionText(value: string): string {
  return briefingDirectionLabels[value] ?? "검토 필요";
}

function briefingThesisEffectText(value: string): string {
  return briefingThesisEffectLabels[value] ?? "영향 확인 필요";
}

function briefingTypeText(value: string): string {
  return briefingTypeLabels[value] ?? "변경 기반 브리핑";
}

function time(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function BriefingsClient() {
  const [data, setData] = useState<BriefingListResponse | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [generationOpen, setGenerationOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getBriefings(controller.signal)
      .then((response) => {
        setData(response);
        setError("");
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") {
          return;
        }
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "브리핑을 불러오지 못했습니다.",
        );
      });
    return () => controller.abort();
  }, [refresh]);

  function handleCreated() {
    setGenerationOpen(false);
    setRefresh((value) => value + 1);
  }

  if (error) {
    return (
      <Card>
        <p className="text-red">{error}</p>
        <button
          type="button"
          className="mt-4 rounded-lg border border-border px-4 py-2 font-bold"
          onClick={() => {
            setError("");
            setRefresh((value) => value + 1);
          }}
        >
          다시 시도
        </button>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card>
        <p className="py-12 text-center">브리핑 확인 중…</p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setGenerationOpen(true)}
          className="min-h-11 rounded-xl bg-yellow px-5 text-sm font-bold text-background"
        >
          브리핑 만들기
        </button>
      </div>

      {!data.emailConfigured ? (
        <p className="rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm font-semibold text-yellow">
          이메일 알림이 아직 설정되지 않았습니다. 웹에서 만든 브리핑 이력은 계속
          확인할 수 있습니다.
        </p>
      ) : null}

      {data.items.length === 0 ? (
        <EmptyState
          title="브리핑 이력 없음"
          detail="기간과 포함 항목을 확인한 뒤 변경 기반 브리핑을 만들 수 있습니다."
        />
      ) : (
        data.items.map((briefing) => (
          <Card key={briefing.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold text-cyan">
                  {briefingTypeText(briefing.briefingType)} ·{" "}
                  {briefingStatusLabels[briefing.status]}
                </p>
                <h2 className="mt-1 text-lg font-bold">{briefing.title}</h2>
                <p className="mt-2 text-sm leading-6 text-secondary">
                  {briefing.compactSummary}
                </p>
              </div>
              <time className="text-xs text-muted">
                {time(briefing.generatedAt)}
              </time>
            </div>

            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3 lg:grid-cols-6">
              {[
                ["항목", briefing.itemCount],
                ["중요 변경", briefing.materialChangeCount],
                ["공식 확인", briefing.officialConfirmedCount],
                ["검증 필요", briefing.needsVerificationCount],
                ["정정", briefing.correctionCount],
                ["부인", briefing.denialCount],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-surface p-3">
                  <dt className="text-xs text-muted">{label}</dt>
                  <dd className="mt-1 font-bold">{value}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-4 space-y-3">
              {briefing.items.map((item) => (
                <article
                  key={item.id}
                  className="rounded-xl border border-border bg-surface p-4"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <h3 className="font-bold">{item.headline}</h3>
                    <span className="text-xs font-bold text-cyan">
                      {briefingVerificationText(item.verificationStatus)} · 증거 강도{" "}
                      {item.trustScore}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-secondary">
                    {item.shortSummary}
                  </p>
                  <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                    <p className="rounded-lg border border-border p-2">
                      관리 방향:{" "}
                      <strong>
                        {briefingDirectionText(item.managementDirection)}
                      </strong>
                    </p>
                    <p className="rounded-lg border border-border p-2">
                      투자근거 영향:{" "}
                      <strong>
                        {briefingThesisEffectText(item.thesisEffect)}
                      </strong>
                    </p>
                  </div>
                  {item.nextInformation.length ||
                  item.invalidationConditions.length ? (
                    <div className="mt-3 grid gap-3 text-xs leading-5 text-secondary sm:grid-cols-2">
                      <div>
                        <p className="font-bold text-foreground">
                          다음 확인 정보
                        </p>
                        <p>
                          {item.nextInformation.join(" · ") || "추가 확인 필요"}
                        </p>
                      </div>
                      <div>
                        <p className="font-bold text-foreground">
                          판단 무효화 조건
                        </p>
                        <p>
                          {item.invalidationConditions.join(" · ") ||
                            "사용자 투자근거에서 확인"}
                        </p>
                      </div>
                    </div>
                  ) : null}
                  <p className="mt-2 text-xs text-muted">
                    {item.trustScoreExplanation}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-3 text-sm font-bold text-cyan">
                    <Link href={`/events/${item.informationEventId}`}>
                      사건 상세
                    </Link>
                    {[...item.sourceLinks, ...item.officialReferenceLinks].map(
                      (link) => (
                        <a
                          key={`${item.id}-${link.url}`}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title="외부 사이트로 이동"
                        >
                          {link.title}
                        </a>
                      ),
                    )}
                  </div>
                </article>
              ))}
            </div>
          </Card>
        ))
      )}

      {generationOpen ? (
        <BriefingGenerationDialog
          onClose={() => setGenerationOpen(false)}
          onCreated={handleCreated}
        />
      ) : null}
    </div>
  );
}
