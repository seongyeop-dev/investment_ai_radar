"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  dismissReferenceDiscoveryCandidate,
  listReferenceDiscoveryCandidateReviewHistory,
  promoteReferenceDiscoveryCandidate,
  verifyReferenceDiscoveryCandidateDate,
} from "@/lib/api/analyst-references";
import {
  ApiClientError,
} from "@/lib/api/client";
import type {
  ReferenceDiscoveryCandidate,
  ReferenceDiscoveryCandidateReviewHistory,
  ReferenceDiscoveryCandidateReviewResult,
} from "@/types/api";

const INPUT_CLASS =
  "min-h-10 w-full rounded-xl border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-cyan";

const ACTION_LABELS = {
  VERIFY_DATE: "발행일 확인",
  PROMOTE: "참고자료 등록",
  DISMISS: "검토 제외",
} as const;

type SubmittingAction =
  | "verify"
  | "promote"
  | "dismiss"
  | null;

interface ReferenceDiscoveryCandidateReviewControlsProps {
  candidate: ReferenceDiscoveryCandidate;
  onReviewed: (
    candidate: ReferenceDiscoveryCandidate,
  ) => void;
}

function formatDate(
  value: string | null,
): string {
  if (!value) {
    return "확인되지 않음";
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "ko-KR",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(parsed);
}

function toDateTimeLocalValue(
  value: string | null,
): string {
  if (!value) {
    return "";
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  const localTime = new Date(
    parsed.getTime() -
      parsed.getTimezoneOffset() * 60_000,
  );

  return localTime
    .toISOString()
    .slice(0, 16);
}

function reviewErrorMessage(
  error: unknown,
): string {
  if (error instanceof ApiClientError) {
    if (
      error.code ===
      "REFERENCE_DISCOVERY_CANDIDATE_CONFIRMATION_REQUIRED"
    ) {
      return "작업 확인 체크가 필요합니다.";
    }

    if (
      error.code ===
      "REFERENCE_DISCOVERY_CANDIDATE_STATE_INVALID"
    ) {
      return "현재 검토 상태에서는 이 작업을 수행할 수 없습니다.";
    }

    if (
      error.code ===
      "REFERENCE_DISCOVERY_CANDIDATE_PROMOTION_BLOCKED"
    ) {
      return "참고자료 등록이 차단됐습니다. 자료 중복 또는 출처 상태를 확인해 주세요.";
    }

    if (
      error.code ===
      "REFERENCE_DISCOVERY_CANDIDATE_NOT_FOUND"
    ) {
      return "검토할 후보 자료를 찾을 수 없습니다.";
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "검토 작업을 처리하지 못했습니다.";
}

export function ReferenceDiscoveryCandidateReviewControls({
  candidate,
  onReviewed,
}: ReferenceDiscoveryCandidateReviewControlsProps) {
  const [
    publishedAtInput,
    setPublishedAtInput,
  ] = useState(
    toDateTimeLocalValue(
      candidate.publishedAt,
    ),
  );

  const [
    verifyReason,
    setVerifyReason,
  ] = useState("");

  const [
    promoteReason,
    setPromoteReason,
  ] = useState("");

  const [
    dismissReason,
    setDismissReason,
  ] = useState("");

  const [
    promoteConfirmed,
    setPromoteConfirmed,
  ] = useState(false);

  const [
    dismissConfirmed,
    setDismissConfirmed,
  ] = useState(false);

  const [
    submitting,
    setSubmitting,
  ] = useState<SubmittingAction>(null);

  const [
    actionError,
    setActionError,
  ] = useState<string | null>(null);

  const [
    actionSuccess,
    setActionSuccess,
  ] = useState<string | null>(null);

  const [
    history,
    setHistory,
  ] = useState<
    ReferenceDiscoveryCandidateReviewHistory[]
  >([]);

  const [
    historyLoading,
    setHistoryLoading,
  ] = useState(true);

  const [
    historyError,
    setHistoryError,
  ] = useState<string | null>(null);

  const [
    historyRefreshKey,
    setHistoryRefreshKey,
  ] = useState(0);

  const finalStatus =
    candidate.verificationStatus === "PROMOTED" ||
    candidate.verificationStatus === "DISMISSED";

  useEffect(() => {
    const controller = new AbortController();

    async function loadHistory() {
      setHistoryLoading(true);
      setHistoryError(null);

      try {
        const response =
          await listReferenceDiscoveryCandidateReviewHistory(
            candidate.id,
            {
              limit: 50,
              offset: 0,
            },
            controller.signal,
          );

        setHistory(response.items);
      } catch (caught) {
        if (
          caught instanceof ApiClientError &&
          caught.kind === "cancelled"
        ) {
          return;
        }

        setHistory([]);
        setHistoryError(
          reviewErrorMessage(caught),
        );
      } finally {
        if (!controller.signal.aborted) {
          setHistoryLoading(false);
        }
      }
    }

    void loadHistory();

    return () => {
      controller.abort();
    };
  }, [
    candidate.id,
    historyRefreshKey,
  ]);

  function completeAction(
    result: ReferenceDiscoveryCandidateReviewResult,
    message: string,
  ) {
    setActionError(null);
    setActionSuccess(message);
    setPublishedAtInput(
      toDateTimeLocalValue(
        result.candidate.publishedAt,
      ),
    );
    setPromoteConfirmed(false);
    setDismissConfirmed(false);
    onReviewed(result.candidate);
    setHistoryRefreshKey(
      (current) => current + 1,
    );
  }

  async function verifyDate() {
    if (!publishedAtInput) {
      setActionError(
        "확인한 발행일과 시간을 입력해 주세요.",
      );
      return;
    }

    const parsed = new Date(
      publishedAtInput,
    );

    if (Number.isNaN(parsed.getTime())) {
      setActionError(
        "발행일 형식을 확인해 주세요.",
      );
      return;
    }

    setSubmitting("verify");
    setActionError(null);
    setActionSuccess(null);

    try {
      const result =
        await verifyReferenceDiscoveryCandidateDate(
          candidate.id,
          {
            publishedAt: parsed.toISOString(),
            reason:
              verifyReason.trim() || null,
          },
        );

      completeAction(
        result,
        "발행일을 확인했습니다.",
      );
    } catch (caught) {
      setActionError(
        reviewErrorMessage(caught),
      );
    } finally {
      setSubmitting(null);
    }
  }

  async function promoteCandidate() {
    if (!promoteConfirmed) {
      setActionError(
        "참고자료 등록 확인에 체크해 주세요.",
      );
      return;
    }

    setSubmitting("promote");
    setActionError(null);
    setActionSuccess(null);

    try {
      const result =
        await promoteReferenceDiscoveryCandidate(
          candidate.id,
          {
            confirm: true,
            reason:
              promoteReason.trim() || null,
          },
        );

      const message =
        result.referenceDuplicate
          ? "기존 참고자료와 중복을 확인하고 안전하게 연결했습니다."
          : "참고자료 보관함에 등록했습니다.";

      completeAction(
        result,
        message,
      );
    } catch (caught) {
      setActionError(
        reviewErrorMessage(caught),
      );
    } finally {
      setSubmitting(null);
    }
  }

  async function dismissCandidate() {
    const normalizedReason =
      dismissReason.trim();

    if (!normalizedReason) {
      setActionError(
        "검토 제외 사유를 입력해 주세요.",
      );
      return;
    }

    if (!dismissConfirmed) {
      setActionError(
        "검토 제외 확인에 체크해 주세요.",
      );
      return;
    }

    setSubmitting("dismiss");
    setActionError(null);
    setActionSuccess(null);

    try {
      const result =
        await dismissReferenceDiscoveryCandidate(
          candidate.id,
          {
            confirm: true,
            reason: normalizedReason,
          },
        );

      completeAction(
        result,
        "검토 대상에서 제외했습니다.",
      );
    } catch (caught) {
      setActionError(
        reviewErrorMessage(caught),
      );
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="mt-4 space-y-4">
      <section className="rounded-2xl border border-border bg-background/70 p-4">
        <div>
          <h5 className="font-bold">
            검토 작업
          </h5>
          <p className="mt-1 text-xs leading-5 text-muted">
            공식 링크의 메타데이터를
            확인한 후에만 발행일,
            등록, 제외 작업을 진행합니다.
          </p>
        </div>

        {actionError ? (
          <p className="mt-4 rounded-xl border border-red/40 bg-red/10 p-3 text-sm leading-6 text-red">
            {actionError}
          </p>
        ) : null}

        {actionSuccess ? (
          <p className="mt-4 rounded-xl border border-green/40 bg-green/10 p-3 text-sm leading-6 text-green">
            {actionSuccess}
          </p>
        ) : null}

        {!finalStatus ? (
          <div className="mt-4 rounded-xl border border-border bg-surface/60 p-4">
            <h6 className="text-sm font-bold">
              발행일 확인
            </h6>

            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              <label className="block text-xs font-semibold">
                확인한 발행일·시간
                <input
                  type="datetime-local"
                  value={publishedAtInput}
                  onChange={(event) => {
                    setPublishedAtInput(
                      event.target.value,
                    );
                  }}
                  className={`${INPUT_CLASS} mt-1.5`}
                />
              </label>

              <label className="block text-xs font-semibold">
                확인 메모 선택
                <input
                  value={verifyReason}
                  onChange={(event) => {
                    setVerifyReason(
                      event.target.value,
                    );
                  }}
                  maxLength={1000}
                  className={`${INPUT_CLASS} mt-1.5`}
                  placeholder="확인한 공식 근거 또는 메모"
                />
              </label>
            </div>

            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  void verifyDate();
                }}
                disabled={
                  submitting !== null ||
                  !publishedAtInput
                }
                className="inline-flex min-h-10 items-center justify-center rounded-xl border border-cyan/50 px-4 text-sm font-bold text-cyan disabled:opacity-50"
              >
                {submitting === "verify"
                  ? "확인 처리 중"
                  : candidate.verificationStatus ===
                      "DATE_VERIFIED"
                    ? "발행일 수정"
                    : "발행일 확인"}
              </button>
            </div>
          </div>
        ) : null}

        {candidate.verificationStatus ===
        "DATE_VERIFIED" ? (
          <div className="mt-4 rounded-xl border border-green/30 bg-green/5 p-4">
            <h6 className="text-sm font-bold">
              참고자료 등록
            </h6>

            <label className="mt-3 block text-xs font-semibold">
              등록 메모 선택
              <input
                value={promoteReason}
                onChange={(event) => {
                  setPromoteReason(
                    event.target.value,
                  );
                }}
                maxLength={1000}
                className={`${INPUT_CLASS} mt-1.5`}
                placeholder="등록 판단 근거 또는 메모"
              />
            </label>

            <label className="mt-3 flex items-start gap-2 text-xs leading-5 text-secondary">
              <input
                type="checkbox"
                checked={promoteConfirmed}
                onChange={(event) => {
                  setPromoteConfirmed(
                    event.target.checked,
                  );
                }}
                className="mt-1"
              />
              <span>
                발행일과 공식 출처를
                확인했으며 참고자료
                보관함에 등록합니다.
              </span>
            </label>

            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  void promoteCandidate();
                }}
                disabled={
                  submitting !== null ||
                  !promoteConfirmed
                }
                className="inline-flex min-h-10 items-center justify-center rounded-xl bg-green px-4 text-sm font-bold text-background disabled:opacity-50"
              >
                {submitting === "promote"
                  ? "등록 처리 중"
                  : "참고자료 등록"}
              </button>
            </div>
          </div>
        ) : null}

        {!finalStatus ? (
          <div className="mt-4 rounded-xl border border-red/30 bg-red/5 p-4">
            <h6 className="text-sm font-bold">
              검토 제외
            </h6>

            <label className="mt-3 block text-xs font-semibold">
              제외 사유 필수
              <textarea
                value={dismissReason}
                onChange={(event) => {
                  setDismissReason(
                    event.target.value,
                  );
                }}
                maxLength={1000}
                rows={3}
                className={`${INPUT_CLASS} mt-1.5 py-2`}
                placeholder="중복, 출처 부적합, 자료 유형 부적합 등"
              />
            </label>

            <label className="mt-3 flex items-start gap-2 text-xs leading-5 text-secondary">
              <input
                type="checkbox"
                checked={dismissConfirmed}
                onChange={(event) => {
                  setDismissConfirmed(
                    event.target.checked,
                  );
                }}
                className="mt-1"
              />
              <span>
                입력한 사유로 이 후보를
                검토 대상에서 제외합니다.
              </span>
            </label>

            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  void dismissCandidate();
                }}
                disabled={
                  submitting !== null ||
                  !dismissConfirmed ||
                  !dismissReason.trim()
                }
                className="inline-flex min-h-10 items-center justify-center rounded-xl border border-red/50 px-4 text-sm font-bold text-red disabled:opacity-50"
              >
                {submitting === "dismiss"
                  ? "제외 처리 중"
                  : "검토 제외"}
              </button>
            </div>
          </div>
        ) : (
          <p className="mt-4 rounded-xl border border-border bg-surface/60 p-3 text-xs leading-5 text-secondary">
            이 후보는 최종 검토 상태입니다.
            추가 변경은 처리하지 않습니다.
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-border bg-background/70 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h5 className="font-bold">
              검토 이력
            </h5>
            <p className="mt-1 text-xs text-muted">
              {history.length}건
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              setHistoryRefreshKey(
                (current) => current + 1,
              );
            }}
            disabled={historyLoading}
            className="inline-flex min-h-9 items-center justify-center rounded-lg border border-border px-3 text-xs font-bold text-cyan disabled:opacity-50"
          >
            {historyLoading
              ? "확인 중"
              : "이력 새로고침"}
          </button>
        </div>

        {historyError ? (
          <p className="mt-3 rounded-xl border border-red/40 bg-red/10 p-3 text-xs leading-5 text-red">
            {historyError}
          </p>
        ) : null}

        {historyLoading ? (
          <p className="mt-3 text-xs text-muted">
            검토 이력을 불러오는 중입니다.
          </p>
        ) : null}

        {!historyLoading &&
        !historyError &&
        history.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed border-border p-3 text-xs text-muted">
            아직 검토 이력이 없습니다.
          </p>
        ) : null}

        <div className="mt-3 space-y-2">
          {history.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-border bg-surface/60 p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <strong className="text-xs">
                  {ACTION_LABELS[item.action]}
                </strong>
                <span className="text-xs text-muted">
                  {formatDate(item.createdAt)}
                </span>
              </div>

              <p className="mt-2 text-xs text-secondary">
                {item.previousStatus}
                {" → "}
                {item.newStatus}
              </p>

              {item.verifiedPublishedAt ? (
                <p className="mt-1 text-xs text-secondary">
                  확인 발행일:{" "}
                  {formatDate(
                    item.verifiedPublishedAt,
                  )}
                </p>
              ) : null}

              {item.reason ? (
                <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-secondary">
                  {item.reason}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
