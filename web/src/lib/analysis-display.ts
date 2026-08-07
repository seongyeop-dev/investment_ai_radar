import type {
  AnalysisConfidence,
  DecisionDirection,
  PortfolioImpact,
  ThesisStatus,
} from "@/types/api";

export const directionLabels: Record<DecisionDirection, string> = {
  ADD_REVIEW: "추가매수 검토",
  HOLD: "유지",
  WAIT: "관망",
  REDUCE_REVIEW: "비중축소 검토",
  EXIT_REVIEW: "손절·청산 검토",
  INSUFFICIENT_DATA: "데이터 부족",
};

export const confidenceLabels: Record<AnalysisConfidence, string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

export const thesisStatusLabels: Record<ThesisStatus, string> = {
  NOT_SET: "분석 자료 없음",
  ACTIVE: "기존 근거 유지",
  STRENGTHENED: "투자근거 강화",
  WEAKENED: "투자근거 약화",
  PARTIALLY_BROKEN: "일부 근거 훼손",
  BROKEN: "핵심 근거 훼손",
  REVIEW_REQUIRED: "재검토 필요",
};

const displayableVerification = new Set([
  "OFFICIAL_CONFIRMED",
  "MULTI_SOURCE_CONFIRMED",
  "CORRECTED",
  "OFFICIALLY_DENIED",
  "CONFLICTING",
]);

const reviewVerification = new Set([
  "CORRECTED",
  "OFFICIALLY_DENIED",
  "CONFLICTING",
]);

export function hasDisplayEvidence(impact: PortfolioImpact): boolean {
  return (
    displayableVerification.has(impact.verificationStatus) &&
    impact.verificationStatus !== "STALE_REUSED" &&
    impact.sourceLinks.length > 0
  );
}

export function selectEvidence(
  impacts: PortfolioImpact[],
  kind: "positive" | "negative",
): PortfolioImpact[] {
  const direction = kind === "positive" ? "POSITIVE" : "NEGATIVE";
  const seen = new Set<string>();
  return impacts
    .filter(
      (impact) =>
        impact.impactDirection === direction &&
        hasDisplayEvidence(impact) &&
        !seen.has(impact.eventId),
    )
    .filter((impact) => {
      seen.add(impact.eventId);
      return true;
    })
    .slice(0, 3);
}

export function selectWatchIssues(impacts: PortfolioImpact[]): PortfolioImpact[] {
  const strengthScore = { HIGH: 2, MEDIUM: 1, LOW: 0 };
  const seen = new Set<string>();
  return [...impacts]
    .filter(
      (impact) =>
        hasDisplayEvidence(impact) &&
        impact.impactStrength !== "LOW" &&
        (impact.conditionsToWatch.length > 0 ||
          impact.impactDirection === "NEGATIVE" ||
          impact.impactDirection === "MIXED" ||
          reviewVerification.has(impact.verificationStatus)),
    )
    .sort((left, right) => {
      const strength =
        strengthScore[right.impactStrength] -
        strengthScore[left.impactStrength];
      if (strength !== 0) return strength;
      const special =
        Number(reviewVerification.has(right.verificationStatus)) -
        Number(reviewVerification.has(left.verificationStatus));
      if (special !== 0) return special;
      return Date.parse(right.generatedAt) - Date.parse(left.generatedAt);
    })
    .filter((impact) => {
      if (seen.has(impact.eventId)) return false;
      seen.add(impact.eventId);
      return true;
    })
    .slice(0, 2);
}

export function countImportantInformation(impacts: PortfolioImpact[]): number {
  return new Set(
    impacts.filter(hasDisplayEvidence).map((impact) => impact.eventId),
  ).size;
}

export function formatAnalysisTime(value: string | null): string {
  if (!value) return "분석 기록 없음";
  return new Date(value).toLocaleString("ko-KR");
}
