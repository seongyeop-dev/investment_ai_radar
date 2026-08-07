"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Dialog } from "@/components/common/dialog";
import {
  importReferenceSubscription,
  listReferenceSubscriptionSources,
} from "@/lib/api/analyst-references";
import { ApiClientError } from "@/lib/api/client";
import type {
  ReferenceMatchMode,
  ReferenceSubjectType,
  ReferenceSubscription,
  ReferenceSubscriptionImportInput,
  ReferenceSubscriptionImportPreview,
  ReferenceSubscriptionSource,
} from "@/types/api";

interface ReferenceSubscriptionImportDialogProps {
  onClose: () => void;
  onCreated: (
    subscription: ReferenceSubscription,
  ) => void;
}

interface ImportDraft {
  sourceId: string;
  subjectType: ReferenceSubjectType | "";
  displayName: string;
  matchMode: ReferenceMatchMode | "";
  matchTermsText: string;
}

const EMPTY_DRAFT: ImportDraft = {
  sourceId: "",
  subjectType: "",
  displayName: "",
  matchMode: "",
  matchTermsText: "",
};

const INPUT_CLASS =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 " +
  "text-sm text-foreground placeholder:text-muted focus:border-cyan " +
  "disabled:opacity-60";

const subjectOptions: Array<{
  value: ReferenceSubjectType;
  label: string;
}> = [
  {
    value: "EXPERT",
    label: "전문가",
  },
  {
    value: "INSTITUTION",
    label: "기관",
  },
  {
    value: "PUBLISHER",
    label: "발행사",
  },
];

const matchModeOptions: Array<{
  value: ReferenceMatchMode;
  label: string;
  description: string;
}> = [
  {
    value: "ALL_SOURCE",
    label: "출처 전체",
    description:
      "선택한 공식 Source의 모든 신규 자료를 확인합니다.",
  },
  {
    value: "AUTHOR",
    label: "저자명 일치",
    description:
      "저자 또는 전문가 이름이 일치하는 자료만 확인합니다.",
  },
  {
    value: "KEYWORD",
    label: "키워드 일치",
    description:
      "제목과 공개 메타데이터의 키워드가 일치하는 자료만 확인합니다.",
  },
];

const warningLabels: Record<string, string> = {
  SOURCE_NOT_FOUND:
    "선택한 공식 Source를 찾을 수 없습니다.",
  SOURCE_NOT_OFFICIAL:
    "공식 출처로 확인되지 않아 등록할 수 없습니다.",
  SOURCE_DISABLED:
    "현재 비활성화된 Source라 등록할 수 없습니다.",
  DUPLICATE_SUBSCRIPTION:
    "동일한 관심 대상 구독이 이미 등록되어 있습니다.",
};

function parseMatchTerms(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function validateDraft(draft: ImportDraft): string {
  if (!draft.sourceId) {
    return "공식 Source를 선택해 주세요.";
  }

  if (!draft.subjectType) {
    return "관심 대상 유형을 선택해 주세요.";
  }

  if (!draft.displayName.trim()) {
    return "전문가·기관 이름을 입력해 주세요.";
  }

  if (!draft.matchMode) {
    return "자료 연결 조건을 선택해 주세요.";
  }

  if (
    draft.matchMode !== "ALL_SOURCE" &&
    !parseMatchTerms(draft.matchTermsText).length
  ) {
    return "저자명 또는 검색 키워드를 한 개 이상 입력해 주세요.";
  }

  return "";
}

function warningLabel(value: string): string {
  return warningLabels[value] ?? value;
}

export function ReferenceSubscriptionImportDialog({
  onClose,
  onCreated,
}: ReferenceSubscriptionImportDialogProps) {
  const [draft, setDraft] =
    useState<ImportDraft>(EMPTY_DRAFT);
  const [sources, setSources] = useState<
    ReferenceSubscriptionSource[]
  >([]);
  const [sourcesLoading, setSourcesLoading] =
    useState(true);
  const [previewLoading, setPreviewLoading] =
    useState(false);
  const [confirmLoading, setConfirmLoading] =
    useState(false);
  const [confirmCompleted, setConfirmCompleted] =
    useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] =
    useState<ReferenceSubscriptionImportPreview | null>(
      null,
    );

  useEffect(() => {
    const controller = new AbortController();

    listReferenceSubscriptionSources(
      {
        limit: 100,
        offset: 0,
      },
      controller.signal,
    )
      .then((response) => {
        setSources(response.items);
        setError("");
      })
      .catch((reason: unknown) => {
        if (
          reason instanceof ApiClientError &&
          reason.kind === "cancelled"
        ) {
          return;
        }

        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "공식 Source 목록을 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setSourcesLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  const selectedSource = useMemo(
    () =>
      sources.find(
        (source) => source.id === draft.sourceId,
      ) ?? null,
    [draft.sourceId, sources],
  );

  const selectedMatchMode = useMemo(
    () =>
      matchModeOptions.find(
        (option) =>
          option.value === draft.matchMode,
      ) ?? null,
    [draft.matchMode],
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
  ): ReferenceSubscriptionImportInput {
    if (
      !draft.subjectType ||
      !draft.matchMode
    ) {
      throw new Error(
        "필수 선택값이 없습니다.",
      );
    }

    return {
      sourceId: draft.sourceId,
      subjectType: draft.subjectType,
      displayName: draft.displayName.trim(),
      matchMode: draft.matchMode,
      matchTerms:
        draft.matchMode === "ALL_SOURCE"
          ? []
          : parseMatchTerms(
              draft.matchTermsText,
            ),
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

    const validationError =
      validateDraft(draft);

    if (validationError) {
      setError(validationError);
      return;
    }

    setPreviewLoading(true);
    setPreview(null);
    setError("");

    try {
      const result =
        await importReferenceSubscription(
          createPayload(false),
        );

      if (result.confirmed) {
        setError(
          "Preview 요청에서 예상하지 않은 등록 응답을 받았습니다.",
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
      const result =
        await importReferenceSubscription(
          createPayload(true),
        );

      if (!result.confirmed) {
        setError(
          "최종 등록 요청에서 Preview 응답을 받았습니다.",
        );
        return;
      }

      setConfirmCompleted(true);
      onCreated(result.subscription);
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "관심 대상 구독을 등록하지 못했습니다.",
      );
    } finally {
      setConfirmLoading(false);
    }
  }

  return (
    <Dialog
      title="관심 전문가·기관 자동 구독"
      description={
        "검증된 공식 Source와 공개 메타데이터만 사용합니다. " +
        "등록 후 신규 자료 확인은 자동화되지만 투자 판단 " +
        "계산에는 연결되지 않습니다."
      }
      onRequestClose={() => {
        if (
          !previewLoading &&
          !confirmLoading
        ) {
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
            <h3 className="text-sm font-bold">
              공식 출처와 관심 대상
            </h3>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold sm:col-span-2">
                공식 Source
                <select
                  data-autofocus="true"
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.sourceId}
                  onChange={(event) =>
                    updateDraft(
                      "sourceId",
                      event.target.value,
                    )
                  }
                  disabled={
                    sourcesLoading ||
                    !sources.length
                  }
                  required
                >
                  <option value="">
                    {sourcesLoading
                      ? "불러오는 중…"
                      : sources.length
                        ? "선택"
                        : "사용 가능한 공식 Source 없음"}
                  </option>

                  {sources.map((source) => (
                    <option
                      key={source.id}
                      value={source.id}
                    >
                      {source.name} · {source.domain}
                    </option>
                  ))}
                </select>
              </label>

              {selectedSource ? (
                <div className="rounded-xl border border-border bg-card p-3 text-xs text-secondary sm:col-span-2">
                  <strong className="block text-sm text-foreground">
                    {selectedSource.name}
                  </strong>
                  <span className="mt-1 block break-all">
                    {selectedSource.domain}
                  </span>
                  <span className="mt-1 block">
                    등급 {selectedSource.sourceGrade}
                    {" · "}
                    {selectedSource.providerType ??
                      "Provider 미설정"}
                    {" · "}
                    {selectedSource.language.toUpperCase()}
                  </span>
                </div>
              ) : null}

              <label className="text-sm font-semibold">
                관심 대상 유형
                <select
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.subjectType}
                  onChange={(event) =>
                    updateDraft(
                      "subjectType",
                      event.target.value as
                        | ReferenceSubjectType
                        | "",
                    )
                  }
                  required
                >
                  <option value="">선택</option>
                  {subjectOptions.map((option) => (
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
                표시 이름
                <input
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.displayName}
                  onChange={(event) =>
                    updateDraft(
                      "displayName",
                      event.target.value,
                    )
                  }
                  placeholder="Howard Marks"
                  maxLength={200}
                  required
                />
              </label>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-bold">
              자동 연결 조건
            </h3>

            <div className="mt-4 space-y-4">
              <label className="block text-sm font-semibold">
                연결 방식
                <select
                  className={`${INPUT_CLASS} mt-1.5`}
                  value={draft.matchMode}
                  onChange={(event) =>
                    updateDraft(
                      "matchMode",
                      event.target.value as
                        | ReferenceMatchMode
                        | "",
                    )
                  }
                  required
                >
                  <option value="">선택</option>
                  {matchModeOptions.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              {selectedMatchMode ? (
                <p className="text-xs leading-5 text-muted">
                  {selectedMatchMode.description}
                </p>
              ) : null}

              {draft.matchMode !== "ALL_SOURCE" ? (
                <label className="block text-sm font-semibold">
                  저자명·키워드
                  <textarea
                    className={`${INPUT_CLASS} mt-1.5 min-h-28 py-3`}
                    value={draft.matchTermsText}
                    onChange={(event) =>
                      updateDraft(
                        "matchTermsText",
                        event.target.value,
                      )
                    }
                    placeholder={
                      "한 줄에 하나씩 입력하거나 쉼표로 구분\n" +
                      "Howard Marks\nHoward S. Marks"
                    }
                    disabled={!draft.matchMode}
                  />
                  <span className="mt-1 block text-xs leading-5 text-muted">
                    대소문자를 구분하지 않고 중복 표현은 자동으로
                    제거됩니다.
                  </span>
                </label>
              ) : null}
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
                <h3 className="font-bold">
                  등록 전 검증 결과
                </h3>

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
                    정규화된 이름
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {preview.normalizedDisplayName}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    공식 출처
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {preview.source
                      ? `${preview.source.name} · ${preview.source.domain}`
                      : "확인되지 않음"}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    적용 검색어
                  </dt>
                  <dd className="mt-1 text-secondary">
                    {preview.normalizedMatchTerms.length
                      ? preview.normalizedMatchTerms.join(", ")
                      : "출처 전체"}
                  </dd>
                </div>
              </dl>

              <p className="mt-4 rounded-xl border border-border bg-card p-3 text-sm">
                동일 구독:{" "}
                <strong>
                  {preview.duplicate.duplicate
                    ? "있음"
                    : "없음"}
                </strong>
              </p>

              {preview.validationWarnings.length ? (
                <ul className="mt-4 space-y-1 text-sm text-secondary">
                  {preview.validationWarnings.map(
                    (warning) => (
                      <li key={warning}>
                        · {warningLabel(warning)}
                      </li>
                    ),
                  )}
                </ul>
              ) : (
                <p className="mt-4 text-sm text-green">
                  추가 검증 경고가 없습니다.
                </p>
              )}

                                                        <p className="mt-4 text-xs leading-5 text-muted">
                              {confirmCompleted ? (
                                <>
                                  관심 대상 등록이 완료되었습니다.
                                  <br />
                                  신규 공개자료는 자동 확인 과정에서 추가됩니다.
                                </>
                              ) : (
                                <>
                                  현재는 Preview만 수행했습니다. DB에는 저장되지
                                  않았습니다.
                                </>
                              )}
                            </p>
            </section>
          ) : null}
        </div>

        <footer className="flex flex-col-reverse gap-2 border-t border-border p-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={
              previewLoading ||
              confirmLoading
            }
            className="min-h-11 rounded-xl border border-border px-4 text-sm font-semibold disabled:opacity-60"
          >
            닫기
          </button>

          <button
            type="submit"
            disabled={
              previewLoading ||
              confirmLoading ||
              sourcesLoading ||
              !sources.length ||
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

          {preview?.wouldCreate &&
          !confirmCompleted ? (
            <button
              type="button"
              onClick={confirmImport}
              disabled={
                previewLoading ||
                confirmLoading
              }
              className="min-h-11 rounded-xl border border-green px-5 text-sm font-bold text-green disabled:opacity-60"
            >
              {confirmLoading
                ? "등록 중…"
                : "최종 등록"}
            </button>
          ) : null}
        </footer>
      </form>
    </Dialog>
  );
}