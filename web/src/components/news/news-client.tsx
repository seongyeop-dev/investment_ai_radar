"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { SourceGradeBadge, StatusBadge, TrustBadge } from "@/components/common/badges";
import { Card, EmptyState } from "@/components/common/ui";
import { ImportantInformationImportDialog } from "@/components/news/important-information-import-dialog";
import { ApiClientError } from "@/lib/api/client";
import { listNews } from "@/lib/api/news";
import {
  certaintyLabels,
  TRUST_SCORE_EXPLANATION,
  verificationLabels,
} from "@/lib/news";
import type {
  NewsListResponse,
  SourceGrade,
  VerificationStatus,
} from "@/types/api";

function time(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function NewsClient() {
  const [data, setData] = useState<NewsListResponse | null>(null);
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState<SourceGrade | "">("");
  const [verification, setVerification] = useState<VerificationStatus | "">("");
  const [materialOnly, setMaterialOnly] = useState(false);
  const [includeReused, setIncludeReused] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [importOpen, setImportOpen] = useState(false);

  const load = useCallback(
    (signal: AbortSignal) => {
      listNews(
        {
          query,
          sourceGrade: grade,
          verificationStatus: verification,
          materialChange: materialOnly ? true : undefined,
          staleReused: includeReused ? undefined : false,
          limit: 100,
        },
        signal,
      )
        .then(setData)
        .catch((reason: unknown) => {
          if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
          setError(
            reason instanceof ApiClientError
              ? reason.message
              : "뉴스 참조를 불러오지 못했습니다.",
          );
        })
        .finally(() => {
          if (!signal.aborted) setLoading(false);
        });
    },
    [grade, includeReused, materialOnly, query, verification],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, refresh]);

  const changed = data?.items.filter((item) => item.materialChange).length ?? 0;
  const reused = data?.items.filter((item) => item.staleReused).length ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setImportOpen(true)}
          className="min-h-11 rounded-xl bg-cyan px-5 text-sm font-bold text-background"
        >
          중요 정보 등록
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ["표시 기사", data?.total ?? 0],
          ["새 사실", changed],
          ["재탕·중복", reused],
        ].map(([label, value]) => (
          <Card key={label}>
            <p className="text-xs font-semibold text-muted">{label}</p>
            <p className="mt-2 text-2xl font-bold">{value}</p>
          </Card>
        ))}
      </div>

      <Card title="필터">
        <div className="grid gap-3 md:grid-cols-3">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="기사·주장·출처 검색"
            className="min-h-11 rounded-xl border border-border bg-surface px-3 text-sm"
          />
          <select
            value={grade}
            onChange={(event) => setGrade(event.target.value as SourceGrade | "")}
            className="min-h-11 rounded-xl border border-border bg-surface px-3 text-sm"
          >
            <option value="">모든 출처 등급</option>
            {["A", "B", "C", "D"].map((value) => (
              <option key={value} value={value}>출처 {value}</option>
            ))}
          </select>
          <select
            value={verification}
            onChange={(event) =>
              setVerification(event.target.value as VerificationStatus | "")
            }
            className="min-h-11 rounded-xl border border-border bg-surface px-3 text-sm"
          >
            <option value="">모든 검증 상태</option>
            {Object.entries(verificationLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={materialOnly}
              onChange={(event) => setMaterialOnly(event.target.checked)}
            />
            중요 변경만 보기
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeReused}
              onChange={(event) => setIncludeReused(event.target.checked)}
            />
            재탕·중복 포함
          </label>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              setError("");
              setRefresh((value) => value + 1);
            }}
            className="min-h-10 rounded-lg border border-cyan/40 px-4 font-bold text-cyan"
          >
            새로고침
          </button>
        </div>
      </Card>

      {loading ? (
        <Card><p className="py-16 text-center text-secondary">불러오는 중…</p></Card>
      ) : error ? (
        <Card>
          <div role="alert" className="rounded-xl border border-red/40 bg-red/10 p-5">
            <p className="font-semibold text-red">{error}</p>
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                setError("");
                setRefresh((value) => value + 1);
              }}
              className="mt-4 min-h-10 rounded-lg border border-red/40 px-4 font-bold text-red"
            >
              다시 시도
            </button>
          </div>
        </Card>
      ) : data?.items.length ? (
        <div className="grid gap-4">
          {data.items.map((item) => (
            <article key={item.id} className="rounded-2xl border border-border bg-card p-5">
              <div className="flex flex-wrap gap-2">
                <SourceGradeBadge grade={item.sourceGrade} />
                <StatusBadge>{verificationLabels[item.verificationStatus]}</StatusBadge>
                <StatusBadge>{certaintyLabels[item.certaintyLevel]}</StatusBadge>
                {item.materialChange ? <StatusBadge>새 사실</StatusBadge> : null}
                {item.staleReused ? <StatusBadge>재탕·중복</StatusBadge> : null}
              </div>
              <p className="mt-4 text-xs font-semibold text-cyan">
                {item.relatedInstrument?.canonicalSymbol ?? "연결 종목"} ·{" "}
                {item.relatedInstrument?.displayName ?? "종목 정보"}
              </p>
              <h2 className="mt-1 text-lg font-bold leading-7">{item.title}</h2>
              <p className="mt-2 text-xs text-muted">
                {item.sourceName} · {time(item.publishedAt)}
              </p>
              <p className="mt-4 max-h-24 overflow-hidden text-sm leading-6 text-secondary">
                {item.shortSummary}
              </p>
              <div className="mt-4 rounded-xl border border-border bg-surface p-4">
                <p className="text-xs font-semibold text-muted">핵심 주장</p>
                <p className="mt-1 text-sm leading-6">{item.primaryClaim}</p>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <TrustBadge>증거 강도 {item.trustScore}/100</TrustBadge>
                <span className="text-xs text-muted">{TRUST_SCORE_EXPLANATION}</span>
              </div>
              <div className="mt-5 flex flex-wrap gap-3 text-sm font-bold">
                <a
                  href={item.originalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan"
                >
                  원문 보기 (외부 사이트) ↗
                </a>
                {item.officialReferences.map((reference) => (
                  <a
                    key={reference.id}
                    href={reference.officialUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-green"
                  >
                    공식 자료 보기 ↗
                  </a>
                ))}
                <Link href={`/events/${item.informationEventId}`} className="text-secondary">
                  사건 상세 보기
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            title="뉴스 참조 없음"
            detail="웹에서 중요 정보를 등록하거나 뉴스 수집 출처를 설정해 주세요."
            actionHref="/sources"
            actionLabel="출처 설정 보기"
          />
        </Card>
      )}

      {importOpen ? (
        <ImportantInformationImportDialog
          onClose={() => setImportOpen(false)}
          onCompleted={() => {
            setLoading(true);
            setError("");
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </div>
  );
}
