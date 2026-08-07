import type {
  Currency,
  InvestmentHorizon,
  PortfolioAssetType,
  PositionStatus,
  ThesisStatus,
  TrackingStatus,
  UserConviction,
} from "@/types/api";

export const assetTypeLabels: Record<PortfolioAssetType, string> = {
  EQUITY: "주식",
  ETF: "ETF",
  ADR: "ADR",
  CRYPTO: "암호화폐",
  OTHER: "기타",
};

export const positionStatusLabels: Record<PositionStatus, string> = {
  EMPTY: "미보유",
  HOLDING: "보유",
  CLOSED: "청산 완료",
  NEEDS_REVIEW: "확인 필요",
};

export const trackingStatusLabels: Record<TrackingStatus, string> = {
  NONE: "추적 없음",
  WATCHLIST: "관심",
  REENTRY_WATCH: "재진입 관심",
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

export const convictionLabels: Record<UserConviction, string> = {
  NOT_SET: "미설정",
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

export const marketLabels: Record<string, string> = {
  KRX: "KRX",
  NASDAQ: "NASDAQ",
  NYSE: "NYSE",
  AMEX: "AMEX",
  UPBIT: "UPBIT",
  BINANCE: "BINANCE",
  OTHER: "기타",
};

export const currencyLabels: Record<Currency, string> = {
  KRW: "KRW",
  USD: "USD",
  USDT: "USDT",
  OTHER: "기타",
};

export const investmentHorizonLabels: Record<InvestmentHorizon, string> = {
  SCALP: "단기 대응",
  SHORT: "단기",
  MEDIUM: "중기",
  LONG: "장기",
  UNSET: "미설정",
};

function safeLabel(labels: Record<string, string>, value: string): string {
  return labels[value] ?? "알 수 없음";
}

export const getAssetTypeLabel = (value: string): string =>
  safeLabel(assetTypeLabels, value);
export const getPositionStatusLabel = (value: string): string =>
  safeLabel(positionStatusLabels, value);
export const getTrackingStatusLabel = (value: string): string =>
  safeLabel(trackingStatusLabels, value);
export const getThesisStatusLabel = (value: string): string =>
  safeLabel(thesisStatusLabels, value);
export const getConvictionLabel = (value: string): string =>
  safeLabel(convictionLabels, value);
export const getMarketLabel = (value: string): string =>
  safeLabel(marketLabels, value);
export const getCurrencyLabel = (value: string): string =>
  safeLabel(currencyLabels, value);
export const getInvestmentHorizonLabel = (value: string): string =>
  safeLabel(investmentHorizonLabels, value);
