import { isNonNegativeDecimal, isPercentage } from "@/lib/portfolio-form";
import type {
  RecommendationMode,
  RiskProfile,
  RiskProfileInput,
} from "@/types/api";

export interface RiskProfileFormValues {
  maxPositionPercent: string;
  maxPortfolioLossPercent: string;
  defaultStopLossPercent: string;
  defaultTakeProfitPercent: string;
  maxSingleTradeAmount: string;
  cashReservePercent: string;
  allowAveragingDown: boolean;
  recommendationMode: RecommendationMode;
}

export const EMPTY_RISK_PROFILE_FORM: RiskProfileFormValues = {
  maxPositionPercent: "",
  maxPortfolioLossPercent: "",
  defaultStopLossPercent: "",
  defaultTakeProfitPercent: "",
  maxSingleTradeAmount: "",
  cashReservePercent: "",
  allowAveragingDown: false,
  recommendationMode: "UNSET",
};

const PERCENT_FIELDS = [
  "maxPositionPercent",
  "maxPortfolioLossPercent",
  "defaultStopLossPercent",
  "defaultTakeProfitPercent",
  "cashReservePercent",
] as const;

export function validateRiskProfileForm(
  values: RiskProfileFormValues,
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of PERCENT_FIELDS) {
    if (values[field] && !isPercentage(values[field])) {
      errors[field] = "0에서 100 사이의 값을 입력해 주세요.";
    }
  }
  if (
    values.maxSingleTradeAmount &&
    !isNonNegativeDecimal(values.maxSingleTradeAmount)
  ) {
    errors.maxSingleTradeAmount =
      "0 이상의 금액을 숫자 문자열로 입력해 주세요.";
  }
  return errors;
}

function optionalDecimal(value: string): string | null {
  return value.trim() || null;
}

export function toRiskProfileInput(
  values: RiskProfileFormValues,
): RiskProfileInput {
  return {
    maxPositionPercent: optionalDecimal(values.maxPositionPercent),
    maxPortfolioLossPercent: optionalDecimal(values.maxPortfolioLossPercent),
    defaultStopLossPercent: optionalDecimal(values.defaultStopLossPercent),
    defaultTakeProfitPercent: optionalDecimal(
      values.defaultTakeProfitPercent,
    ),
    maxSingleTradeAmount: optionalDecimal(values.maxSingleTradeAmount),
    cashReservePercent: optionalDecimal(values.cashReservePercent),
    allowAveragingDown: values.allowAveragingDown,
    recommendationMode: values.recommendationMode,
  };
}

export function riskProfileToForm(
  profile: RiskProfile,
): RiskProfileFormValues {
  return {
    maxPositionPercent: profile.maxPositionPercent ?? "",
    maxPortfolioLossPercent: profile.maxPortfolioLossPercent ?? "",
    defaultStopLossPercent: profile.defaultStopLossPercent ?? "",
    defaultTakeProfitPercent: profile.defaultTakeProfitPercent ?? "",
    maxSingleTradeAmount: profile.maxSingleTradeAmount ?? "",
    cashReservePercent: profile.cashReservePercent ?? "",
    allowAveragingDown: profile.allowAveragingDown,
    recommendationMode: profile.recommendationMode,
  };
}
