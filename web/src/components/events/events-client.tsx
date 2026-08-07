"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/common/badges";
import { Card, EmptyState } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { listEvents } from "@/lib/api/news";
import { lifecycleLabels, verificationLabels } from "@/lib/news";
import type { EventListResponse } from "@/types/api";

export function EventsClient() {
  const [data, setData] = useState<EventListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    listEvents(controller.signal)
      .then(setData)
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "사건을 불러오지 못했습니다.",
        );
      });
    return () => controller.abort();
  }, []);

  if (error) return <Card><p className="text-red">{error}</p></Card>;
  if (!data) return <Card><p className="py-16 text-center">불러오는 중…</p></Card>;
  if (!data.items.length) return <Card><EmptyState title="통합 사건 없음" detail="뉴스와 공시가 수집되면 같은 사건별로 통합합니다." actionHref="/sources" actionLabel="출처 설정 보기" /></Card>;
  return (
    <div className="grid gap-4">
      {data.items.map((event) => (
        <Link
          key={event.id}
          href={`/events/${event.id}`}
          className="rounded-2xl border border-border bg-card p-5 hover:border-cyan/40"
        >
          <div className="flex flex-wrap gap-2">
            <StatusBadge>{lifecycleLabels[event.lifecycleStatus]}</StatusBadge>
            <StatusBadge>{verificationLabels[event.verificationStatus]}</StatusBadge>
          </div>
          <h2 className="mt-4 line-clamp-3 break-words text-lg font-bold">{event.normalizedClaim}</h2>
          <dl className="mt-4 grid gap-2 text-sm text-secondary sm:grid-cols-3">
            {event.newsReferenceCount ? <div><dt>뉴스 참조</dt><dd className="font-bold text-foreground">{event.newsReferenceCount}</dd></div> : null}
            {event.independentOriginCount ? <div><dt>독립 원출처</dt><dd className="font-bold text-foreground">{event.independentOriginCount}</dd></div> : null}
            <div><dt>공식 자료</dt><dd className="font-bold text-foreground">{event.officialSourceCount}</dd></div>
          </dl>
        </Link>
      ))}
    </div>
  );
}
