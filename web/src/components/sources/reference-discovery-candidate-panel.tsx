"use client";

import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  getReferenceDiscoveryCandidate,
  listReferenceDiscoveryCandidates,
  listReferenceSubscriptions,
  listReferenceSubscriptionSources,
} from "@/lib/api/analyst-references";
import { ReferenceDiscoveryCandidateReviewControls } from "@/components/sources/reference-discovery-candidate-review-controls";
import {
  ApiClientError,
} from "@/lib/api/client";
import {
  collectPaginatedItems,
  nextOffset,
  normalizeOffset,
  paginationSummary,
  previousOffset,
  resetOffset,
  selectionForPage,
} from "@/lib/pagination";
import type {
  ReferenceDiscoveryCandidate,
  ReferenceDiscoveryCandidateStatus,
  ReferenceSubscription,
  ReferenceSubscriptionSource,
} from "@/types/api";

const INPUT_CLASS =
  "min-h-10 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition focus:border-cyan";

const CANDIDATE_PAGE_SIZE = 50;
const OPTION_PAGE_SIZE = 50;

const STATUS_LABELS: Record<
  ReferenceDiscoveryCandidateStatus,
  string
> = {
  DATE_UNVERIFIED: "날짜 미확인",
  DATE_VERIFIED: "날짜 확인",
  PROMOTED: "참고자료 등록",
  DISMISSED: "검토 제외",
};

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

function errorMessage(
  error: unknown,
): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "자료를 불러오지 못했습니다.";
}

function statusClass(
  status: ReferenceDiscoveryCandidateStatus,
): string {
  if (status === "DATE_VERIFIED") {
    return "border-cyan/40 bg-cyan/10 text-cyan";
  }

  if (status === "PROMOTED") {
    return "border-green/40 bg-green/10 text-green";
  }

  if (status === "DISMISSED") {
    return "border-red/40 bg-red/10 text-red";
  }

  return "border-gold/40 bg-gold/10 text-gold";
}

export function ReferenceDiscoveryCandidatePanel() {
  const [
    items,
    setItems,
  ] = useState<
    ReferenceDiscoveryCandidate[]
  >([]);
  const [
    total,
    setTotal,
  ] = useState(0);
  const [
    offset,
    setOffset,
  ] = useState(0);
  const [
    sources,
    setSources,
  ] = useState<
    ReferenceSubscriptionSource[]
  >([]);
  const [
    subscriptions,
    setSubscriptions,
  ] = useState<
    ReferenceSubscription[]
  >([]);

  const [
    loading,
    setLoading,
  ] = useState(true);
  const [
    error,
    setError,
  ] = useState<string | null>(null);
  const [
    optionError,
    setOptionError,
  ] = useState<string | null>(null);

  const [
    queryDraft,
    setQueryDraft,
  ] = useState("");
  const [
    appliedQuery,
    setAppliedQuery,
  ] = useState("");
  const [
    sourceId,
    setSourceId,
  ] = useState("");
  const [
    subscriptionId,
    setSubscriptionId,
  ] = useState("");
  const [
    verificationStatus,
    setVerificationStatus,
  ] = useState<
    ReferenceDiscoveryCandidateStatus | ""
  >("DATE_UNVERIFIED");
  const [
    refreshKey,
    setRefreshKey,
  ] = useState(0);

  const [
    selectedId,
    setSelectedId,
  ] = useState<string | null>(null);
  const [
    detail,
    setDetail,
  ] = useState<
    ReferenceDiscoveryCandidate | null
  >(null);
  const [
    detailLoading,
    setDetailLoading,
  ] = useState(false);
  const [
    detailError,
    setDetailError,
  ] = useState<string | null>(null);
  const [
    copiedId,
    setCopiedId,
  ] = useState<string | null>(null);

  const availableSubscriptions = useMemo(
    () =>
      sourceId
        ? subscriptions.filter(
            (subscription) =>
              subscription.source.id === sourceId,
          )
        : subscriptions,
    [
      sourceId,
      subscriptions,
    ],
  );

  useEffect(() => {
    const controller = new AbortController();

    async function loadOptions() {
      try {
        const [
          sourceResponse,
          subscriptionResponse,
        ] = await Promise.all([
          collectPaginatedItems(
            listReferenceSubscriptionSources,
            {
              pageSize: OPTION_PAGE_SIZE,
              signal: controller.signal,
            },
          ),
          collectPaginatedItems(
            listReferenceSubscriptions,
            {
              pageSize: OPTION_PAGE_SIZE,
              signal: controller.signal,
            },
          ),
        ]);

        setSources(sourceResponse);
        setSubscriptions(subscriptionResponse);
        setOptionError(null);
      } catch (caught) {
        if (controller.signal.aborted) {
          return;
        }

        if (
          caught instanceof ApiClientError &&
          caught.kind === "cancelled"
        ) {
          return;
        }

        setOptionError(
          errorMessage(caught),
        );
      }
    }

    void loadOptions();

    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadCandidates() {
      setLoading(true);
      setError(null);

      try {
        const response =
          await listReferenceDiscoveryCandidates(
            {
              sourceId:
                sourceId || undefined,
              subscriptionId:
                subscriptionId || undefined,
              verificationStatus,
              query: appliedQuery,
              limit: CANDIDATE_PAGE_SIZE,
              offset,
            },
            controller.signal,
          );

        const validOffset = normalizeOffset(
          response.total,
          CANDIDATE_PAGE_SIZE,
          offset,
        );

        if (validOffset !== offset) {
          setTotal(response.total);
          setOffset(validOffset);
          return;
        }

        setItems(response.items);
        setTotal(response.total);
        setSelectedId((current) =>
          selectionForPage(
            current,
            response.items,
          ),
        );
        setDetail((current) =>
          current &&
          selectionForPage(
            current.id,
            response.items,
          ) === null
            ? null
            : current,
        );
      } catch (caught) {
        if (
          caught instanceof ApiClientError &&
          caught.kind === "cancelled"
        ) {
          return;
        }

        setItems([]);
        setTotal(0);
        setError(
          errorMessage(caught),
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadCandidates();

    return () => {
      controller.abort();
    };
  }, [
    appliedQuery,
    offset,
    refreshKey,
    sourceId,
    subscriptionId,
    verificationStatus,
  ]);

  useEffect(() => {
    if (!selectedId) {
      return;
    }

    const candidateId = selectedId;
    const controller = new AbortController();

    async function loadDetail() {
      setDetailLoading(true);
      setDetailError(null);

      try {
        const response =
          await getReferenceDiscoveryCandidate(
            candidateId,
            controller.signal,
          );

        setDetail(response);
      } catch (caught) {
        if (
          caught instanceof ApiClientError &&
          caught.kind === "cancelled"
        ) {
          return;
        }

        setDetail(null);
        setDetailError(
          errorMessage(caught),
        );
      } finally {
        if (!controller.signal.aborted) {
          setDetailLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      controller.abort();
    };
  }, [
    refreshKey,
    selectedId,
  ]);

  function applySearch(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setOffset(resetOffset());
    setSelectedId(null);
    setAppliedQuery(
      queryDraft.trim(),
    );
  }

  function resetFilters() {
    setQueryDraft("");
    setAppliedQuery("");
    setSourceId("");
    setSubscriptionId("");
    setVerificationStatus(
      "DATE_UNVERIFIED",
    );
    setOffset(resetOffset());
    setSelectedId(null);
  }

  const page = paginationSummary(
    total,
    CANDIDATE_PAGE_SIZE,
    offset,
    items.length,
  );

  async function copyCanonicalUrl(
    candidate: ReferenceDiscoveryCandidate,
  ) {
    try {
      await navigator.clipboard.writeText(
        candidate.canonicalUrl,
      );
      setCopiedId(candidate.id);

      window.setTimeout(() => {
        setCopiedId((current) =>
          current === candidate.id
            ? null
            : current,
        );
      }, 1500);
    } catch {
      setDetailError(
        "공식 링크를 복사하지 못했습니다.",
      );
    }
  }

  function handleCandidateReviewed(
    candidate: ReferenceDiscoveryCandidate,
  ) {
    setDetail(candidate);
    setRefreshKey(
      (current) => current + 1,
    );
  }

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-[0_18px_50px_rgba(0,0,0,0.16)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-bold">
              검토 대기 자료
            </h2>

            <span className="rounded-full border border-gold/40 bg-gold/10 px-2.5 py-1 text-xs font-bold text-gold">
              {total}건
            </span>
          </div>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary">
            공식 인덱스에서 발견됐지만 발행일이
            확인되지 않은 자료입니다. 승인 전까지
            참고자료 보관함과 투자 판단 계산에서
            격리됩니다.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setRefreshKey(
              (current) => current + 1,
            );
          }}
          disabled={loading}
          className="inline-flex min-h-10 items-center justify-center rounded-xl border border-border px-4 text-sm font-bold text-cyan hover:border-cyan/50 disabled:opacity-50"
        >
          {loading
            ? "확인 중"
            : "새로고침"}
        </button>
      </div>

      <form
        onSubmit={applySearch}
        className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        <label className="block text-sm font-semibold">
          제목·전문가·도메인 검색
          <input
            value={queryDraft}
            onChange={(event) => {
              setQueryDraft(
                event.target.value,
              );
            }}
            className={`${INPUT_CLASS} mt-1.5`}
            placeholder="제목 또는 전문가명"
          />
        </label>

        <label className="block text-sm font-semibold">
          공식 출처
          <select
            value={sourceId}
            onChange={(event) => {
              setSourceId(
                event.target.value,
              );
              setSubscriptionId("");
              setOffset(resetOffset());
              setSelectedId(null);
            }}
            className={`${INPUT_CLASS} mt-1.5`}
          >
            <option value="">
              전체 출처
            </option>

            {sources.map((source) => (
              <option
                key={source.id}
                value={source.id}
              >
                {source.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-semibold">
          자동 구독
          <select
            value={subscriptionId}
            onChange={(event) => {
              setSubscriptionId(
                event.target.value,
              );
              setOffset(resetOffset());
              setSelectedId(null);
            }}
            className={`${INPUT_CLASS} mt-1.5`}
          >
            <option value="">
              전체 구독
            </option>

            {availableSubscriptions.map(
              (subscription) => (
                <option
                  key={subscription.id}
                  value={subscription.id}
                >
                  {subscription.displayName}
                </option>
              ),
            )}
          </select>
        </label>

        <label className="block text-sm font-semibold">
          검토 상태
          <select
            value={verificationStatus}
            onChange={(event) => {
              setVerificationStatus(
                event.target.value as
                  | ReferenceDiscoveryCandidateStatus
                  | "",
              );
              setOffset(resetOffset());
              setSelectedId(null);
            }}
            className={`${INPUT_CLASS} mt-1.5`}
          >
            <option value="">
              전체 상태
            </option>
            <option value="DATE_UNVERIFIED">
              날짜 미확인
            </option>
            <option value="DATE_VERIFIED">
              날짜 확인
            </option>
            <option value="PROMOTED">
              참고자료 등록
            </option>
            <option value="DISMISSED">
              검토 제외
            </option>
          </select>
        </label>

        <div className="flex flex-col gap-2 sm:col-span-2 sm:flex-row lg:col-span-4 lg:justify-end">
          <button
            type="button"
            onClick={resetFilters}
            className="min-h-10 rounded-xl border border-border px-4 text-sm font-semibold"
          >
            필터 초기화
          </button>

          <button
            type="submit"
            className="min-h-10 rounded-xl bg-cyan px-4 text-sm font-bold text-background"
          >
            검색 적용
          </button>
        </div>
      </form>

      {optionError ? (
        <p className="mt-4 rounded-xl border border-gold/30 bg-gold/5 p-3 text-xs leading-5 text-secondary">
          필터 목록을 불러오지 못했습니다. 후보
          목록 조회는 계속 사용할 수 있습니다.
          {" "}
          {optionError}
        </p>
      ) : null}

      {error ? (
        <p className="mt-4 rounded-xl border border-red/40 bg-red/10 p-4 text-sm leading-6 text-red">
          {error}
        </p>
      ) : null}

      <div className="mt-5 space-y-4">
        {loading ? (
          <p className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-muted">
            검토 대기 자료를 불러오는 중입니다.
          </p>
        ) : null}

        {!loading &&
        !error &&
        items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/60 p-5">
            <p className="font-semibold">
              조건에 맞는 검토 대기 자료가 없습니다.
            </p>
            <p className="mt-2 text-xs leading-5 text-muted">
              현재 실환경에서 후보가 0건이면 정상적인
              빈 상태로 표시됩니다.
            </p>
          </div>
        ) : null}

        {items.map((candidate) => {
          const selected =
            selectedId === candidate.id;
          const shownDetail =
            selected &&
            detail?.id === candidate.id
              ? detail
              : candidate;

          return (
            <article
              key={candidate.id}
              className="rounded-2xl border border-border bg-surface/60 p-4"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-bold leading-6">
                      {candidate.title}
                    </h3>

                    <span
                      className={`rounded-full border px-2.5 py-1 text-xs font-bold ${statusClass(candidate.verificationStatus)}`}
                    >
                      {
                        STATUS_LABELS[
                          candidate
                            .verificationStatus
                        ]
                      }
                    </span>
                  </div>

                  <p className="mt-2 text-sm text-secondary">
                    {candidate.analystName ??
                      "전문가명 미확인"}
                    {" · "}
                    {candidate.source.name}
                  </p>

                  <p className="mt-1 break-all text-xs text-muted">
                    {candidate.source.domain}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(
                      selected
                        ? null
                        : candidate.id,
                    );
                  }}
                  className="inline-flex min-h-9 shrink-0 items-center justify-center rounded-lg border border-border px-3 text-xs font-bold text-cyan hover:border-cyan/50"
                >
                  {selected
                    ? "상세 닫기"
                    : "상세 보기"}
                </button>
              </div>

              <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted">
                    자동 구독
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {
                      candidate.subscription
                        .displayName
                    }
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    발행일
                  </dt>
                  <dd className="mt-1 font-semibold text-gold">
                    {candidate.publishedAt
                      ? formatDate(
                          candidate.publishedAt,
                        )
                      : "날짜 미확인"}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    마지막 발견
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {formatDate(
                      candidate.lastSeenAt,
                    )}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    발견 횟수
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {candidate.seenCount}회
                  </dd>
                </div>
              </dl>

              {selected ? (
                <div className="mt-5 rounded-2xl border border-cyan/30 bg-cyan/5 p-4">
                  {detailLoading ? (
                    <p className="text-sm text-muted">
                      상세 정보를 불러오는 중입니다.
                    </p>
                  ) : null}

                  {detailError ? (
                    <p className="rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red">
                      {detailError}
                    </p>
                  ) : null}

                  {!detailLoading ? (
                    <>
                      <h4 className="font-bold">
                        후보 상세 정보
                      </h4>

                      <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
                        <div>
                          <dt className="text-xs text-muted">
                            최초 발견
                          </dt>
                          <dd className="mt-1 font-semibold">
                            {formatDate(
                              shownDetail
                                .firstSeenAt,
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs text-muted">
                            마지막 발견
                          </dt>
                          <dd className="mt-1 font-semibold">
                            {formatDate(
                              shownDetail
                                .lastSeenAt,
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs text-muted">
                            출처 등급
                          </dt>
                          <dd className="mt-1 font-semibold">
                            {
                              shownDetail
                                .source
                                .sourceGrade
                            }
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs text-muted">
                            출처 활성 상태
                          </dt>
                          <dd className="mt-1 font-semibold">
                            {shownDetail.source.enabled
                              ? "활성"
                              : "중지"}
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs text-muted">
                            구독 활성 상태
                          </dt>
                          <dd className="mt-1 font-semibold">
                            {
                              shownDetail
                                .subscription
                                .enabled
                                ? "활성"
                                : "중지"
                            }
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs text-muted">
                            Provider Item ID
                          </dt>
                          <dd className="mt-1 break-all font-semibold">
                            {
                              shownDetail
                                .providerItemId
                            }
                          </dd>
                        </div>

                        <div className="sm:col-span-2 lg:col-span-3">
                          <dt className="text-xs text-muted">
                            공식 링크
                          </dt>
                          <dd className="mt-1 break-all font-semibold">
                            {
                              shownDetail
                                .canonicalUrl
                            }
                          </dd>
                        </div>
                      </dl>

                      <div className="mt-4 flex justify-end">
                        <button
                          type="button"
                          onClick={() => {
                            void copyCanonicalUrl(
                              shownDetail,
                            );
                          }}
                          className="inline-flex min-h-9 items-center justify-center rounded-lg border border-border px-3 text-xs font-bold text-cyan hover:border-cyan/50"
                        >
                          {copiedId ===
                          shownDetail.id
                            ? "링크 복사 완료"
                            : "공식 링크 복사"}
                        </button>
                      </div>

                      <ReferenceDiscoveryCandidateReviewControls
                        key={`${shownDetail.id}:${shownDetail.updatedAt}`}
                        candidate={shownDetail}
                        onReviewed={
                          handleCandidateReviewed
                        }
                      />
                    </>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      <nav
        aria-label="후보 목록 페이지 이동"
        className="mt-5 flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface/60 p-3"
      >
        <p
          aria-live="polite"
          className="min-w-0 break-words text-xs leading-5 text-secondary"
        >
          {page.start}-{page.end}건 표시
          {" / "}
          전체 {total}건
          {" · "}
          {page.page}/{page.pageCount}페이지
        </p>

        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <button
            type="button"
            aria-label="이전 후보 페이지"
            onClick={() => {
              if (!loading) {
                setOffset(
                  previousOffset(
                    offset,
                    CANDIDATE_PAGE_SIZE,
                  ),
                );
              }
            }}
            disabled={
              loading || !page.hasPrevious
            }
            className="min-h-10 flex-1 rounded-xl border border-border px-4 text-sm font-bold text-cyan disabled:opacity-50 sm:flex-none"
          >
            이전 페이지
          </button>

          <button
            type="button"
            aria-label="다음 후보 페이지"
            onClick={() => {
              if (!loading) {
                setOffset(
                  nextOffset(
                    total,
                    CANDIDATE_PAGE_SIZE,
                    offset,
                  ),
                );
              }
            }}
            disabled={
              loading || !page.hasNext
            }
            className="min-h-10 flex-1 rounded-xl border border-border px-4 text-sm font-bold text-cyan disabled:opacity-50 sm:flex-none"
          >
            다음 페이지
          </button>
        </div>
      </nav>
    </section>
  );
}
