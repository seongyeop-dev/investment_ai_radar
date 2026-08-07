"use client";

import { useState } from "react";

import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import { generateBriefing } from "@/lib/api/operations";
import type {
  Briefing,
  BriefingGenerationInput,
  BriefingGenerationPreview,
} from "@/types/api";

function localDateTime(value: Date): string {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function initialPeriod(): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1_000);
  return {
    start: localDateTime(start),
    end: localDateTime(end),
  };
}

function verificationLabel(value: string): string {
  const labels: Record<string, string> = {
    OFFICIAL_CONFIRMED: "공식 확인",
    MULTI_SOURCE_CONFIRMED: "복수 출처 확인",
    NEEDS_VERIFICATION: "추가 검증 필요",
    CONFLICTING: "내용 충돌",
    OFFICIALLY_DENIED: "공식 부인",
    CORRECTED: "정정",
    STALE_REUSED: "재사용 자료",
  };
  return labels[value] ?? "검증 상태 확인 필요";
}

export function BriefingGenerationDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (briefing: Briefing) => void;
}) {
  const period = initialPeriod();
  const [periodStart, setPeriodStart] = useState(period.start);
  const [periodEnd, setPeriodEnd] = useState(period.end);
  const [minimumPriority, setMinimumPriority] = useState("0");
  const [includedItemsConfirmed, setIncludedItemsConfirmed] = useState(false);
  const [preview, setPreview] = useState<BriefingGenerationPreview | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function clearPreview() {
    setPreview(null);
    setError("");
  }

  function payload(confirm: boolean): BriefingGenerationInput {
    return {
      periodStart: new Date(periodStart).toISOString(),
      periodEnd: new Date(periodEnd).toISOString(),
      minimumPriority: Number(minimumPriority),
      includedItemsConfirmed,
      confirm,
    };
  }

  async function submit(confirm: boolean) {
    if (!periodStart || !periodEnd) {
      setError("브리핑 시작 시각과 종료 시각을 입력해 주세요.");
      return;
    }
    if (new Date(periodStart).getTime() >= new Date(periodEnd).getTime()) {
      setError("브리핑 시작 시각은 종료 시각보다 이전이어야 합니다.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const result = await generateBriefing(payload(confirm));
      if (result.confirmed) {
        onCreated(result.briefing);
        onClose();
        return;
      }
      setPreview(result);
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "브리핑 요청을 처리하지 못했습니다.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      title="변경 기반 브리핑 만들기"
      description="선택한 기간의 새로운 중요 변경과 정정·공식 부인을 묶습니다. 생성 전 확인은 DB에 저장하지 않으며 이메일을 보내지 않습니다."
      onRequestClose={onClose}
    >
      <div className="overflow-y-auto px-5 py-5 sm:px-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold">
            브리핑 시작 시각
            <input
              data-autofocus="true"
              type="datetime-local"
              value={periodStart}
              onChange={(event) => {
                setPeriodStart(event.target.value);
                clearPreview();
              }}
              className="mt-2 min-h-11 w-full rounded-xl border border-border bg-card px-3"
            />
          </label>
          <label className="text-sm font-semibold">
            브리핑 종료 시각
            <input
              type="datetime-local"
              value={periodEnd}
              onChange={(event) => {
                setPeriodEnd(event.target.value);
                clearPreview();
              }}
              className="mt-2 min-h-11 w-full rounded-xl border border-border bg-card px-3"
            />
          </label>
        </div>

        <label className="mt-4 block text-sm font-semibold">
          최소 중요도
          <select
            value={minimumPriority}
            onChange={(event) => {
              setMinimumPriority(event.target.value);
              clearPreview();
            }}
            className="mt-2 min-h-11 w-full rounded-xl border border-border bg-card px-3"
          >
            <option value="0">새 중요 변경 전체</option>
            <option value="70">중요 변경 이상</option>
            <option value="80">공식 확인 이상</option>
          </select>
        </label>

        <label className="mt-5 flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-sm">
          <input
            type="checkbox"
            checked={includedItemsConfirmed}
            onChange={(event) => {
              setIncludedItemsConfirmed(event.target.checked);
              clearPreview();
            }}
            className="mt-1"
          />
          <span>
            <strong className="block">포함 항목과 기간을 직접 확인했습니다.</strong>
            <span className="mt-1 block text-xs leading-5 text-muted">
              외부 사이트에 접속하거나 이메일을 발송하지 않습니다. 최종 생성 전에는
              브리핑 기록과 항목을 저장하지 않습니다.
            </span>
          </span>
        </label>

        {preview ? (
          <section className="mt-5 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-bold">생성 전 확인 결과</h3>
              <strong className={preview.canConfirm ? "text-emerald-400" : "text-yellow"}>
                {preview.canConfirm ? "생성 가능" : "새 항목 없음"}
              </strong>
            </div>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted">포함 항목</dt>
                <dd className="mt-1 font-bold">{preview.briefing.itemCount}건</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">중복 제외</dt>
                <dd className="mt-1 font-bold">{preview.excludedDuplicates}건</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">중요 변경</dt>
                <dd className="mt-1 font-bold">
                  {preview.briefing.materialChangeCount}건
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">공식 확인</dt>
                <dd className="mt-1 font-bold">
                  {preview.briefing.officialConfirmedCount}건
                </dd>
              </div>
            </dl>
            <div className="mt-4 space-y-2">
              {preview.briefing.items.map((item) => (
                <article
                  key={item.id}
                  className="rounded-xl border border-border bg-card p-3"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <strong className="text-sm">{item.headline}</strong>
                    <span className="text-xs font-bold text-cyan">
                      {verificationLabel(item.verificationStatus)}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-secondary">
                    {item.shortSummary}
                  </p>
                </article>
              ))}
              {preview.briefing.items.length === 0 ? (
                <p className="text-sm text-secondary">
                  선택한 기간에 새로 생성할 중요 변경이 없습니다.
                </p>
              ) : null}
            </div>
            <p className="mt-4 text-xs leading-5 text-muted">
              현재는 생성 전 확인만 수행했습니다. DB 저장과 이메일 발송은 모두
              실행되지 않았습니다.
            </p>
          </section>
        ) : null}

        {error ? (
          <p className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </p>
        ) : null}
      </div>

      <footer className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-4 sm:px-6">
        <button
          type="button"
          onClick={onClose}
          className="min-h-11 rounded-xl border border-border px-4 text-sm font-semibold"
        >
          닫기
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => void submit(false)}
          className="min-h-11 rounded-xl bg-cyan px-5 text-sm font-bold text-background disabled:opacity-40"
        >
          {submitting ? "확인 중…" : "생성 전 확인"}
        </button>
        <button
          type="button"
          disabled={!preview?.canConfirm || submitting}
          onClick={() => void submit(true)}
          className="min-h-11 rounded-xl border border-emerald-500 px-5 text-sm font-bold text-emerald-400 disabled:opacity-40"
        >
          최종 생성
        </button>
      </footer>
    </Dialog>
  );
}
