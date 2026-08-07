import type { ReactNode } from "react";

function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "cyan" | "green" | "yellow" | "red";
}) {
  const tones = {
    neutral: "border-border bg-surface text-secondary",
    cyan: "border-cyan/40 bg-cyan/10 text-cyan",
    green: "border-green/40 bg-green/10 text-green",
    yellow: "border-yellow/40 bg-yellow/10 text-yellow",
    red: "border-red/40 bg-red/10 text-red",
  };
  return (
    <span className={`inline-flex min-h-7 items-center rounded-full border px-2.5 text-xs font-bold ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function StatusBadge({ children }: { children: ReactNode }) {
  return <Badge>{children}</Badge>;
}

export function TrustBadge({ children }: { children: ReactNode }) {
  return <Badge tone="cyan">{children}</Badge>;
}

export function FreshnessBadge({ children }: { children: ReactNode }) {
  return <Badge tone="green">{children}</Badge>;
}

export function ImpactBadge({ children }: { children: ReactNode }) {
  return <Badge tone="yellow">{children}</Badge>;
}

export function RecommendationBadge({ children }: { children: ReactNode }) {
  return <Badge tone="red">{children}</Badge>;
}

export function SourceGradeBadge({ grade }: { grade: "A" | "B" | "C" | "D" }) {
  const tone = grade === "A" ? "green" : grade === "B" ? "cyan" : "neutral";
  return <Badge tone={tone}>출처 {grade}</Badge>;
}
