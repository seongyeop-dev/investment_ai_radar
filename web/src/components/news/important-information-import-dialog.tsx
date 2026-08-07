"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import { importImportantInformation } from "@/lib/api/news";
import { listPortfolio } from "@/lib/api/portfolio";
import {
  verificationLabels,
} from "@/lib/news";
import type {
  ImportantInformationImportInput,
  ImportantInformationImportPreview,
  PortfolioItem,
} from "@/types/api";

interface ImportantInformationImportDialogProps {
  onClose: () => void;
  onCompleted: () => void;
}

interface ImportDraft {
  sourceUrl: string;
  publisherName: string;
  title: string;
  publishedAt: string;
  primaryClaim: string;
  publicSummary: string;
  portfolioItemId: string;
  language: string;
  materialChange: boolean;
}

const EMPTY_DRAFT: ImportDraft = {
  sourceUrl: "",
  publisherName: "",
  title: "",
  publishedAt: "",
  primaryClaim: "",
  publicSummary: "",
  portfolioItemId: "",
  language: "ko",
  materialChange: true,
};

const INPUT_CLASS =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 " +
  "text-sm text-foreground placeholder:text-muted focus:border-cyan " +
  "disabled:opacity-60";

const warningLabels: Record<string, string> = {
  URL_NORMALIZED: "추적값과 화면 위치값을 제거해 URL을 표준화합니다.",
  DUPLICATE_CANONICAL_URL: "동일한 공개 링크가 이미 등록되어 있습니다.",
  MANUAL_SOURCE_WILL_BE_CREATED:
    "이 발행사의 수동 등록용 출처 항목을 새로 만듭니다.",
  INSTRUMENT_WILL_BE_CREATED:
    "선택한 등록 종목을 검증 종목과 연결합니다.",
  OFFICIAL_SOURCE_MATCHED:
    "등록된 공식 출처 도메인과 일치합니다.",
  NON_OFFICIAL_SOURCE_REQUIRES_REVIEW:
    "공식 출처가 아니므로 추가 검증 필요 상태로 등록합니다.",
  SOURCE_GRADE_INFERRED_FROM_PUBLIC_METADATA:
    "기존 공개 참고자료 유형을 기준으로 출처 등급을 분류했습니다.",
};

function optionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

function validateDraft(draft: ImportDraft): string {
  if (!draft.sourceUrl.trim()) {
    return "공개 링크를 입력해 주세요.";
  }
  try {
    const url = new URL(draft.sourceUrl.trim());
    if (!["http:", "https:"].includes(url.protocol)) {
      return "공개 링크는 HTTP 또는 HTTPS 주소만 사용할 수 있습니다.";
    }
  } catch {
    return "공개 링크 형식을 확인해 주세요.";
  }
  if (!draft.publisherName.trim()) {
    return "발행사를 입력해 주세요.";
  }
  if (!draft.title.trim()) {
    return "제목을 입력해 주세요.";
  }
  if (!draft.publishedAt) {
    return "발행 일시를 입력해 주세요.";
  }
  if (!draft.primaryClaim.trim()) {
    return "핵심 주장을 입력해 주세요.";
  }
  if (!draft.portfolioItemId) {
    return "연결할 등록 종목을 선택해 주세요.";
  }
  if (draft.publicSummary.length > 1000) {
    return "공개 요약은 1,000자 이하로 입력해 주세요.";
  }
  return "";
}

function warningLabel(value: string): string {
  return warningLabels[value] ?? value;
}

export function ImportantInformationImportDialog({
  onClose,
  onCompleted,
}: ImportantInformationImportDialogProps) {
  const [draft, setDraft] = useState<ImportDraft>(EMPTY_DRAFT);
  const [portfolioItems, setPortfolioItems] = useState<PortfolioItem[]>([]);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmCompleted, setConfirmCompleted] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] =
    useState<ImportantInformationImportPreview | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listPortfolio(
      {
        limit: 100,
        offset: 0,
      },
      controller.signal,
    )
      .then((response) => {
        setPortfolioItems(response.items);
        setError("");
      })
      .catch((reason: unknown) => {
        if (
          reason instanceof ApiClientError &&
          reason.kind === "cancelled"
        ) {
          return;
        }
        setError("등록 종목을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setPortfolioLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const selectedPortfolio = useMemo(
    () =>
      portfolioItems.find(
        (item) => item.id === draft.portfolioItemId,
      ) ?? null,
    [draft.portfolioItemId, portfolioItems],
  );

  function updateDraft<K extends keyof ImportDraft>(
    key: K,
    value: ImportDraft[K],
  ) {
    setDraft((current) => ({
      ...current,
      [key]: value,
    }));
    setPreview(null);
    setConfirmCompleted(false);
    setError("");
  }

  function createPayload(
    confirm: boolean,
  ): ImportantInformationImportInput {
    return {
      sourceUrl: draft.sourceUrl.trim(),
      publisherName: draft.publisherName.trim(),
      title: draft.title.trim(),
      publishedAt: new Date(draft.publishedAt).toISOString(),
      primaryClaim: draft.primaryClaim.trim(),
      publicSummary: optionalText(draft.publicSummary),
      portfolioItemId: draft.portfolioItemId,
      language: draft.language,
      materialChange: draft.materialChange,
      confirm,
    };
  }

  async function submitPreview(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    if (previewLoading || confirmLoading) {
      return;
    }
    const validationError = validateDraft(draft);
    if (validationError) {
      setError(validationError);
      return;
    }

    setPreviewLoading(true);
    setPreview(null);
    setError("");
    try {
      const result = await importImportantInformation(
        createPayload(false),
      );
      if (result.confirmed) {
        setError("검증 요청에서 예상하지 않은 등록 응답을 받았습니다.");
        return;
      }
      setPreview(result);
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "등록 전 검증을 수행하지 못했습니다.",
      );
    } finally {
      setPreviewLoading(false);
    }
  }

  async function confirmImport() {
    if (
      !preview?.wouldCreate ||
      confirmLoading ||
      confirmCompleted
    ) {
      return;
    }

    setConfirmLoading(true);
    setError("");
    try {
      const result = await importImportantInformation(
        createPayload(true),
      );
      if (!result.confirmed) {
        setError("최종 등록 요청에서 검증 응답을 받았습니다.");
        return;
      }
      setConfirmCompleted(true);
      onCompleted();
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "중요 정보를 등록하지 못했습니다.",
      );
    } finally {
      setConfirmLoading(false);
    }
  }

  return (
    <Dialog
      title="중요 정보 등록"
      description={
        "공개 링크와 메타데이터, 핵심 주장만 저장합니다. " +
        "기사 전문은 저장하지 않으며 출처 등급과 검증 상태는 " +
        "기존 출처·공식 자료를 기준으로 자동 분류합니다."
      }
      onRequestClose={() => {
        if (!previewLoading && !confirmLoading) {
          onClose();
        }
      }}
    >
      <form
        className="flex min-h-0 flex-1 flex-col"
        onSubmit={submitPreview}
      >
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5 sm:px-6">
          <section>
            <h3 className="text-sm font-bold">공개 정보</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold sm:col-span-2">
                공개 링크
                <input
                  data-autofocus="true"
                  type="url"
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.sourceUrl}
                  onChange={(event) =>
                    updateDraft("sourceUrl", event.target.value)
                  }
                  placeholder="https://..."
                  required
                />
              </label>

              <label className="text-sm font-semibold">
                발행사
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.publisherName}
                  onChange={(event) =>
                    updateDraft(
                      "publisherName",
                      event.target.value,
                    )
                  }
                  placeholder="예: TipRanks"
                  required
                />
              </label>

              <label className="text-sm font-semibold">
                발행 일시
                <input
                  type="datetime-local"
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.publishedAt}
                  onChange={(event) =>
                    updateDraft(
                      "publishedAt",
                      event.target.value,
                    )
                  }
                  required
                />
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                제목
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.title}
                  onChange={(event) =>
                    updateDraft("title", event.target.value)
                  }
                  required
                />
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                핵심 주장
                <textarea
                  className={`${INPUT_CLASS} mt-1.5 min-h-28 py-3`}
                  value={draft.primaryClaim}
                  onChange={(event) =>
                    updateDraft(
                      "primaryClaim",
                      event.target.value,
                    )
                  }
                  maxLength={2000}
                  required
                />
                <span className="mt-1 block text-right text-xs text-muted">
                  {draft.primaryClaim.length}/2,000
                </span>
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                공개 요약
                <textarea
                  className={`${INPUT_CLASS} mt-1.5 min-h-24 py-3`}
                  value={draft.publicSummary}
                  onChange={(event) =>
                    updateDraft(
                      "publicSummary",
                      event.target.value,
                    )
                  }
                  maxLength={1000}
                  placeholder="선택 입력"
                />
                <span className="mt-1 block text-right text-xs text-muted">
                  {draft.publicSummary.length}/1,000
                </span>
              </label>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-bold">연결·표시 설정</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                연결 종목
                <select
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.portfolioItemId}
                  onChange={(event) =>
                    updateDraft(
                      "portfolioItemId",
                      event.target.value,
                    )
                  }
                  disabled={portfolioLoading}
                  required
                >
                  <option value="">
                    {portfolioLoading
                      ? "등록 종목 불러오는 중…"
                      : "선택"}
                  </option>
                  {portfolioItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.symbol} · {item.market})
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-sm font-semibold">
                원문 언어
                <select
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.language}
                  onChange={(event) =>
                    updateDraft("language", event.target.value)
                  }
                >
                  <option value="ko">한국어</option>
                  <option value="en">영어</option>
                  <option value="und">확인되지 않음</option>
                </select>
              </label>
            </div>

            <label className="mt-4 flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-sm">
              <input
                type="checkbox"
                checked={draft.materialChange}
                onChange={(event) =>
                  updateDraft(
                    "materialChange",
                    event.target.checked,
                  )
                }
              />
              <span>
                <strong className="block">
                  중요 변경으로 표시
                </strong>
                <span className="mt-1 block text-xs leading-5 text-muted">
                  통합 사건과 브리핑 검토 대상으로 연결합니다.
                </span>
              </span>
            </label>

            {selectedPortfolio ? (
              <p className="mt-3 text-xs text-cyan">
                연결 예정: {selectedPortfolio.name} ·{" "}
                {selectedPortfolio.symbol} · {selectedPortfolio.market}
              </p>
            ) : null}
          </section>

          {error ? (
            <p
              role="alert"
              className="rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red"
            >
              {error}
            </p>
          ) : null}

          {confirmCompleted ? (
            <section className="rounded-2xl border border-green/40 bg-green/10 p-4">
              <h3 className="font-bold text-green">등록 완료</h3>
              <p className="mt-2 text-sm leading-6 text-secondary">
                중요 정보와 핵심 주장, 통합 사건 연결이 저장됐습니다.
                창을 닫으면 목록에서 확인할 수 있습니다.
              </p>
            </section>
          ) : null}

          {preview ? (
            <section className="rounded-2xl border border-cyan/30 bg-cyan/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-bold">등록 전 검증 결과</h3>
                <span
                  className={
                    preview.wouldCreate
                      ? "text-sm font-bold text-green"
                      : "text-sm font-bold text-red"
                  }
                >
                  {preview.wouldCreate
                    ? "등록 가능"
                    : "등록 차단"}
                </span>
              </div>

              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <dt className="text-xs text-muted">정규화 URL</dt>
                  <dd className="mt-1 break-all font-medium">
                    {preview.normalizedUrl}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">연결 종목</dt>
                  <dd className="mt-1 font-medium">
                    {preview.portfolioItem.name} (
                    {preview.portfolioItem.symbol})
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">출처 분류</dt>
                  <dd className="mt-1 font-medium">
                    출처 {preview.classification.sourceGrade} ·{" "}
                    {preview.classification.officialSource
                      ? "공식 출처"
                      : "비공식 출처"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">예상 검증 상태</dt>
                  <dd className="mt-1 font-medium">
                    {
                      verificationLabels[
                        preview.classification
                          .predictedVerificationStatus
                      ]
                    }
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">중복 링크</dt>
                  <dd className="mt-1 font-medium">
                    {preview.duplicate.duplicate
                      ? "있음"
                      : "없음"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">출처 항목</dt>
                  <dd className="mt-1 font-medium">
                    {preview.wouldCreateSource
                      ? "새로 생성"
                      : "기존 항목 재사용"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">검증 종목 연결</dt>
                  <dd className="mt-1 font-medium">
                    {preview.wouldCreateInstrument
                      ? "새로 연결"
                      : "기존 연결 재사용"}
                  </dd>
                </div>
              </dl>

              {preview.validationWarnings.length ? (
                <ul className="mt-4 space-y-1 text-sm text-secondary">
                  {preview.validationWarnings.map((warning) => (
                    <li key={warning}>
                      · {warningLabel(warning)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-4 text-sm text-green">
                  추가 검증 경고가 없습니다.
                </p>
              )}

              <p className="mt-4 text-xs leading-5 text-muted">
                현재는 검증만 수행했습니다. DB에는 저장되지 않았고
                외부 사이트에도 접속하지 않았습니다.
              </p>
            </section>
          ) : null}
        </div>

        <footer className="flex flex-col-reverse gap-2 border-t border-border p-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={previewLoading || confirmLoading}
            className="min-h-11 rounded-xl border border-border px-4 text-sm font-semibold disabled:opacity-60"
          >
            닫기
          </button>

          <button
            type="submit"
            disabled={
              previewLoading ||
              confirmLoading ||
              portfolioLoading ||
              confirmCompleted
            }
            className="min-h-11 rounded-xl bg-cyan px-5 text-sm font-bold text-background disabled:opacity-60"
          >
            {confirmCompleted
              ? "등록 완료"
              : previewLoading
                ? "검증 중…"
                : "등록 전 검증"}
          </button>

          {preview?.wouldCreate && !confirmCompleted ? (
            <button
              type="button"
              onClick={confirmImport}
              disabled={previewLoading || confirmLoading}
              className="min-h-11 rounded-xl border border-green px-5 text-sm font-bold text-green disabled:opacity-60"
            >
              {confirmLoading ? "등록 중…" : "최종 등록"}
            </button>
          ) : null}
        </footer>
      </form>
    </Dialog>
  );
}
