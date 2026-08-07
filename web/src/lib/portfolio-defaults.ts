import type { Currency, PortfolioAssetType } from "@/types/api";

const MARKET_DEFAULTS: Record<
  string,
  { assetType: PortfolioAssetType; currency: Currency }
> = {
  KRX: { assetType: "EQUITY", currency: "KRW" },
  NASDAQ: { assetType: "EQUITY", currency: "USD" },
  NYSE: { assetType: "EQUITY", currency: "USD" },
  AMEX: { assetType: "EQUITY", currency: "USD" },
  UPBIT: { assetType: "CRYPTO", currency: "KRW" },
  BINANCE: { assetType: "CRYPTO", currency: "USDT" },
  OTHER: { assetType: "OTHER", currency: "OTHER" },
};

export function applyMarketDefaults<
  T extends {
    assetType: PortfolioAssetType;
    market: string;
    currency: Currency;
  },
>(
  values: T,
  market: string,
  overrides: { assetType: boolean; currency: boolean },
): T {
  const defaults = MARKET_DEFAULTS[market] ?? MARKET_DEFAULTS.OTHER;
  return {
    ...values,
    market,
    assetType: overrides.assetType ? values.assetType : defaults.assetType,
    currency: overrides.currency ? values.currency : defaults.currency,
  };
}
