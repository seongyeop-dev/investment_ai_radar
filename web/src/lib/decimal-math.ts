const SCALE = 18;
const ZERO = BigInt(0);
const ONE = BigInt(1);
const TWO = BigInt(2);
const HUNDRED = BigInt(100);
const TEN = BigInt(10);
const FACTOR = TEN ** BigInt(SCALE);
const DECIMAL_PATTERN = /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/;

type Parsed = { units: bigint; scale: number };

function parse(value: string): Parsed {
  const normalized = value.trim();
  if (!DECIMAL_PATTERN.test(normalized)) {
    throw new Error("올바른 Decimal 문자열이 아닙니다.");
  }
  const negative = normalized.startsWith("-");
  const unsigned = negative ? normalized.slice(1) : normalized;
  const [integer, fraction = ""] = unsigned.split(".");
  const units = BigInt(`${integer}${fraction}`);
  return { units: negative ? -units : units, scale: fraction.length };
}

function divideHalfEven(numerator: bigint, denominator: bigint): bigint {
  if (denominator <= ZERO) throw new Error("분모는 0보다 커야 합니다.");
  const negative = numerator < ZERO;
  const absolute = negative ? -numerator : numerator;
  const quotient = absolute / denominator;
  const remainder = absolute % denominator;
  const doubled = remainder * TWO;
  const rounded =
    doubled > denominator ||
    (doubled === denominator && quotient % TWO !== ZERO)
      ? quotient + ONE
      : quotient;
  return negative ? -rounded : rounded;
}

function toScale(value: Parsed, scale: number): bigint {
  if (value.scale === scale) return value.units;
  if (value.scale < scale) {
    return value.units * TEN ** BigInt(scale - value.scale);
  }
  return divideHalfEven(
    value.units,
    TEN ** BigInt(value.scale - scale),
  );
}

function formatUnits(units: bigint, trim = false): string {
  const negative = units < ZERO;
  const absolute = negative ? -units : units;
  const padded = absolute.toString().padStart(SCALE + 1, "0");
  const integer = padded.slice(0, -SCALE);
  const fraction = padded.slice(-SCALE);
  const resolvedFraction = trim ? fraction.replace(/0+$/, "") : fraction;
  const body = resolvedFraction ? `${integer}.${resolvedFraction}` : integer;
  return negative && absolute !== ZERO ? `-${body}` : body;
}

export function decimalMultiply(left: string, right: string): string {
  const a = parse(left);
  const b = parse(right);
  return formatUnits(
    toScale({ units: a.units * b.units, scale: a.scale + b.scale }, SCALE),
  );
}

export function decimalDivide(
  numerator: string,
  denominator: string,
): string {
  const numeratorUnits = toScale(parse(numerator), SCALE);
  const denominatorUnits = toScale(parse(denominator), SCALE);
  if (denominatorUnits === ZERO) {
    throw new Error("0으로 나눌 수 없습니다.");
  }
  return formatUnits(
    divideHalfEven(numeratorUnits * FACTOR, denominatorUnits),
  );
}

export function decimalSubtract(
  first: string,
  ...rest: string[]
): string {
  let units = toScale(parse(first), SCALE);
  for (const value of rest) units -= toScale(parse(value), SCALE);
  return formatUnits(units);
}

export function decimalSum(values: string[]): string {
  return formatUnits(
    values.reduce(
      (total, value) => total + toScale(parse(value), SCALE),
      ZERO,
    ),
  );
}

export function decimalPercentage(
  numerator: string,
  denominator: string,
): string | null {
  const numeratorUnits = toScale(parse(numerator), SCALE);
  const denominatorUnits = toScale(parse(denominator), SCALE);
  if (denominatorUnits === ZERO) return null;
  return formatUnits(
    divideHalfEven(numeratorUnits * HUNDRED * FACTOR, denominatorUnits),
  );
}

export function decimalCompare(left: string, right: string): number {
  const a = toScale(parse(left), SCALE);
  const b = toScale(parse(right), SCALE);
  return a === b ? 0 : a < b ? -1 : 1;
}

export function trimDecimal(value: string): string {
  return formatUnits(toScale(parse(value), SCALE), true);
}
