"use client";

import { useEffect, useMemo, useState } from "react";

import { Dialog } from "@/components/common/dialog";
import { importEconomicEvent } from "@/lib/api/analysis";
import { ApiClientError } from "@/lib/api/client";
import { listPortfolio } from "@/lib/api/portfolio";
import type {
  EconomicEventImportPreview,
  PortfolioItem,
} from "@/types/api";

const EVENT_TYPES = [
  { value: "COMPANY_EARNINGS", label: "기업 실적 발표" },
  { value: "MACRO_INDICATOR", label: "경제지표 발표" },
  { value: "SHAREHOLDER_MEETING", label: "주주총회·기업 행사" },
  { value: "DIVIDEND", label: "배당 일정" },
  { value: "OTHER", label: "기타 공식 일정" },
] as const;

const fieldClass =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-cyan";
const areaClass =
  "min-h-28 w-full resize-y rounded-xl border border-border bg-card px-3 py-3 text-sm outline-none focus:border-cyan";

function splitLines(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function itemLabel(item: PortfolioItem): string {
  return `${item.name} (${item.symbol} · ${item.market})`;
}

export function EconomicEventImportDialog({
  onClose,
  onCompleted,
}: {
  onClose: () => void;
  onCompleted: () => void;
}) {
  const [portfolioItems, setPortfolioItems] = useState<PortfolioItem[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [eventType, setEventType] = useState("COMPANY_EARNINGS");
  const [title, setTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [officialSourceName, setOfficialSourceName] = useState("");
  const [officialSourceUrl, setOfficialSourceUrl] = useState("");
  const [portfolioItemId, setPortfolioItemId] = useState("");
  const [impactPath, setImpactPath] = useState("");
  const [preReleaseChecks, setPreReleaseChecks] = useState("");
  const [officialSourceConfirmed, setOfficialSourceConfirmed] = useState(false);
  const [preview, setPreview] = useState<EconomicEventImportPreview | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    listPortfolio(
      { includeArchived: false, limit: 100, offset: 0 },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) return;
        setPortfolioItems(response.items);
        setPortfolioItemId((current) => current || response.items[0]?.id || "");
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "등록 종목을 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setOptionsLoading(false);
      });
    return () => controller.abort();
  }, []);

  const canPreview = useMemo(
    () =>
      Boolean(
        eventType &&
          title.trim() &&
          scheduledAt &&
          officialSourceName.trim() &&
          officialSourceUrl.trim() &&
          portfolioItemId &&
          splitLines(impactPath).length &&
          officialSourceConfirmed,
      ),
    [
      eventType,
      title,
      scheduledAt,
      officialSourceName,
      officialSourceUrl,
      portfolioItemId,
      impactPath,
      officialSourceConfirmed,
    ],
  );

  function invalidatePreview() {
    setPreview(null);
    setError("");
  }

  async function submit(confirm: boolean) {
    if (!canPreview) {
      setError("필수 입력값과 공식 원문 확인 항목을 확인해 주세요.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const result = await importEconomicEvent({
        eventType,
        title: title.trim(),
        scheduledAt: new Date(scheduledAt).toISOString(),
        officialSourceName: officialSourceName.trim(),
        officialSourceUrl: officialSourceUrl.trim(),
        portfolioItemIds: [portfolioItemId],
        expectedImpactPath: splitLines(impactPath),
        preReleaseChecks: splitLines(preReleaseChecks),
        officialSourceConfirmed,
        confirm,
      });

      if (result.confirmed) {
        onCompleted();
        onClose();
        return;
      }
      setPreview(result);
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "경제·기업 일정 요청을 처리하지 못했습니다.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      title="공식 일정 등록"
      description="공식 원문 주소, 발표 예정 시각, 연결 종목과 예상 영향 경로만 저장합니다. 외부 사이트에 접속하지 않으며 시장 예상치나 가격 정보는 만들지 않습니다."
      onRequestClose={onClose}
    >
      <form
        className="flex min-h-0 flex-1 flex-col"
        onSubmit={(event) => {
          event.preventDefault();
          void submit(false);
        }}
      >
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5 sm:px-6">
          <section className="space-y-4">
            <h3 className="font-bold">공식 일정 정보</h3>

            <label className="block space-y-2">
              <span className="text-sm font-semibold">일정 종류</span>
              <select
                value={eventType}
                onChange={(event) => {
                  setEventType(event.target.value);
                  invalidatePreview();
                }}
                className={fieldClass}
                data-autofocus="true"
              >
                {EVENT_TYPES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-semibold">일정 제목</span>
              <input
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value);
                  invalidatePreview();
                }}
                className={fieldClass}
                maxLength={500}
                placeholder="예: Microsoft FY2027 Q1 실적 발표"
              />
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-2">
                <span className="text-sm font-semibold">발표 예정 시각</span>
                <input
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(event) => {
                    setScheduledAt(event.target.value);
                    invalidatePreview();
                  }}
                  className={fieldClass}
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-semibold">공식 출처명</span>
                <input
                  value={officialSourceName}
                  onChange={(event) => {
                    setOfficialSourceName(event.target.value);
                    invalidatePreview();
                  }}
                  className={fieldClass}
                  maxLength={300}
                  placeholder="예: Microsoft Investor Relations"
                />
              </label>
            </div>

            <label className="block space-y-2">
              <span className="text-sm font-semibold">공식 일정 원문 주소</span>
              <input
                type="url"
                value={officialSourceUrl}
                onChange={(event) => {
                  setOfficialSourceUrl(event.target.value);
                  invalidatePreview();
                }}
                className={fieldClass}
                maxLength={1000}
                placeholder="https://..."
              />
            </label>
          </section>

          <section className="space-y-4">
            <h3 className="font-bold">연결·확인 설정</h3>

            <label className="block space-y-2">
              <span className="text-sm font-semibold">연결 종목</span>
              <select
                value={portfolioItemId}
                onChange={(event) => {
                  setPortfolioItemId(event.target.value);
                  invalidatePreview();
                }}
                className={fieldClass}
                disabled={optionsLoading || portfolioItems.length === 0}
              >
                {portfolioItems.length === 0 ? (
                  <option value="">등록 종목 없음</option>
                ) : null}
                {portfolioItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {itemLabel(item)}
                  </option>
                ))}
              </select>
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-semibold">
                예상 영향 경로
              </span>
              <textarea
                value={impactPath}
                onChange={(event) => {
                  setImpactPath(event.target.value);
                  invalidatePreview();
                }}
                className={areaClass}
                maxLength={3000}
                placeholder={"한 줄에 한 단계씩 입력\n예: 실적 발표\n클라우드·AI 성장 확인\n종목 관리 방향 재검토"}
              />
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-semibold">
                발표 전 확인 항목
              </span>
              <textarea
                value={preReleaseChecks}
                onChange={(event) => {
                  setPreReleaseChecks(event.target.value);
                  invalidatePreview();
                }}
                className={areaClass}
                maxLength={3000}
                placeholder={"선택 입력\n예: 공식 IR 일정 재확인\n발표 자료 공개 여부 확인"}
              />
            </label>

            <label className="flex items-start gap-3 rounded-xl border border-border bg-card p-4">
              <input
                type="checkbox"
                checked={officialSourceConfirmed}
                onChange={(event) => {
                  setOfficialSourceConfirmed(event.target.checked);
                  invalidatePreview();
                }}
                className="mt-1"
              />
              <span>
                <span className="block text-sm font-semibold">
                  공식 원문과 발표 예정 시각을 직접 확인했습니다.
                </span>
                <span className="mt-1 block text-xs leading-5 text-muted">
                  등록 전 확인은 입력값·중복·종목 연결만 점검하며 외부 사이트를
                  자동으로 열지 않습니다.
                </span>
              </span>
            </label>
          </section>

          {preview ? (
            <section
              className={`rounded-2xl border p-4 ${
                preview.canConfirm
                  ? "border-emerald-500/40 bg-emerald-500/5"
                  : "border-amber-500/40 bg-amber-500/5"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-bold">등록 전 확인 결과</h3>
                <span
                  className={
                    preview.canConfirm
                      ? "text-sm font-bold text-emerald-400"
                      : "text-sm font-bold text-amber-400"
                  }
                >
                  {preview.canConfirm ? "등록 가능" : "추가 확인 필요"}
                </span>
              </div>

              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-muted">공식 출처 도메인</dt>
                  <dd className="mt-1 break-all font-semibold">
                    {preview.sourceDomain}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">중복 일정</dt>
                  <dd className="mt-1 font-semibold">
                    {preview.duplicate.duplicate ? "있음" : "없음"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">연결 종목</dt>
                  <dd className="mt-1 font-semibold">
                    {preview.portfolioItems
                      .map((item) => `${item.name} (${item.symbol})`)
                      .join(", ")}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">발표 예정 시각</dt>
                  <dd className="mt-1 font-semibold">
                    {new Date(preview.scheduledAt).toLocaleString("ko-KR")}
                  </dd>
                </div>
              </dl>

              <div className="mt-3">
                <p className="text-xs text-muted">정규화된 원문 주소</p>
                <p className="mt-1 break-all text-sm font-semibold">
                  {preview.normalizedUrl}
                </p>
              </div>

              {preview.validationWarnings.length ? (
                <ul className="mt-4 space-y-1 text-sm text-secondary">
                  {preview.validationWarnings.map((warning) => (
                    <li key={warning}>· {warning}</li>
                  ))}
                </ul>
              ) : null}

              <p className="mt-4 text-xs leading-5 text-muted">
                현재는 등록 전 확인만 수행했습니다. DB에는 저장하지 않았고 외부
                사이트에도 접속하지 않았습니다.
              </p>
            </section>
          ) : null}

          {error ? (
            <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
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
            type="submit"
            disabled={!canPreview || submitting}
            className="min-h-11 rounded-xl bg-cyan px-5 text-sm font-bold text-background disabled:opacity-40"
          >
            {submitting ? "확인 중…" : "등록 전 확인"}
          </button>
          <button
            type="button"
            disabled={!preview?.canConfirm || submitting}
            onClick={() => void submit(true)}
            className="min-h-11 rounded-xl border border-emerald-500 px-5 text-sm font-bold text-emerald-400 disabled:opacity-40"
          >
            최종 등록
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
