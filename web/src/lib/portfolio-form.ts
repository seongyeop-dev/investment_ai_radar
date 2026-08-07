import type {
  Currency,
  HoldingStatus,
  InvestmentHorizon,
  PortfolioCreateInput,
  PortfolioItem,
  PortfolioAssetType,
  TrackingStatus,
} from "@/types/api";
import { formatEditableDecimal } from "@/lib/portfolio-format";

export interface PortfolioFormValues {
  assetType: PortfolioAssetType;
  name: string;
  symbol: string;
  market: string;
  currency: Currency;
  holdingStatus: HoldingStatus;
  trackingStatus: TrackingStatus;
  quantity: string;
  averagePrice: string;
  initialTradedAt: string;
  initialFeeAmount: string;
  initialTaxAmount: string;
  investmentHorizon: InvestmentHorizon;
  strategy: string;
  targetAllocation: string;
  maxLossPercent: string;
  notes: string;
}

export const EMPTY_PORTFOLIO_FORM: PortfolioFormValues = {
  assetType: "EQUITY",
  name: "",
  symbol: "",
  market: "KRX",
  currency: "KRW",
  holdingStatus: "WATCHLIST",
  trackingStatus: "WATCHLIST",
  quantity: "0",
  averagePrice: "",
  initialTradedAt: "",
  initialFeeAmount: "0",
  initialTaxAmount: "0",
  investmentHorizon: "UNSET",
  strategy: "",
  targetAllocation: "",
  maxLossPercent: "",
  notes: "",
};

const DECIMAL_PATTERN = /^(?:0|[1-9]\d*)(?:\.\d+)?$/;

export const MARKET_OPTIONS: Record<PortfolioAssetType, string[]> = {
  EQUITY: ["KRX", "NASDAQ", "NYSE", "AMEX", "OTC", "OTHER"],
  ETF: ["KRX", "NASDAQ", "NYSE", "AMEX", "OTC", "OTHER"],
  ADR: ["NASDAQ", "NYSE", "AMEX", "OTC", "OTHER"],
  CRYPTO: ["UPBIT", "BINANCE", "OTHER"],
  OTHER: ["OTHER"],
};

export type PortfolioPreset =
  | "KOREAN_EQUITY"
  | "US_EQUITY"
  | "UPBIT_BITCOIN"
  | "BINANCE_BITCOIN";

export function applyPortfolioPreset(
  values: PortfolioFormValues,
  preset: PortfolioPreset,
): PortfolioFormValues {
  const fields = {
    KOREAN_EQUITY: {
      assetType: "EQUITY",
      market: "KRX",
      currency: "KRW",
    },
    US_EQUITY: {
      assetType: "EQUITY",
      market: "NASDAQ",
      currency: "USD",
    },
    UPBIT_BITCOIN: {
      assetType: "CRYPTO",
      name: "비트코인",
      symbol: "BTC",
      market: "UPBIT",
      currency: "KRW",
    },
    BINANCE_BITCOIN: {
      assetType: "CRYPTO",
      name: "비트코인",
      symbol: "BTC",
      market: "BINANCE",
      currency: "USDT",
    },
  } satisfies Record<PortfolioPreset, Partial<PortfolioFormValues>>;
  return { ...values, ...fields[preset] };
}

export function isNonNegativeDecimal(value: string): boolean {
  return DECIMAL_PATTERN.test(value.trim());
}

export function isPositiveDecimal(value: string): boolean {
  const normalized = value.trim();
  return (
    isNonNegativeDecimal(normalized) &&
    normalized.replace(/[.0]/g, "").length > 0
  );
}

export function isPercentage(value: string): boolean {
  const normalized = value.trim();
  if (!isNonNegativeDecimal(normalized)) {
    return false;
  }
  const [integer, fraction = ""] = normalized.split(".");
  const compactInteger = integer.replace(/^0+(?=\d)/, "");
  if (compactInteger.length > 3) {
    return false;
  }
  const whole = Number(compactInteger);
  return whole < 100 || (whole === 100 && !/[1-9]/.test(fraction));
}

export function validatePortfolioForm(
  values: PortfolioFormValues,
  requireInitialBuy = true,
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!values.name.trim()) errors.name = "종목명을 입력해 주세요.";
  if (!values.symbol.trim()) errors.symbol = "종목코드를 입력해 주세요.";
  if (values.symbol.trim().length > 32)
    errors.symbol = "종목코드는 32자 이하여야 합니다.";
  if (!values.market.trim()) errors.market = "시장을 입력해 주세요.";
  if (!MARKET_OPTIONS[values.assetType].includes(values.market.trim().toUpperCase()))
    errors.market =
      values.assetType === "CRYPTO"
        ? "지원하는 거래소를 선택해 주세요."
        : "지원하는 시장을 선택해 주세요.";
  if (!isNonNegativeDecimal(values.quantity))
    errors.quantity = "수량은 0 이상의 숫자 문자열이어야 합니다.";
  if (
    values.assetType === "CRYPTO" &&
    (values.quantity.trim().split(".")[1]?.length ?? 0) > 8
  )
    errors.quantity = "암호자산 수량은 소수점 이하 8자리까지 입력할 수 있습니다.";
  if (values.averagePrice && !isNonNegativeDecimal(values.averagePrice))
    errors.averagePrice = "평균단가는 0 이상의 숫자 문자열이어야 합니다.";
  if (values.holdingStatus === "HOLDING") {
    if (!isPositiveDecimal(values.quantity))
      errors.quantity = "보유 상태의 수량은 0보다 커야 합니다.";
    if (!isPositiveDecimal(values.averagePrice))
      errors.averagePrice = "보유 상태의 평균단가는 0보다 커야 합니다.";
    if (requireInitialBuy && !values.initialTradedAt) {
      errors.initialTradedAt = "최초 매수일시를 입력하세요.";
    } else if (requireInitialBuy) {
      const initialDate = new Date(values.initialTradedAt);
      if (Number.isNaN(initialDate.getTime())) {
        errors.initialTradedAt = "올바른 최초 매수일시를 입력하세요.";
      } else if (initialDate.getTime() > Date.now()) {
        errors.initialTradedAt = "미래 시각의 매수 거래는 등록할 수 없습니다.";
      }
    }
    if (requireInitialBuy && !isNonNegativeDecimal(values.initialFeeAmount)) {
      errors.initialFeeAmount = "수수료는 0 이상이어야 합니다.";
    }
    if (requireInitialBuy && !isNonNegativeDecimal(values.initialTaxAmount)) {
      errors.initialTaxAmount = "세금은 0 이상이어야 합니다.";
    }
  }
  for (const field of ["targetAllocation", "maxLossPercent"] as const) {
    if (values[field] && !isPercentage(values[field])) {
      errors[field] = "0에서 100 사이의 값을 입력해 주세요.";
    }
  }
  if (values.strategy.length > 500)
    errors.strategy = "전략은 500자 이하여야 합니다.";
  if (values.notes.length > 4000)
    errors.notes = "메모는 4,000자 이하여야 합니다.";
  return errors;
}

function optionalDecimal(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

export function toPortfolioInput(
  values: PortfolioFormValues,
  includeInitialBuy = false,
): PortfolioCreateInput {
  const holding = values.holdingStatus === "HOLDING";
  return {
    assetType: values.assetType,
    name: values.name.trim(),
    symbol: values.symbol.trim().toUpperCase(),
    market: values.market.trim().toUpperCase(),
    currency: values.currency,
    holdingStatus: values.holdingStatus,
    trackingStatus: holding ? "NONE" : values.trackingStatus,
    quantity: holding ? values.quantity.trim() || "0" : "0",
    averagePrice: holding ? optionalDecimal(values.averagePrice) : null,
    investmentHorizon: values.investmentHorizon,
    strategy: values.strategy.trim(),
    targetAllocation: optionalDecimal(values.targetAllocation),
    maxLossPercent: optionalDecimal(values.maxLossPercent),
    notes: values.notes.trim() || null,
    ...(includeInitialBuy
      ? {
          initialBuy: holding
            ? {
                tradedAt: new Date(values.initialTradedAt).toISOString(),
                quantity: values.quantity.trim(),
                unitPrice: values.averagePrice.trim(),
                feeAmount: values.initialFeeAmount.trim(),
                taxAmount: values.initialTaxAmount.trim(),
                notes: "종목 등록 시 최초 매수",
              }
            : null,
        }
      : {}),
  };
}

export function portfolioToForm(item: PortfolioItem): PortfolioFormValues {
  return {
    assetType: item.assetType,
    name: item.name,
    symbol: item.symbol,
    market: item.market,
    currency: item.currency,
    holdingStatus: item.holdingStatus,
    trackingStatus: item.trackingStatus,
    quantity: formatEditableDecimal(item.quantity),
    averagePrice: formatEditableDecimal(item.averagePrice),
    initialTradedAt: "",
    initialFeeAmount: "0",
    initialTaxAmount: "0",
    investmentHorizon: item.investmentHorizon,
    strategy: item.strategy,
    targetAllocation: item.targetAllocation ?? "",
    maxLossPercent: item.maxLossPercent ?? "",
    notes: item.notes ?? "",
  };
}
