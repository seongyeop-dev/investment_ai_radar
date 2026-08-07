"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Dialog } from "@/components/common/dialog";
import { ApiClientError } from "@/lib/api/client";
import { importOfficialDisclosure } from "@/lib/api/news";
import { listPortfolio } from "@/lib/api/portfolio";
import { verificationLabels } from "@/lib/news";
import type {
  OfficialDisclosureImportInput,
  OfficialDisclosureImportPreview,
  PortfolioItem,
} from "@/types/api";

interface OfficialDisclosureImportDialogProps {
  onClose: () => void;
  onCompleted: () => void;
}

interface ImportDraft {
  officialUrl: string;
  title: string;
  publishedAt: string;
  claim: string;
  summary: string;
  portfolioItemId: string;
  formType: string;
  materialChange: boolean;
}

const EMPTY_DRAFT: ImportDraft = {
  officialUrl: "",
  title: "",
  publishedAt: "",
  claim: "",
  summary: "",
  portfolioItemId: "",
  formType: "",
  materialChange: true,
};

const INPUT_CLASS =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 " +
  "text-sm text-foreground placeholder:text-muted focus:border-cyan " +
  "disabled:opacity-60";

const warningLabels: Record<string, string> = {
  URL_NORMALIZED: "추적값과 화면 위치값을 제거해 공식 주소를 표준화합니다.",
  SEC_OFFICIAL_URL_CONFIRMED: "SEC 공식 도메인을 확인했습니다.",
  OPENDART_OFFICIAL_URL_CONFIRMED: "OpenDART 공식 도메인을 확인했습니다.",
  DUPLICATE_OFFICIAL_DISCLOSURE: "동일한 공식 공시가 이미 등록되어 있습니다.",
  INSTRUMENT_WILL_BE_CREATED: "선택한 등록 종목을 공식 공시 종목과 연결합니다.",
};

function optionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

function validateOfficialUrl(value: string): string {
  try {
    const url = new URL(value.trim());
    if (!["http:", "https:"].includes(url.protocol)) {
      return "공식 원문은 HTTP 또는 HTTPS 주소만 사용할 수 있습니다.";
    }
    const hostname = url.hostname.toLowerCase();
    const sec = hostname === "sec.gov" || hostname.endsWith(".sec.gov");
    const dart = ["dart.fss.or.kr", "opendart.fss.or.kr"].includes(
      hostname,
    );
    if (!sec && !dart) {
      return "SEC 또는 OpenDART 공식 주소를 입력해 주세요.";
    }
    return "";
  } catch {
    return "공식 원문 주소 형식을 확인해 주세요.";
  }
}

function validateDraft(draft: ImportDraft): string {
  if (!draft.officialUrl.trim()) {
    return "공식 원문 주소를 입력해 주세요.";
  }
  const urlError = validateOfficialUrl(draft.officialUrl);
  if (urlError) return urlError;
  if (!draft.title.trim()) {
    return "공시 제목을 입력해 주세요.";
  }
  if (!draft.publishedAt) {
    return "공시 일시를 입력해 주세요.";
  }
  if (!draft.claim.trim()) {
    return "핵심 공시 내용을 입력해 주세요.";
  }
  if (!draft.portfolioItemId) {
    return "연결할 등록 종목을 선택해 주세요.";
  }
  return "";
}

function warningLabel(value: string): string {
  return warningLabels[value] ?? value;
}

export function OfficialDisclosureImportDialog({
  onClose,
  onCompleted,
}: OfficialDisclosureImportDialogProps) {
  const [draft, setDraft] = useState<ImportDraft>(EMPTY_DRAFT);
  const [portfolioItems, setPortfolioItems] = useState<PortfolioItem[]>([]);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmCompleted, setConfirmCompleted] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] =
    useState<OfficialDisclosureImportPreview | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listPortfolio({ limit: 100, offset: 0 }, controller.signal)
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
        if (!controller.signal.aborted) setPortfolioLoading(false);
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
    setDraft((current) => ({ ...current, [key]: value }));
    setPreview(null);
    setConfirmCompleted(false);
    setError("");
  }

  function createPayload(
    confirm: boolean,
  ): OfficialDisclosureImportInput {
    return {
      officialUrl: draft.officialUrl.trim(),
      title: draft.title.trim(),
      publishedAt: new Date(draft.publishedAt).toISOString(),
      claim: draft.claim.trim(),
      summary: optionalText(draft.summary),
      portfolioItemId: draft.portfolioItemId,
      formType: optionalText(draft.formType),
      materialChange: draft.materialChange,
      confirm,
    };
  }

  async function submitPreview(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    if (previewLoading || confirmLoading) return;

    const validationError = validateDraft(draft);
    if (validationError) {
      setError(validationError);
      return;
    }

    setPreviewLoading(true);
    setPreview(null);
    setError("");
    try {
      const result = await importOfficialDisclosure(
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
      const result = await importOfficialDisclosure(
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
          : "공식 공시를 등록하지 못했습니다.",
      );
    } finally {
      setConfirmLoading(false);
    }
  }

  return (
    <Dialog
      title="공식 공시 등록"
      description={
        "SEC 또는 OpenDART 공식 원문 링크와 구조화된 핵심 정보만 저장합니다. " +
        "공시 전문은 저장하지 않으며 공식 도메인, 중복, 연결 종목을 먼저 확인합니다."
      }
      onRequestClose={() => {
        if (!previewLoading && !confirmLoading) onClose();
      }}
    >
      <form
        className="flex min-h-0 flex-1 flex-col"
        onSubmit={submitPreview}
      >
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5 sm:px-6">
          <section>
            <h3 className="text-sm font-bold">공식 공개 정보</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold sm:col-span-2">
                공식 원문 주소
                <input
                  data-autofocus="true"
                  type="url"
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.officialUrl}
                  onChange={(event) =>
                    updateDraft("officialUrl", event.target.value)
                  }
                  placeholder="https://www.sec.gov/... 또는 https://dart.fss.or.kr/..."
                  required
                />
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                공시 제목
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.title}
                  onChange={(event) =>
                    updateDraft("title", event.target.value)
                  }
                  required
                />
              </label>

              <label className="text-sm font-semibold">
                공시 일시
                <input
                  type="datetime-local"
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.publishedAt}
                  onChange={(event) =>
                    updateDraft("publishedAt", event.target.value)
                  }
                  required
                />
              </label>

              <label className="text-sm font-semibold">
                서식·공시 종류
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.formType}
                  onChange={(event) =>
                    updateDraft("formType", event.target.value)
                  }
                  placeholder="예: 8-K, 10-Q, 주요사항보고서"
                />
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                핵심 공시 내용
                <textarea
                  className={`${INPUT_CLASS} mt-1.5 min-h-28 py-3`}
                  value={draft.claim}
                  onChange={(event) =>
                    updateDraft("claim", event.target.value)
                  }
                  maxLength={2000}
                  required
                />
                <span className="mt-1 block text-right text-xs text-muted">
                  {draft.claim.length}/2,000
                </span>
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                구조화 요약
                <textarea
                  className={`${INPUT_CLASS} mt-1.5 min-h-24 py-3`}
                  value={draft.summary}
                  onChange={(event) =>
                    updateDraft("summary", event.target.value)
                  }
                  maxLength={2000}
                  placeholder="선택 입력"
                />
                <span className="mt-1 block text-right text-xs text-muted">
                  {draft.summary.length}/2,000
                </span>
              </label>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-bold">연결·표시 설정</h3>
            <label className="mt-4 block text-sm font-semibold">
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
                <strong className="block">중요 공시로 표시</strong>
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
                공식 공시와 통합 사건 연결이 저장됐습니다.
              </p>
            </section>
          ) : null}

          {preview ? (
            <section className="rounded-2xl border border-cyan/40 bg-cyan/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-bold">등록 전 검증 결과</h3>
                <strong
                  className={
                    preview.wouldCreate
                      ? "text-green"
                      : "text-red"
                  }
                >
                  {preview.wouldCreate
                    ? "등록 가능"
                    : "중복 공시"}
                </strong>
              </div>

              <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <dt className="text-xs text-muted">정규화 URL</dt>
                  <dd className="mt-1 break-all font-semibold">
                    {preview.normalizedUrl}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">공식 제공자</dt>
                  <dd className="mt-1 font-semibold">
                    {preview.classification.providerLabel}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">출처 분류</dt>
                  <dd className="mt-1 font-semibold">
                    출처 {preview.classification.sourceGrade} · 공식 출처
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">예상 검증 상태</dt>
                  <dd className="mt-1 font-semibold">
                    {
                      verificationLabels[
                        preview.classification
                          .predictedVerificationStatus
                      ]
                    }
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">중복 공시</dt>
                  <dd className="mt-1 font-semibold">
                    {preview.duplicate.duplicate ? "있음" : "없음"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">연결 종목</dt>
                  <dd className="mt-1 font-semibold">
                    {preview.portfolioItem.name} (
                    {preview.portfolioItem.symbol})
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">종목 연결</dt>
                  <dd className="mt-1 font-semibold">
                    {preview.wouldCreateInstrument
                      ? "새로 연결"
                      : "기존 연결 사용"}
                  </dd>
                </div>
              </dl>

              {preview.validationWarnings.length ? (
                <ul className="mt-4 space-y-1 text-xs leading-5 text-secondary">
                  {preview.validationWarnings.map((warning) => (
                    <li key={warning}>· {warningLabel(warning)}</li>
                  ))}
                </ul>
              ) : null}

              <p className="mt-4 text-xs leading-5 text-muted">
                현재는 검증만 수행했습니다. DB에는 저장하지 않았고
                외부 사이트에도 접속하지 않았습니다.
              </p>
            </section>
          ) : null}
        </div>

        <footer className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-4 sm:px-6">
          <button
            type="button"
            onClick={onClose}
            disabled={previewLoading || confirmLoading}
            className="min-h-11 rounded-xl border border-border px-4 text-sm font-bold"
          >
            닫기
          </button>
          <button
            type="submit"
            disabled={
              previewLoading ||
              confirmLoading ||
              confirmCompleted
            }
            className="min-h-11 rounded-xl bg-cyan px-5 text-sm font-bold text-black disabled:opacity-60"
          >
            {previewLoading ? "검증 중…" : "등록 전 검증"}
          </button>
          <button
            type="button"
            onClick={confirmImport}
            disabled={
              !preview?.wouldCreate ||
              confirmLoading ||
              confirmCompleted
            }
            className="min-h-11 rounded-xl border border-green px-5 text-sm font-bold text-green disabled:opacity-40"
          >
            {confirmLoading
              ? "등록 중…"
              : confirmCompleted
                ? "등록 완료"
                : "최종 등록"}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
