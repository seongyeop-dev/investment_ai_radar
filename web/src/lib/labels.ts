import type {
  HoldingStatus,
  InvestmentHorizon,
  RecommendationMode,
} from "@/types/api";

export const HOLDING_STATUS_LABELS: Record<HoldingStatus, string> = {
  HOLDING: "보유",
  WATCHLIST: "관심",
  SOLD: "매도 완료",
  REENTRY_WATCH: "재진입 관심",
};

export const INVESTMENT_HORIZON_LABELS: Record<InvestmentHorizon, string> = {
  SCALP: "단타",
  SHORT: "단기",
  MEDIUM: "중기",
  LONG: "장기",
  UNSET: "미설정",
};

export const RECOMMENDATION_MODE_LABELS: Record<RecommendationMode, string> = {
  CONSERVATIVE: "보수적",
  BALANCED: "균형",
  AGGRESSIVE: "공격적",
  UNSET: "미설정",
};
