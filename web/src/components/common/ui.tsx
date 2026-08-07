import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="mb-6">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-cyan">
        {eyebrow}
      </p>
      <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{title}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary md:text-base">
        {description}
      </p>
    </header>
  );
}

export function Card({
  title,
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-[0_18px_50px_rgba(0,0,0,0.16)]">
      {title ? <h2 className="mb-4 text-base font-bold">{title}</h2> : null}
      {children}
    </section>
  );
}

export function EmptyState({
  title = "표시할 데이터가 없습니다.",
  detail = "수집된 데이터가 없습니다.",
  actionHref,
  actionLabel,
}: {
  title?: string;
  detail?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="grid min-h-[280px] place-items-center rounded-xl border border-dashed border-border bg-surface/60 p-6 text-center">
      <div>
        <div
          aria-hidden="true"
          className="mx-auto mb-4 grid size-11 place-items-center rounded-full border border-border text-cyan"
        >
          —
        </div>
        <p className="font-bold">{title}</p>
        <p className="mt-2 text-sm leading-6 text-secondary">{detail}</p>
        {actionHref && actionLabel ? (
          <Link
            href={actionHref}
            className="mt-5 inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-sm font-bold text-cyan"
          >
            {actionLabel}
          </Link>
        ) : null}
      </div>
    </div>
  );
}

export function DataTimestamp({ value }: { value?: string | null }) {
  return (
    <time className="text-xs text-muted" dateTime={value ?? undefined}>
      기준 시각 {value ?? "--"}
    </time>
  );
}
