import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  confidenceLabels,
  directionLabels,
  selectEvidence,
  selectWatchIssues,
  thesisStatusLabels,
} from "../src/lib/analysis-display.ts";
import {
  getAssetTypeLabel,
  getPositionStatusLabel,
  getThesisStatusLabel,
  getTrackingStatusLabel,
} from "../src/lib/display-labels.ts";
import {
  formatEditableDecimal,
  formatPortfolioPrice,
  formatPortfolioQuantity,
} from "../src/lib/portfolio-format.ts";
import {
  applyMarketDefaults,
} from "../src/lib/portfolio-defaults.ts";

test("사용자 라벨은 내부 enum을 한글 또는 승인된 약어로 표시한다", () => {
  assert.equal(getAssetTypeLabel("EQUITY"), "주식");
  assert.equal(getAssetTypeLabel("CRYPTO"), "암호화폐");
  assert.equal(getAssetTypeLabel("OTHER"), "기타");
  assert.equal(getPositionStatusLabel("CLOSED"), "청산 완료");
  assert.equal(getTrackingStatusLabel("REENTRY_WATCH"), "재진입 관심");
  assert.equal(getThesisStatusLabel("NOT_SET"), "분석 자료 없음");
  assert.equal(thesisStatusLabels.ACTIVE, "기존 근거 유지");
  assert.equal(confidenceLabels.LOW, "낮음");
  assert.equal(directionLabels.INSUFFICIENT_DATA, "데이터 부족");
  assert.equal(getAssetTypeLabel("NEW_ENUM"), "알 수 없음");
});

test("Decimal 문자열 포매터는 float 변환 없이 뒤쪽 0을 정리한다", () => {
  assert.equal(formatEditableDecimal("0.000000000000000000"), "0");
  assert.equal(formatEditableDecimal("1.000000000000000000"), "1");
  assert.equal(formatEditableDecimal("1.500000000000000000"), "1.5");
  assert.equal(formatEditableDecimal("0.000123450000000000"), "0.00012345");
  assert.equal(formatPortfolioQuantity("0.000000000000000000", "EQUITY", "005930"), "0");
  assert.equal(formatPortfolioPrice("180950.000000000000000000", "KRW"), "₩180,950");
  assert.equal(formatPortfolioPrice("152.800000000000000000", "USD"), "$152.80");
  assert.equal(formatPortfolioPrice("123.450000000000000000", "USDT"), "123.45 USDT");
  assert.equal(
    formatEditableDecimal("12345678901234567890.123450000000000000"),
    "12345678901234567890.12345",
  );
});

test("시장 기본값과 사용자가 직접 바꾼 값을 구분한다", () => {
  const base = { assetType: "EQUITY", market: "KRX", currency: "KRW" };
  assert.deepEqual(
    applyMarketDefaults(base, "KRX", { assetType: false, currency: false }),
    { ...base, market: "KRX", assetType: "EQUITY", currency: "KRW" },
  );
  assert.equal(
    applyMarketDefaults(base, "NASDAQ", { assetType: false, currency: false }).currency,
    "USD",
  );
  assert.equal(
    applyMarketDefaults(base, "NYSE", { assetType: false, currency: false }).currency,
    "USD",
  );
  assert.equal(
    applyMarketDefaults(base, "UPBIT", { assetType: false, currency: false }).assetType,
    "CRYPTO",
  );
  assert.equal(
    applyMarketDefaults(base, "BINANCE", { assetType: false, currency: false }).currency,
    "USDT",
  );
  assert.equal(
    applyMarketDefaults(base, "OTHER", { assetType: false, currency: false }).assetType,
    "OTHER",
  );
  const customized = { ...base, assetType: "ETF", currency: "USD" };
  assert.deepEqual(
    applyMarketDefaults(customized, "UPBIT", { assetType: true, currency: true }),
    { ...customized, market: "UPBIT" },
  );
});

test("API payload 생성 코드는 symbol과 assetType 필드명을 그대로 유지한다", async () => {
  const form = await readFile(
    new URL("../src/lib/portfolio-form.ts", import.meta.url),
    "utf8",
  );
  assert.match(form, /assetType: values\.assetType/);
  assert.match(form, /symbol: values\.symbol\.trim\(\)\.toUpperCase\(\)/);
  assert.doesNotMatch(form, /stockCode:/);
});

test("Portfolio 상세는 사용자 Thesis 입력 없이 자동 분석자료만 표시한다", async () => {
  const portfolio = await readFile(
    new URL("../src/components/portfolio/portfolio-client.tsx", import.meta.url),
    "utf8",
  );
  const detail = await readFile(
    new URL(
      "../src/components/portfolio/portfolio-detail-client.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  assert.match(portfolio, /종목명·종목코드 검색/);
  assert.match(portfolio, />\s*종목코드\s*</);
  assert.match(portfolio, />\s*시장\s*</);
  assert.match(portfolio, /type="number"/);
  assert.doesNotMatch(detail, /<textarea/);
  assert.doesNotMatch(detail, /saveThesis/);
  assert.doesNotMatch(detail, /사용자 확신도/);
  assert.doesNotMatch(detail, /투자근거 저장/);
  assert.doesNotMatch(detail, /thesisStatusLabels\).*<select/s);
  assert.match(detail, /const visibleSectionKeys = \[/);
  assert.match(detail, /const sectionTitle = \(key: string, label: string\)/);
  assert.match(detail, /sectionTitle\("summary", "자동 분석 요약"\)/);
  assert.match(detail, /sectionTitle\("evidence", "핵심 근거"\)/);
  assert.doesNotMatch(detail, /<Card title="\d+\./);
  assert.equal(
    [...detail.matchAll(/ChatGPT 심층 분석용 복사/g)].length,
    1,
  );
  assert.match(detail, /getPortfolioMappings/);
  assert.match(detail, /종목 연결 상태/);
  assert.match(detail, /분석 새로고침/);
  assert.doesNotMatch(detail, /AI_ASSISTED/);
  assert.match(detail, /watchIssues\.length \?/);
  assert.match(
    detail,
    /positiveEvidence\.length > 0 \|\| negativeEvidence\.length > 0/,
  );
});

test("검증 근거와 주시 이슈는 출처·중요도·중복·최대 개수 정책을 지킨다", () => {
  const base = {
    id: "impact-1",
    eventId: "event-1",
    portfolioItemId: "portfolio-1",
    impactDirection: "NEGATIVE",
    impactStrength: "HIGH",
    evidenceStrength: "HIGH",
    conditionsToWatch: ["계약 변경 확인"],
    sourceLinks: [
      {
        title: "공식 원문",
        url: "https://example.invalid/official",
        official: true,
      },
    ],
    verificationStatus: "OFFICIAL_CONFIRMED",
    generatedAt: "2026-07-26T12:00:00Z",
  };
  const impacts = [
    base,
    { ...base, id: "duplicate" },
    {
      ...base,
      id: "impact-2",
      eventId: "event-2",
      impactStrength: "MEDIUM",
      verificationStatus: "CORRECTED",
    },
    {
      ...base,
      id: "impact-3",
      eventId: "event-3",
      impactStrength: "MEDIUM",
    },
    {
      ...base,
      id: "low",
      eventId: "event-low",
      impactStrength: "LOW",
    },
    {
      ...base,
      id: "stale",
      eventId: "event-stale",
      verificationStatus: "STALE_REUSED",
    },
  ];
  const watchIssues = selectWatchIssues(impacts);
  assert.equal(watchIssues.length, 2);
  assert.equal(new Set(watchIssues.map((item) => item.eventId)).size, 2);
  assert.equal(watchIssues[0].impactStrength, "HIGH");
  assert.equal(selectEvidence(impacts, "negative").length, 3);
  assert.equal(selectEvidence(impacts, "positive").length, 0);
});

test("일반 출처 화면은 비활성 공개 시세 Provider를 렌더링하지 않는다", async () => {
  const sources = await readFile(
    new URL(
      "../src/components/sources/provider-status-client.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  assert.match(sources, /hiddenQuoteProviders/);
  assert.match(sources, /visibleProviders/);
  assert.doesNotMatch(sources, /최신 시세/);
  assert.doesNotMatch(sources, /Upbit 공개 BTC 시세/);
  assert.doesNotMatch(sources, /Binance 공개 BTC 시세/);
  assert.match(sources, /data\.conflictingMappingCount/);
  assert.match(sources, /data\.recentDisclosureCount/);
  assert.match(sources, /item\.requestCount/);
  assert.match(sources, /최근 오류/);
});

test("Portfolio 입력과 Dialog는 390px부터 데스크톱까지 넘침 방지 계약을 유지한다", async () => {
  const portfolio = await readFile(
    new URL("../src/components/portfolio/portfolio-client.tsx", import.meta.url),
    "utf8",
  );
  const dialog = await readFile(
    new URL("../src/components/common/dialog.tsx", import.meta.url),
    "utf8",
  );
  const detail = await readFile(
    new URL(
      "../src/components/portfolio/portfolio-detail-client.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  assert.match(portfolio, /className="min-w-0"/);
  assert.match(portfolio, /min-w-0 flex-1/);
  assert.match(portfolio, /sm:w-72/);
  assert.match(portfolio, /sm:grid-cols-2/);
  assert.match(dialog, /fixed inset-0/);
  assert.match(dialog, /overflow-hidden/);
  assert.match(portfolio, /overflow-y-auto/);
  assert.match(dialog, /max-h-/);
  assert.match(detail, /sm:grid-cols-2/);
  assert.match(detail, /lg:grid-cols-4/);
  assert.match(detail, /flex flex-wrap/);
});

test("공시 화면은 공식 공개 정보 필터와 포트폴리오 연결만 표시한다", async () => {
  const disclosures = await readFile(
    new URL(
      "../src/components/disclosures/disclosure-client.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  assert.match(disclosures, /const providerLabels/);
  assert.match(disclosures, /서식·공시 종류/);
  assert.match(disclosures, /신규·정정/);
  assert.match(disclosures, /검증 상태/);
  assert.match(disclosures, /relatedPortfolioItems/);
  assert.match(disclosures, /출처 등급 \{item\.sourceGrade\}/);
  assert.match(disclosures, /공식 원문 보기/);
  assert.match(disclosures, /공식 공시 데이터 제공자 미설정/);
  assert.match(disclosures, /공식 회사 연결 미확인/);
  assert.match(disclosures, /sm:grid-cols-2 lg:grid-cols-4/);
  assert.doesNotMatch(disclosures, /rawPayload|articleBody|disclosureBody/);
});
