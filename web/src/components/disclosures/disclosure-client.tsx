"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { StatusBadge } from "@/components/common/badges";
import { OfficialDisclosureImportDialog } from "@/components/disclosures/official-disclosure-import-dialog";
import { Card, EmptyState } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { getPositionStatusLabel, getTrackingStatusLabel } from "@/lib/display-labels";
import { listDisclosures } from "@/lib/api/news";
import { getSystemInfo } from "@/lib/api/system";
import { lifecycleLabels, verificationLabels } from "@/lib/news";
import type { DisclosureListResponse, SystemInfo } from "@/types/api";

const providerLabels: Record<string, string> = {
  OPENDART: "국내 OpenDART",
  SEC_EDGAR: "미국 SEC",
};

type ChangeFilter = "ALL" | "NEW" | "CORRECTION";

export function DisclosureClient() {
  const [data, setData] = useState<DisclosureListResponse | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [error, setError] = useState("");
  const [provider, setProvider] = useState("");
  const [query, setQuery] = useState("");
  const [formType, setFormType] = useState("");
  const [verification, setVerification] = useState("");
  const [changeFilter, setChangeFilter] = useState<ChangeFilter>("ALL");
  const [publishedFrom, setPublishedFrom] = useState("");
  const [publishedTo, setPublishedTo] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      listDisclosures(controller.signal),
      getSystemInfo(controller.signal),
    ])
      .then(([disclosures, info]) => {
        setData(disclosures);
        setSystem(info);
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "공시를 불러오지 못했습니다.",
        );
      });
    return () => controller.abort();
  }, [refresh]);

  const formTypes = useMemo(
    () =>
      [...new Set((data?.items ?? []).map((item) => item.formType ?? item.reportType))]
        .filter((value): value is string => Boolean(value))
        .sort(),
    [data],
  );

  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return (data?.items ?? []).filter((item) => {
      const related = item.relatedPortfolioItems
        .map((portfolio) => `${portfolio.name} ${portfolio.symbol}`)
        .join(" ");
      const searchable =
        `${item.companyName} ${item.title} ${item.relatedInstrument?.canonicalSymbol ?? ""} ${related}`.toLowerCase();
      const isCorrection =
        Boolean(item.correctionOfId) ||
        item.lifecycleStatus === "CORRECTED" ||
        Boolean(item.formType?.endsWith("/A"));
      const published = item.publishedAt.slice(0, 10);
      return (
        (!provider || item.provider === provider) &&
        (!normalizedQuery || searchable.includes(normalizedQuery)) &&
        (!formType || (item.formType ?? item.reportType) === formType) &&
        (!verification || item.verificationStatus === verification) &&
        (changeFilter === "ALL" ||
          (changeFilter === "NEW" && !isCorrection) ||
          (changeFilter === "CORRECTION" && isCorrection)) &&
        (!publishedFrom || published >= publishedFrom) &&
        (!publishedTo || published <= publishedTo)
      );
    });
  }, [
    changeFilter,
    data,
    formType,
    provider,
    publishedFrom,
    publishedTo,
    query,
    verification,
  ]);

  if (error)
    return (
      <Card>
        <p className="text-red">{error}</p>
      </Card>
    );
  if (!data || !system)
    return (
      <Card>
        <p className="py-16 text-center">불러오는 중…</p>
      </Card>
    );

  if (!data.items.length) {
    const providerFailure = [system.openDartStatus, system.secStatus].some(
      (status) =>
        status === "FAILED" ||
        status === "ERROR" ||
        status === "NETWORK_UNAVAILABLE",
    );
    const title =
      !system.openDartConfigured && !system.secConfigured
        ? "공식 공시 데이터 제공자 미설정"
        : providerFailure
          ? "공식 공시 수집 실패"
          : system.verifiedMappingCount === 0
            ? "공식 회사 연결 미확인"
            : !system.lastProviderSyncAt
              ? "공식 공시 수집 전"
              : "수집 기간에 실제 공시 없음";
    const detail =
      !system.openDartConfigured && !system.secConfigured
        ? "OpenDART 인증키 또는 SEC 연락처가 설정되지 않아 외부 요청을 수행하지 않았습니다."
        : providerFailure
          ? "데이터 제공자 상태에서 네트워크 또는 응답 오류를 확인해 주세요."
          : system.verifiedMappingCount === 0
            ? "공식 종목코드·CIK 검증이 완료된 분석 종목이 없습니다."
            : "검증 연결은 준비됐으며 아직 저장된 공식 공시 정보가 없습니다.";
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setImportOpen(true)}
            className="min-h-11 rounded-xl bg-cyan px-5 text-sm font-bold text-black"
          >
            공식 공시 등록
          </button>
        </div>
        <Card>
          <EmptyState
            title={title}
            detail={detail}
            actionHref="/system"
            actionLabel="설정 상태 보기"
          />
        </Card>
        {importOpen ? (
          <OfficialDisclosureImportDialog
            onClose={() => setImportOpen(false)}
            onCompleted={() => {
              setError("");
              setRefresh((value) => value + 1);
            }}
          />
        ) : null}
      </div>
    );
  }

  const input =
    "min-h-11 rounded-xl border border-border bg-surface px-3 text-sm";

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setImportOpen(true)}
          className="min-h-11 rounded-xl bg-cyan px-5 text-sm font-bold text-black"
        >
          공식 공시 등록
        </button>
      </div>

      <Card title="공시 필터">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm font-semibold">
            데이터 제공자
            <select
              className={`${input} mt-1.5 w-full`}
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              <option value="">전체</option>
              <option value="OPENDART">국내 OpenDART</option>
              <option value="SEC_EDGAR">미국 SEC</option>
            </select>
          </label>
          <label className="text-sm font-semibold">
            종목
            <input
              className={`${input} mt-1.5 w-full`}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="종목명·종목코드"
            />
          </label>
          <label className="text-sm font-semibold">
            서식·공시 종류
            <select
              className={`${input} mt-1.5 w-full`}
              value={formType}
              onChange={(event) => setFormType(event.target.value)}
            >
              <option value="">전체</option>
              {formTypes.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold">
            신규·정정
            <select
              className={`${input} mt-1.5 w-full`}
              value={changeFilter}
              onChange={(event) =>
                setChangeFilter(event.target.value as ChangeFilter)
              }
            >
              <option value="ALL">전체</option>
              <option value="NEW">신규·업데이트</option>
              <option value="CORRECTION">정정 공시</option>
            </select>
          </label>
          <label className="text-sm font-semibold">
            검증 상태
            <select
              className={`${input} mt-1.5 w-full`}
              value={verification}
              onChange={(event) => setVerification(event.target.value)}
            >
              <option value="">전체</option>
              {Object.entries(verificationLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold">
            시작일
            <input
              type="date"
              className={`${input} mt-1.5 w-full`}
              value={publishedFrom}
              onChange={(event) => setPublishedFrom(event.target.value)}
            />
          </label>
          <label className="text-sm font-semibold">
            종료일
            <input
              type="date"
              className={`${input} mt-1.5 w-full`}
              value={publishedTo}
              onChange={(event) => setPublishedTo(event.target.value)}
            />
          </label>
        </div>
      </Card>

      {visibleItems.length ? (
        <div className="grid gap-4">
          {visibleItems.map((item) => {
            const amendment = Boolean(item.formType?.endsWith("/A"));
            return (
              <article
                key={item.id}
                className="rounded-2xl border border-border bg-card p-5"
              >
                <div className="flex flex-wrap gap-2">
                  <StatusBadge>
                    {providerLabels[item.provider] ?? "공식 공시"}
                  </StatusBadge>
                  <StatusBadge>
                    {verificationLabels[item.verificationStatus]}
                  </StatusBadge>
                  <StatusBadge>출처 등급 {item.sourceGrade}</StatusBadge>
                  <StatusBadge>
                    {amendment
                      ? "정정 공시"
                      : lifecycleLabels[item.lifecycleStatus]}
                  </StatusBadge>
                  <StatusBadge>
                    {item.materialChange ? "핵심 사건 후보" : "참고 공시"}
                  </StatusBadge>
                </div>
                <p className="mt-4 text-xs font-semibold text-cyan">
                  {item.companyName}
                </p>
                <h2 className="mt-1 line-clamp-3 break-words text-lg font-bold">
                  {item.title}
                </h2>
                <p className="mt-2 text-xs text-muted">
                  {item.formType ?? item.reportType ?? "공시"} ·{" "}
                  {new Intl.DateTimeFormat("ko-KR", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(item.publishedAt))}
                </p>
                {item.relatedPortfolioItems.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.relatedPortfolioItems.map((portfolio) => (
                      <Link
                        key={portfolio.id}
                        href={`/portfolio/${portfolio.id}`}
                        className="rounded-full border border-cyan/30 px-2.5 py-1 text-xs text-cyan"
                      >
                        {portfolio.name} ·{" "}
                        {getPositionStatusLabel(portfolio.positionStatus)}
                        {portfolio.trackingStatus !== "NONE"
                          ? ` · ${getTrackingStatusLabel(portfolio.trackingStatus)}`
                          : ""}
                      </Link>
                    ))}
                  </div>
                ) : null}
                <p className="mt-4 text-sm leading-6 text-secondary">
                  {item.summary ??
                    "공식 공시 정보만 확인됐습니다. 세부 내용과 투자 영향은 공식 원문에서 별도로 확인해 주세요."}
                </p>
                <div className="mt-5 flex flex-wrap gap-4 text-sm font-bold">
                  <a
                    href={item.officialUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-green"
                  >
                    공식 원문 보기 ↗
                  </a>
                  <Link
                    href={`/events/${item.eventId}`}
                    className="text-secondary"
                  >
                    연결 사건 보기
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState
            title="필터 조건에 맞는 공식 공시 없음"
            detail="데이터 제공자·종목·서식·검증 상태 또는 기간 조건을 조정해 주세요."
          />
        </Card>
      )}

      {importOpen ? (
        <OfficialDisclosureImportDialog
          onClose={() => setImportOpen(false)}
          onCompleted={() => {
            setError("");
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </div>
  );
}
