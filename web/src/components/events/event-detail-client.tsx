"use client";

import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/common/badges";
import { Card } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { getEvent } from "@/lib/api/news";
import { lifecycleLabels, verificationLabels } from "@/lib/news";
import type { InformationEvent } from "@/types/api";

function time(value: string | null) {
  if (!value) return "--";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function canonicalUrl(value: string) {
  const url = new URL(value);
  url.hash = "";
  [...url.searchParams.keys()].forEach((key) => {
    if (
      key.toLowerCase().startsWith("utm_") ||
      ["fbclid", "gclid", "ref", "source"].includes(key.toLowerCase())
    ) {
      url.searchParams.delete(key);
    }
  });
  url.searchParams.sort();
  return url.toString();
}

export function EventDetailClient({ id }: { id: string }) {
  const [event, setEvent] = useState<InformationEvent | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getEvent(id, controller.signal)
      .then(setEvent)
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "사건 상세를 불러오지 못했습니다.",
        );
      });
    return () => controller.abort();
  }, [id]);

  if (error) return <Card><p className="text-red">{error}</p></Card>;
  if (!event) return <Card><p className="py-16 text-center">불러오는 중…</p></Card>;

  const timelineItems = [
    ...(event.newsReferences ?? []).map((news) => ({
      key: `news-${news.id}`,
      at: news.publishedAt,
      title: news.title,
      detail: news.staleReused
        ? "동일 내용 재보도, 새로운 사실 없음"
        : news.materialChange
          ? "새로운 사실이 포함된 뉴스 참조"
          : "최초 또는 추가 보도",
      url: news.canonicalUrl,
      external: true,
    })),
    ...(event.officialReferences ?? []).map((disclosure) => ({
      key: `official-${disclosure.id}`,
      at: disclosure.publishedAt,
      title: disclosure.title,
      detail: "공식 공시 확인",
      url: disclosure.officialUrl,
      external: true,
    })),
  ].sort((left, right) => left.at.localeCompare(right.at));
  const timeline = Array.from(
    new Map(
      timelineItems.map((item) => [
        item.url ? canonicalUrl(item.url) : item.key,
        item,
      ]),
    ).values(),
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <Card title="사건 타임라인">
        <div className="mb-5 flex flex-wrap gap-2">
          <StatusBadge>{lifecycleLabels[event.lifecycleStatus]}</StatusBadge>
          <StatusBadge>{verificationLabels[event.verificationStatus]}</StatusBadge>
        </div>
        <h2 className="line-clamp-3 break-words text-xl font-bold">
          {event.normalizedClaim}
        </h2>
        <div className="mt-6 space-y-4 border-l border-border pl-5">
          {timeline.map((item) => (
            <article key={item.key} className="relative rounded-xl border border-border bg-surface p-4">
              <span className="absolute -left-[1.7rem] top-5 size-3 rounded-full bg-cyan" />
              <time className="text-xs text-muted">{time(item.at)}</time>
              <h3 className="mt-1 line-clamp-2 break-words font-bold">
                {item.title}
              </h3>
              <p className="mt-1 text-sm text-secondary">{item.detail}</p>
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-block text-sm font-bold text-cyan"
              >
                원문 보기 ↗
              </a>
            </article>
          ))}
        </div>
      </Card>
      <Card title="사건 상태">
        <dl className="space-y-3 text-sm">
          <div><dt className="text-muted">관련 종목</dt><dd className="font-bold">{event.relatedInstrument?.displayName ?? "--"}</dd></div>
          <div><dt className="text-muted">최초 발견</dt><dd>{time(event.firstSeenAt)}</dd></div>
          <div><dt className="text-muted">마지막 확인</dt><dd>{time(event.lastSeenAt)}</dd></div>
          <div><dt className="text-muted">최신 중요 변경</dt><dd>{time(event.latestMaterialChangeAt)}</dd></div>
          <div><dt className="text-muted">공식 자료</dt><dd>{event.officialSourceCount}</dd></div>
          <div><dt className="text-muted">독립 원출처</dt><dd>{event.independentOriginCount}</dd></div>
          <div><dt className="text-muted">재탕 기사</dt><dd>{event.staleReuseCount}</dd></div>
        </dl>
        {event.changedFacts.length ? (
          <div className="mt-5 border-t border-border pt-4">
            <p className="text-xs font-semibold text-muted">새롭게 변경된 사실</p>
            <pre className="mt-2 overflow-auto text-xs">{JSON.stringify(event.changedFacts, null, 2)}</pre>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
