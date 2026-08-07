import type {
  Currency,
  DecimalString,
  PortfolioAssetType,
} from "@/types/api";

function groupedDecimal(value: DecimalString, trimFraction = false): string {
  const [integer, rawFraction = ""] = value.split(".");
  const fraction = trimFraction
    ? rawFraction.replace(/0+$/, "")
    : rawFraction;
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fraction ? `${grouped}.${fraction}` : grouped;
}

export function formatEditableDecimal(
  value: DecimalString | null,
): string {
  if (value === null || value === "") return "";
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [rawInteger = "0", rawFraction = ""] = unsigned.split(".");
  const integer = rawInteger.replace(/^0+(?=\d)/, "") || "0";
  const fraction = rawFraction.replace(/0+$/, "");
  const normalized = fraction ? `${integer}.${fraction}` : integer;
  return negative && normalized !== "0" ? `-${normalized}` : normalized;
}

function roundedDecimal(
  value: DecimalString,
  fractionDigits: number,
  fixed = false,
): string {
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [rawInteger = "0", rawFraction = ""] = unsigned.split(".");
  const kept = rawFraction.slice(0, fractionDigits).padEnd(fractionDigits, "0");
  const shouldRound = Number(rawFraction[fractionDigits] ?? "0") >= 5;
  let scaled = `${rawInteger.replace(/^0+(?=\d)/, "") || "0"}${kept}`;
  if (shouldRound) {
    scaled = (BigInt(scaled || "0") + BigInt(1)).toString();
  }
  const padded = scaled.padStart(fractionDigits + 1, "0");
  const integer =
    fractionDigits > 0 ? padded.slice(0, -fractionDigits) : padded;
  let fraction =
    fractionDigits > 0 ? padded.slice(-fractionDigits) : "";
  if (!fixed) fraction = fraction.replace(/0+$/, "");
  const result = fraction ? `${integer}.${fraction}` : integer;
  return negative && !/^0(?:\.0+)?$/.test(result) ? `-${result}` : result;
}

export function formatPortfolioPrice(
  value: DecimalString | null,
  currency: Currency,
): string {
  if (value === null) return "미입력";
  if (currency === "KRW") {
    return `₩${groupedDecimal(roundedDecimal(value, 0))}`;
  }
  if (currency === "USD") {
    return `$${groupedDecimal(roundedDecimal(value, 2, true))}`;
  }
  if (currency === "USDT") {
    return `${groupedDecimal(roundedDecimal(value, 8), true)} USDT`;
  }
  return `${groupedDecimal(roundedDecimal(value, 4), true)} 기타 통화`;
}

export function formatPortfolioQuantity(
  value: DecimalString,
  assetType: PortfolioAssetType,
  symbol: string,
): string {
  const formatted = groupedDecimal(formatEditableDecimal(value), true);
  return assetType === "CRYPTO" ? `${formatted} ${symbol}` : formatted;
}

export function formatRealizedPnl(
  value: DecimalString,
  currency: Currency,
): string {
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const zero = /^0(?:\.0+)?$/.test(unsigned);
  const sign = negative ? "-" : zero ? "" : "+";
  const amount = formatPortfolioPrice(unsigned, currency);
  return `${sign}${amount}`;
}

export function formatSignedPercent(value: DecimalString | null): string {
  if (value === null) return "계산 불가";
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const zero = /^0(?:\.0+)?$/.test(unsigned);
  return `${negative ? "-" : zero ? "" : "+"}${groupedDecimal(
    roundedDecimal(unsigned, 2),
    true,
  )}%`;
}
