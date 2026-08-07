"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Dialog } from "@/components/common/dialog";
import {
  importAnalystReferenceLink,
} from "@/lib/api/analyst-references";
import { ApiClientError } from "@/lib/api/client";
import { listPortfolio } from "@/lib/api/portfolio";
import type {
  AnalystAccessType,
  AnalystDocumentType,
  AnalystPublisherType,
  AnalystReferenceImportLinkInput,
  AnalystReferenceImportLinkPreview,
  PortfolioItem,
} from "@/types/api";

interface AnalystReferenceImportDialogProps {
  onClose: () => void;
}

interface ImportDraft {
  sourceUrl: string;
  publisherName: string;
  publisherType: AnalystPublisherType | "";
  title: string;
  analystName: string;
  publishedAt: string;
  accessType: AnalystAccessType | "";
  documentType: AnalystDocumentType | "";
  publisherRatingRaw: string;
  publisherTargetPriceRaw: string;
  targetCurrency: string;
  publicAbstract: string;
  portfolioItemIds: string[];
}

const EMPTY_DRAFT: ImportDraft = {
  sourceUrl: "",
  publisherName: "",
  publisherType: "",
  title: "",
  analystName: "",
  publishedAt: "",
  accessType: "",
  documentType: "",
  publisherRatingRaw: "",
  publisherTargetPriceRaw: "",
  targetCurrency: "",
  publicAbstract: "",
  portfolioItemIds: [],
};

const INPUT_CLASS =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 " +
  "text-sm text-foreground placeholder:text-muted focus:border-cyan " +
  "disabled:opacity-60";

const publisherTypeOptions: Array<{
  value: AnalystPublisherType;
  label: string;
}> = [
  { value: "BROKER", label: "증권사" },
  { value: "RESEARCH_HOUSE", label: "리서치 기관" },
  { value: "FINANCIAL_MEDIA", label: "금융 미디어" },
  { value: "INSTITUTION", label: "기관" },
  { value: "OTHER", label: "기타" },
];

const accessTypeOptions: Array<{
  value: AnalystAccessType;
  label: string;
}> = [
  { value: "PUBLIC", label: "공개" },
  { value: "LOGIN_REQUIRED", label: "로그인 필요" },
  { value: "PAYWALLED", label: "유료 접근" },
  { value: "UNKNOWN", label: "확인되지 않음" },
];

const documentTypeOptions: Array<{
  value: AnalystDocumentType;
  label: string;
}> = [
  { value: "REPORT", label: "보고서" },
  { value: "COMMENTARY", label: "코멘터리" },
  { value: "INTERVIEW", label: "인터뷰" },
  { value: "CONSENSUS", label: "컨센서스" },
  { value: "OTHER", label: "기타" },
];

const warningLabels: Record<string, string> = {
  URL_FRAGMENT_REMOVED: "URL의 #fragment가 제거됩니다.",
  URL_NORMALIZED: "URL이 표준 형식으로 정규화됩니다.",
  DUPLICATE_PORTFOLIO_ITEM_IDS_REMOVED:
    "중복 선택된 종목은 한 번만 연결됩니다.",
  DUPLICATE_CANONICAL_URL:
    "동일한 URL로 등록된 참고자료가 이미 있습니다.",
  DUPLICATE_SOURCE_FINGERPRINT:
    "동일한 공개 메타데이터의 참고자료가 이미 있습니다.",
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
  if (!draft.publisherType) {
    return "발행사 유형을 선택해 주세요.";
  }
  if (!draft.title.trim()) {
    return "자료 제목을 입력해 주세요.";
  }
  if (!draft.publishedAt) {
    return "발행 일시를 입력해 주세요.";
  }
  if (!draft.accessType) {
    return "접근 유형을 선택해 주세요.";
  }
  if (!draft.documentType) {
    return "자료 유형을 선택해 주세요.";
  }
  if (!draft.portfolioItemIds.length) {
    return "연결할 보유·관심 종목을 한 개 이상 선택해 주세요.";
  }
  if (draft.publicAbstract.length > 300) {
    return "공개 요약은 300자 이하로 입력해 주세요.";
  }

  return "";
}

function warningLabel(value: string): string {
  if (warningLabels[value]) {
    return warningLabels[value];
  }

  if (value.startsWith("PORTFOLIO_ITEM_NOT_FOUND:")) {
    return `존재하지 않는 종목 ID가 포함됐습니다: ${
      value.split(":")[1] ?? ""
    }`;
  }

  if (value.startsWith("ARCHIVED_PORTFOLIO_ITEM:")) {
    return `보관된 종목이 포함됐습니다: ${
      value.split(":")[1] ?? ""
    }`;
  }

  return value;
}

export function AnalystReferenceImportDialog({
  onClose,
}: AnalystReferenceImportDialogProps) {
  const [draft, setDraft] = useState<ImportDraft>(EMPTY_DRAFT);
  const [portfolioItems, setPortfolioItems] = useState<PortfolioItem[]>([]);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmCompleted, setConfirmCompleted] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] =
    useState<AnalystReferenceImportLinkPreview | null>(null);

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

        setError("보유·관심 종목을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setPortfolioLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  const selectedPortfolioItems = useMemo(
    () =>
      portfolioItems.filter((item) =>
        draft.portfolioItemIds.includes(item.id),
      ),
    [draft.portfolioItemIds, portfolioItems],
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

  function togglePortfolioItem(portfolioItemId: string) {
    const selected = draft.portfolioItemIds.includes(portfolioItemId);

    updateDraft(
      "portfolioItemIds",
      selected
        ? draft.portfolioItemIds.filter(
            (itemId) => itemId !== portfolioItemId,
          )
        : [...draft.portfolioItemIds, portfolioItemId],
    );
  }

  function createPayload(
    confirm: boolean,
  ): AnalystReferenceImportLinkInput {
    if (
      !draft.publisherType ||
      !draft.accessType ||
      !draft.documentType
    ) {
      throw new Error("필수 선택값이 없습니다.");
    }

    return {
      sourceUrl: draft.sourceUrl.trim(),
      publisherName: draft.publisherName.trim(),
      publisherType: draft.publisherType,
      title: draft.title.trim(),
      analystName: optionalText(draft.analystName),
      publishedAt: new Date(draft.publishedAt).toISOString(),
      accessType: draft.accessType,
      documentType: draft.documentType,
      publisherRatingRaw: optionalText(
        draft.publisherRatingRaw,
      ),
      publisherTargetPriceRaw: optionalText(
        draft.publisherTargetPriceRaw,
      ),
      targetCurrency:
        optionalText(draft.targetCurrency)?.toUpperCase() ?? null,
      publicAbstract: optionalText(draft.publicAbstract),
      portfolioItemIds: draft.portfolioItemIds,
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
      const result = await importAnalystReferenceLink(
        createPayload(false),
      );

      if (result.confirmed) {
        setError(
          "Preview 요청에서 예상하지 않은 Confirm 응답을 받았습니다.",
        );
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
      const result = await importAnalystReferenceLink(
        createPayload(true),
      );

      if (!result.confirmed) {
        setError(
          "Confirm request returned a preview response.",
        );
        return;
      }

      setConfirmCompleted(true);
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "Failed to register the analyst reference.",
      );
    } finally {
      setConfirmLoading(false);
    }
  }

  return (
    <Dialog
      title="애널리스트 참고자료 링크 등록"
      description={
        "공개된 제목·발행사·날짜·링크와 공개 메타데이터만 " +
        "검증합니다. 원문·PDF·기사 본문은 저장하지 않습니다."
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
            <h3 className="text-sm font-bold">필수 공개 정보</h3>

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
                  required
                />
              </label>

              <label className="text-sm font-semibold">
                발행사 유형
                <select
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.publisherType}
                  onChange={(event) =>
                    updateDraft(
                      "publisherType",
                      event.target.value as
                        | AnalystPublisherType
                        | "",
                    )
                  }
                  required
                >
                  <option value="">선택</option>
                  {publisherTypeOptions.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                자료 제목
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
                애널리스트
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.analystName}
                  onChange={(event) =>
                    updateDraft(
                      "analystName",
                      event.target.value,
                    )
                  }
                  placeholder="선택 입력"
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

              <label className="text-sm font-semibold">
                접근 유형
                <select
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.accessType}
                  onChange={(event) =>
                    updateDraft(
                      "accessType",
                      event.target.value as
                        | AnalystAccessType
                        | "",
                    )
                  }
                  required
                >
                  <option value="">선택</option>
                  {accessTypeOptions.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-sm font-semibold">
                자료 유형
                <select
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.documentType}
                  onChange={(event) =>
                    updateDraft(
                      "documentType",
                      event.target.value as
                        | AnalystDocumentType
                        | "",
                    )
                  }
                  required
                >
                  <option value="">선택</option>
                  {documentTypeOptions.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-bold">
              공개 메타데이터
            </h3>
            <p className="mt-1 text-xs leading-5 text-muted">
              발행사가 공개한 원문 표현만 입력하며 자동 판단에
              사용하지 않습니다.
            </p>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                공개 투자의견 원문
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.publisherRatingRaw}
                  onChange={(event) =>
                    updateDraft(
                      "publisherRatingRaw",
                      event.target.value,
                    )
                  }
                  placeholder="선택 입력"
                />
              </label>

              <label className="text-sm font-semibold">
                공개 목표가 원문
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.publisherTargetPriceRaw}
                  onChange={(event) =>
                    updateDraft(
                      "publisherTargetPriceRaw",
                      event.target.value,
                    )
                  }
                  placeholder="선택 입력"
                />
              </label>

              <label className="text-sm font-semibold">
                목표가 통화
                <input
                  className={`${INPUT_CLASS} mt-1.5 uppercase`}
                  value={draft.targetCurrency}
                  onChange={(event) =>
                    updateDraft(
                      "targetCurrency",
                      event.target.value,
                    )
                  }
                  placeholder="KRW, USD"
                  maxLength={12}
                />
              </label>

              <label className="text-sm font-semibold sm:col-span-2">
                공개 요약
                <textarea
                  className={`${INPUT_CLASS} mt-1.5 min-h-24 py-3`}
                  value={draft.publicAbstract}
                  onChange={(event) =>
                    updateDraft(
                      "publicAbstract",
                      event.target.value,
                    )
                  }
                  maxLength={300}
                  placeholder="공개된 요약문이 있을 때만 입력"
                />
                <span className="mt-1 block text-right text-xs text-muted">
                  {draft.publicAbstract.length}/300
                </span>
              </label>
            </div>
          </section>

          <section>
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold">
                  연결 대상 종목
                </h3>
                <p className="mt-1 text-xs text-muted">
                  현재 등록된 보유·관심 종목만 선택할 수 있습니다.
                </p>
              </div>

              <span className="text-xs font-semibold text-cyan">
                {selectedPortfolioItems.length}개 선택
              </span>
            </div>

            <div className="mt-3 max-h-56 space-y-2 overflow-y-auto rounded-xl border border-border bg-card p-3">
              {portfolioLoading ? (
                <p className="py-6 text-center text-sm text-muted">
                  종목 불러오는 중…
                </p>
              ) : portfolioItems.length ? (
                portfolioItems.map((item) => (
                  <label
                    key={item.id}
                    className="flex cursor-pointer items-center gap-3 rounded-lg border border-transparent px-3 py-2 hover:border-border hover:bg-surface"
                  >
                    <input
                      type="checkbox"
                      checked={draft.portfolioItemIds.includes(
                        item.id,
                      )}
                      onChange={() =>
                        togglePortfolioItem(item.id)
                      }
                    />
                    <span className="min-w-0">
                      <strong className="block truncate text-sm">
                        {item.name}
                      </strong>
                      <span className="block text-xs text-muted">
                        {item.symbol} · {item.market}
                      </span>
                    </span>
                  </label>
                ))
              ) : (
                <p className="py-6 text-center text-sm text-muted">
                  선택할 수 있는 등록 종목이 없습니다.
                </p>
              )}
            </div>
          </section>

          {error ? (
            <p
              role="alert"
              className="rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red"
            >
              {error}
            </p>
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

              <dl className="mt-4 space-y-3 text-sm">
                <div>
                  <dt className="text-xs text-muted">
                    정규화 URL
                  </dt>
                  <dd className="mt-1 break-all font-medium">
                    {preview.normalizedUrl}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">
                    Fingerprint
                  </dt>
                  <dd className="mt-1 break-all font-mono text-xs">
                    {preview.sourceFingerprint}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">
                    연결 대상
                  </dt>
                  <dd className="mt-1">
                    {preview.portfolioItems
                      .map(
                        (item) =>
                          `${item.name} (${item.symbol})`,
                      )
                      .join(", ") || "없음"}
                  </dd>
                </div>
              </dl>

              <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                <p className="rounded-xl border border-border bg-card p-3">
                  동일 URL:{" "}
                  <strong>
                    {preview.duplicate.canonicalUrlDuplicate
                      ? "있음"
                      : "없음"}
                  </strong>
                </p>
                <p className="rounded-xl border border-border bg-card p-3">
                  동일 메타데이터:{" "}
                  <strong>
                    {preview.duplicate.sourceFingerprintDuplicate
                      ? "있음"
                      : "없음"}
                  </strong>
                </p>
              </div>

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
                현재는 Preview만 수행했습니다. DB에는 저장되지
                않았습니다.
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
            {"\uB2EB\uAE30"}
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
              ? "\uB4F1\uB85D \uC644\uB8CC"
              : previewLoading
                ? "\uAC80\uC99D \uC911\u2026"
                : "\uB4F1\uB85D \uC804 \uAC80\uC99D"}
          </button>

          {preview?.wouldCreate && !confirmCompleted ? (
            <button
              type="button"
              onClick={confirmImport}
              disabled={previewLoading || confirmLoading}
              className="min-h-11 rounded-xl border border-green px-5 text-sm font-bold text-green disabled:opacity-60"
            >
              {confirmLoading
                ? "\uB4F1\uB85D \uC911\u2026"
                : "\uCD5C\uC885 \uB4F1\uB85D"}
            </button>
          ) : null}
        </footer>
      </form>
    </Dialog>
  );
}
