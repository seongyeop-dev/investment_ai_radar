export type SourceGrade = "A" | "B" | "C" | "D";
export type VerificationStatus =
  | "OFFICIAL_CONFIRMED"
  | "MULTI_SOURCE_CONFIRMED"
  | "NEEDS_VERIFICATION"
  | "UNVERIFIED"
  | "CONFLICTING"
  | "OFFICIALLY_DENIED"
  | "CORRECTED"
  | "STALE_REUSED";

export type RecommendationType =
  | "BUY_REVIEW"
  | "HOLD"
  | "WAIT"
  | "REDUCE_REVIEW"
  | "SELL_REVIEW"
  | "INSUFFICIENT_DATA";

export interface RecommendationContract {
  id: string;
  portfolioItemId: string;
  recommendationType: RecommendationType;
  generatedAt: string;
  validUntil: string;
  portfolioContext: string;
  evidenceIds: string[];
  confidence: string;
  trustScore: string;
  dataCompleteness: string;
  bullishEvidence: string[];
  bearishEvidence: string[];
  risks: string[];
  conditions: string[];
  invalidationConditions: string[];
  humanDecisionRequired: true;
}
