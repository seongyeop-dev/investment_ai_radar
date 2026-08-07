export type DecimalString = string;
export type HoldingStatus =
  | "HOLDING"
  | "WATCHLIST"
  | "SOLD"
  | "REENTRY_WATCH";
export type InvestmentHorizon =
  | "SCALP"
  | "SHORT"
  | "MEDIUM"
  | "LONG"
  | "UNSET";
export type Currency = "KRW" | "USD" | "USDT" | "OTHER";
export type PortfolioAssetType = "EQUITY" | "ETF" | "ADR" | "CRYPTO" | "OTHER";
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
export type LifecycleStatus =
  | "ACTIVE"
  | "UPDATED"
  | "CORRECTED"
  | "DENIED"
  | "STALE"
  | "ARCHIVED";
export type CertaintyLevel =
  | "CONFIRMED"
  | "ANNOUNCED"
  | "PLANNED"
  | "UNDER_REVIEW"
  | "PROPOSED"
  | "POSSIBLE"
  | "SPECULATIVE"
  | "UNSUPPORTED";
export type RecommendationMode =
  | "CONSERVATIVE"
  | "BALANCED"
  | "AGGRESSIVE"
  | "UNSET";
export type RiskStyle =
  | "CONSERVATIVE"
  | "BALANCED"
  | "AGGRESSIVE"
  | "CUSTOM";
export type PrimaryGoal =
  | "CAPITAL_PRESERVATION"
  | "INCOME"
  | "BALANCED_GROWTH"
  | "GROWTH"
  | "CUSTOM";
export type AveragingDownPolicy = "DISABLED" | "CONDITIONAL" | "ALLOWED";
export type RiskProfileSource = "CUSTOM" | "DATA_ASSISTED";
export type RiskRecommendationConfidence = "LOW" | "MEDIUM" | "HIGH";
export type ConfirmationAnswer = "YES" | "NO" | "UNSURE";
export type AcceptableLossRange =
  | "UP_TO_10"
  | "FROM_10_TO_20"
  | "OVER_20"
  | "UNSURE";
export type MarketBriefingType =
  | "KRX_PRE_OPEN"
  | "KRX_POST_CLOSE"
  | "NASDAQ_PRE_OPEN"
  | "NASDAQ_POST_CLOSE";
export type MarketCode = "KRX" | "NASDAQ";
export type MarketScheduleStatus =
  | "CONFIRMED"
  | "ESTIMATED"
  | "NOT_CONFIGURED"
  | "UNAVAILABLE"
  | "CLOSED";
export type SaleTransactionType =
  | "PARTIAL_SALE"
  | "FULL_SALE"
  | "HISTORICAL_SALE";
export type SaleTransactionStatus = "ACTIVE" | "VOIDED";
export type PositionStatus = "EMPTY" | "HOLDING" | "CLOSED" | "NEEDS_REVIEW";
export type TrackingStatus = "NONE" | "WATCHLIST" | "REENTRY_WATCH";
export type TransactionSide = "BUY" | "SELL";
export type PositionTransactionType =
  | "OPENING_BALANCE"
  | "NORMAL"
  | "HISTORICAL_IMPORT";
export type TransactionSourceType =
  | "USER_ENTRY"
  | "MIGRATED_SNAPSHOT"
  | "MIGRATED_SALE"
  | "HISTORICAL_IMPORT";
export type PositionTransactionStatus = "ACTIVE" | "VOIDED";

export interface PositionSummary {
  portfolioItemId: string;
  positionStatus: PositionStatus;
  trackingStatus: TrackingStatus;
  currentQuantity: DecimalString;
  currentAveragePrice: DecimalString | null;
  totalBoughtQuantity: DecimalString;
  totalSoldQuantity: DecimalString;
  weightedAverageSalePrice: DecimalString | null;
  totalRealizedPnl: DecimalString;
  totalRealizedReturnPercent: DecimalString | null;
  activeTransactionCount: number;
  buyCount: number;
  sellCount: number;
  firstTradedAt: string | null;
  lastTradedAt: string | null;
}

export interface PositionTransaction {
  id: string;
  portfolioItemId: string;
  transactionSide: TransactionSide;
  transactionType: PositionTransactionType;
  tradedAt: string;
  quantity: DecimalString;
  unitPrice: DecimalString;
  currency: Currency;
  feeAmount: DecimalString;
  taxAmount: DecimalString;
  grossAmount: DecimalString;
  quantityBefore: DecimalString;
  quantityAfter: DecimalString;
  averagePriceBefore: DecimalString | null;
  averagePriceAfter: DecimalString | null;
  realizedPnl: DecimalString | null;
  realizedReturnPercent: DecimalString | null;
  sequenceNumber: number;
  sourceType: TransactionSourceType;
  status: PositionTransactionStatus;
  voidedAt: string | null;
  voidReason: string | null;
  notes: string | null;
  idempotencyKey: string;
  createdAt: string;
  updatedAt: string;
}

export interface PositionTransactionInput {
  tradedAt: string;
  quantity: DecimalString;
  unitPrice: DecimalString;
  feeAmount: DecimalString;
  taxAmount: DecimalString;
  notes: string | null;
  idempotencyKey?: string | null;
}

export type PositionTransactionUpdateInput = Omit<
  Partial<PositionTransactionInput>,
  "quantity" | "idempotencyKey"
>;

export interface HistoricalTransactionInput
  extends PositionTransactionInput {
  transactionSide: TransactionSide;
}

export interface PositionTransactionListResponse {
  items: PositionTransaction[];
  total: number;
}

export interface SaleSummary {
  activeSaleCount: number;
  totalSoldQuantity: DecimalString;
  totalGrossProceeds: DecimalString;
  totalFeeAmount: DecimalString;
  totalTaxAmount: DecimalString;
  totalCostBasis: DecimalString;
  totalRealizedPnl: DecimalString;
  totalRealizedReturnPercent: DecimalString | null;
  weightedAverageSalePrice: DecimalString | null;
  firstSoldAt: string | null;
  lastSoldAt: string | null;
}

export interface SaleTransaction {
  id: string;
  portfolioItemId: string;
  transactionType: SaleTransactionType;
  soldAt: string;
  quantity: DecimalString;
  salePrice: DecimalString;
  purchaseAveragePriceSnapshot: DecimalString;
  currency: Currency;
  feeAmount: DecimalString;
  taxAmount: DecimalString;
  grossProceeds: DecimalString;
  costBasis: DecimalString;
  realizedPnl: DecimalString;
  realizedReturnPercent: DecimalString | null;
  quantityBefore: DecimalString;
  quantityAfter: DecimalString;
  historicalImport: boolean;
  notes: string | null;
  status: SaleTransactionStatus;
  voidedAt: string | null;
  voidReason: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SaleCreateInput {
  soldAt: string;
  quantity: DecimalString;
  salePrice: DecimalString;
  feeAmount: DecimalString;
  taxAmount: DecimalString;
  notes: string | null;
}

export type SaleUpdateInput = Omit<Partial<SaleCreateInput>, "quantity">;

export interface SaleListResponse {
  items: SaleTransaction[];
  total: number;
}

export type HistoricalSaleInput = SaleCreateInput;

export interface HistoricalPortfolioInput {
  assetType: PortfolioAssetType;
  symbol: string;
  name: string;
  market: string;
  currency: Currency;
  averagePrice: DecimalString;
  totalSoldQuantity: DecimalString;
  investmentHorizon: InvestmentHorizon;
  strategy: string;
  targetAllocation: DecimalString | null;
  maxLossPercent: DecimalString | null;
  notes: string | null;
  sales: HistoricalSaleInput[];
}

export interface HistoricalPortfolioResponse {
  portfolioId: string;
  sales: SaleTransaction[];
  saleSummary: SaleSummary;
}

export interface PortfolioItem {
  id: string;
  assetType: PortfolioAssetType;
  symbol: string;
  name: string;
  market: string;
  currency: Currency;
  holdingStatus: HoldingStatus;
  positionStatus: PositionStatus;
  trackingStatus: TrackingStatus;
  quantity: DecimalString;
  averagePrice: DecimalString | null;
  investmentHorizon: InvestmentHorizon;
  strategy: string;
  targetAllocation: DecimalString | null;
  maxLossPercent: DecimalString | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
  currentPriceAvailability: "NOT_CONFIGURED";
  saleSummary: SaleSummary | null;
  activeSaleCount: number;
  totalSoldQuantity: DecimalString;
  weightedAverageSalePrice: DecimalString | null;
  totalRealizedPnl: DecimalString;
  totalRealizedReturnPercent: DecimalString | null;
  firstSoldAt: string | null;
  lastSoldAt: string | null;
  positionSummary: PositionSummary | null;
  totalBoughtQuantity: DecimalString;
  activeTransactionCount: number;
  buyTransactionCount: number;
  sellTransactionCount: number;
  firstTradedAt: string | null;
  lastTradedAt: string | null;
}

export interface PortfolioCreateInput {
  assetType: PortfolioAssetType;
  symbol: string;
  name: string;
  market: string;
  currency: Currency;
  holdingStatus: HoldingStatus;
  trackingStatus?: TrackingStatus | null;
  quantity: DecimalString;
  averagePrice: DecimalString | null;
  investmentHorizon: InvestmentHorizon;
  strategy: string;
  targetAllocation: DecimalString | null;
  maxLossPercent: DecimalString | null;
  notes: string | null;
  initialBuy?: PositionTransactionInput | null;
}

export type PortfolioUpdateInput = Partial<PortfolioCreateInput>;

export interface PortfolioListResponse {
  items: PortfolioItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PortfolioListFilters {
  holdingStatus?: HoldingStatus | "";
  positionStatus?: PositionStatus | "";
  trackingStatus?: TrackingStatus | "";
  market?: string;
  query?: string;
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
}

export interface PortfolioSummary {
  total: number;
  holding: number;
  watchlist: number;
  reentryWatch: number;
  closed: number;
  needsReview: number;
  thesisNotSet: number;
}

export interface PortfolioContextInput {
  positionStatus?: PositionStatus;
  trackingStatus?: TrackingStatus;
  currentQuantity?: DecimalString;
  averageCost?: DecimalString | null;
  currency?: Currency;
  investmentHorizon?: InvestmentHorizon;
  memo?: string | null;
}

export type ThesisStatus =
  | "NOT_SET"
  | "ACTIVE"
  | "STRENGTHENED"
  | "WEAKENED"
  | "PARTIALLY_BROKEN"
  | "BROKEN"
  | "REVIEW_REQUIRED";
export type UserConviction = "LOW" | "MEDIUM" | "HIGH" | "NOT_SET";
export type AnalysisConfidence = "LOW" | "MEDIUM" | "HIGH";
export type DecisionDirection =
  | "ADD_REVIEW"
  | "HOLD"
  | "WAIT"
  | "REDUCE_REVIEW"
  | "EXIT_REVIEW"
  | "INSUFFICIENT_DATA";

export interface InvestmentThesisInput {
  thesisSummary: string;
  investmentPurpose: string;
  investmentHorizon: string;
  originalReasons: string[];
  expectedCatalysts: string[];
  keyRisks: string[];
  conditionsToAdd: string[];
  conditionsToHold: string[];
  conditionsToReduce: string[];
  conditionsToExit: string[];
  invalidationConditions: string[];
  questionsToVerify: string[];
  userConviction: UserConviction;
  thesisStatus: ThesisStatus;
}

export interface InvestmentThesis extends InvestmentThesisInput {
  id: string | null;
  portfolioItemId: string;
  createdAt: string | null;
  updatedAt: string | null;
  lastReviewedAt: string | null;
}

export interface SourceLink {
  title: string;
  url: string;
  official: boolean;
}

export interface PortfolioImpact {
  id: string;
  eventId: string;
  portfolioItemId: string;
  thesisId: string | null;
  relevance: string;
  impactDirection: "POSITIVE" | "NEGATIVE" | "MIXED" | "NEUTRAL" | "UNCLEAR";
  impactStrength: AnalysisConfidence;
  impactHorizon: string;
  thesisEffect: string;
  confidence: AnalysisConfidence;
  evidenceStrength: AnalysisConfidence;
  oneLineSummary: string;
  impactPath: string[];
  supportingFactors: string[];
  opposingFactors: string[];
  conditionsToWatch: string[];
  invalidationConditions: string[];
  missingInformation: string[];
  sourceLinks: SourceLink[];
  verificationStatus: VerificationStatus;
  generatedBy: "RULE_BASED" | "USER" | "AI_ASSISTED";
  generatedAt: string;
  validUntil: string | null;
  humanDecisionRequired: boolean;
}

export interface DecisionReview {
  id: string | null;
  portfolioItemId: string;
  thesisId: string | null;
  direction: DecisionDirection;
  thesisStatus: ThesisStatus;
  confidence: AnalysisConfidence;
  evidenceStrength: AnalysisConfidence;
  whyNow: string;
  supportingEvidence: string[];
  contraryEvidence: string[];
  positiveFactors: string[];
  negativeFactors: string[];
  conditionsToAdd: string[];
  conditionsToHold: string[];
  conditionsToReduce: string[];
  conditionsToExit: string[];
  invalidationConditions: string[];
  missingInformation: string[];
  manualReferencePrice: DecimalString | null;
  averageCostSnapshot: DecimalString | null;
  quantitySnapshot: DecimalString;
  riskProfileSnapshot: Record<string, unknown>;
  basedOnEventIds: string[];
  generatedBy: "RULE_BASED" | "USER" | "AI_ASSISTED";
  generatedAt: string;
  validUntil: string | null;
  acknowledgedAt: string | null;
  userDecision: string | null;
  humanDecisionRequired: true;
}

export interface AnalysisPacket {
  portfolioItemId: string;
  name: string;
  symbol: string;
  market: string;
  assetType: string;
  positionStatus: PositionStatus;
  trackingStatus: TrackingStatus;
  quantity: DecimalString;
  averageCost: DecimalString | null;
  investmentHorizon: string;
  thesis: InvestmentThesis;
  recentImpacts: PortfolioImpact[];
  decisionReview: DecisionReview;
  officialSourceLinks: SourceLink[];
  missingInformation: string[];
  questionsForChatgpt: string[];
  copyText: string;
  articleFullTextIncluded: false;
  humanDecisionRequired: true;
}

export interface EconomicEvent {
  id: string;
  eventType: string;
  title: string;
  scheduledAt: string;
  officialSourceName: string;
  officialSourceUrl: string;
  relatedPortfolioItemIds: string[];
  expectedImpactPath: string[];
  preReleaseChecks: string[];
  actualResult: string | null;
  changed: boolean;
  createdAt: string;
  updatedAt: string;
}



export interface EconomicEventImportInput {
  eventType: string;
  title: string;
  scheduledAt: string;
  officialSourceName: string;
  officialSourceUrl: string;
  portfolioItemIds: string[];
  expectedImpactPath: string[];
  preReleaseChecks: string[];
  officialSourceConfirmed: boolean;
  confirm: boolean;
}

export interface EconomicEventImportPortfolioItem {
  id: string;
  symbol: string;
  name: string;
  market: string;
}

export interface EconomicEventImportDuplicate {
  duplicate: boolean;
  existingEventId: string | null;
}

export interface EconomicEventImportPreview {
  normalizedUrl: string;
  sourceDomain: string;
  scheduledAt: string;
  portfolioItems: EconomicEventImportPortfolioItem[];
  duplicate: EconomicEventImportDuplicate;
  officialSourceConfirmed: boolean;
  validationWarnings: string[];
  wouldCreate: boolean;
  canConfirm: boolean;
  confirmed: false;
}

export interface EconomicEventImportConfirmed {
  event: EconomicEvent;
  portfolioItems: EconomicEventImportPortfolioItem[];
  validationWarnings: string[];
  confirmed: true;
}

export type EconomicEventImportResult =
  | EconomicEventImportPreview
  | EconomicEventImportConfirmed;

export interface RiskProfile {
  maxPositionPercent: DecimalString | null;
  maxPortfolioLossPercent: DecimalString | null;
  defaultStopLossPercent: DecimalString | null;
  defaultTakeProfitPercent: DecimalString | null;
  maxSingleTradeAmount: DecimalString | null;
  cashReservePercent: DecimalString | null;
  allowAveragingDown: boolean;
  recommendationMode: RecommendationMode;
  riskStyle: RiskStyle | null;
  primaryGoal: PrimaryGoal | null;
  defaultInvestmentHorizon: InvestmentHorizon | null;
  maxSinglePositionPercent: DecimalString | null;
  portfolioLossReviewPercent: DecimalString | null;
  defaultLossReviewPercent: DecimalString | null;
  defaultProfitReviewPercent: DecimalString | null;
  minimumCashPercent: DecimalString | null;
  maxSingleAdditionalBuyPercent: DecimalString | null;
  averagingDownPolicy: AveragingDownPolicy | null;
  maxAveragingDownCount: number | null;
  requireOfficialEvidenceForAveragingDown: boolean | null;
  highVolatilityAssetLimitPercent: DecimalString | null;
  cryptoAssetLimitPercent: DecimalString | null;
  notes: string | null;
  acknowledgedAt: string | null;
  source: RiskProfileSource;
  portfolioFingerprint: string | null;
  recommendationVersion: string | null;
  createdAt: string;
  updatedAt: string;
}

export type RiskProfileInput = Partial<
  Omit<
    RiskProfile,
    | "createdAt"
    | "updatedAt"
    | "source"
    | "portfolioFingerprint"
    | "recommendationVersion"
  >
>;

export interface RiskProfileResponse {
  configured: boolean;
  profile: RiskProfile | null;
}

export interface RiskRecommendationAnswers {
  fundsNeededWithinOneYear?: ConfirmationAnswer | null;
  acceptableLossRange?: AcceptableLossRange | null;
  emergencyFund?: ConfirmationAnswer | null;
  averagingDownPreference?: AveragingDownPolicy | null;
}

export interface RiskRecommendationDataCoverage {
  basis: "PURCHASE_COST_BY_CURRENCY";
  portfolioCount: number;
  holdingCount: number;
  transactionCount: number;
  additionalBuyCount: number;
  cryptoPositionCount: number;
  structuralHighVolatilityCount: number;
  currencies: string[];
  costBasisByCurrency: Record<string, string>;
  maxCostConcentrationPercent: DecimalString | null;
  maxCryptoCostSharePercent: DecimalString | null;
  totalRealizedPnlByCurrency: Record<string, string>;
  assetTypeCounts: Record<string, number>;
  investmentHorizonCounts: Record<string, number>;
  positionStatusCounts: Record<string, number>;
  trackingStatusCounts: Record<string, number>;
  partialSellCount: number;
  fullSellCount: number;
  marketPriceProviderConfigured: boolean;
  partialMarketPriceCoverage: boolean;
  quotedCryptoPositionCount: number;
  volatilityProviderConfigured: false;
}

export interface RiskProfileRecommendation {
  suggestedRiskStyle: Exclude<RiskStyle, "CUSTOM">;
  maxSinglePositionPercent: DecimalString;
  portfolioLossReviewPercent: DecimalString;
  defaultLossReviewPercent: DecimalString;
  defaultProfitReviewPercent: DecimalString;
  minimumCashPercent: DecimalString | null;
  maxSingleAdditionalBuyPercent: DecimalString;
  averagingDownPolicy: AveragingDownPolicy;
  maxAveragingDownCount: number;
  requireOfficialEvidenceForAveragingDown: boolean;
  highVolatilityAssetLimitPercent: DecimalString;
  cryptoAssetLimitPercent: DecimalString;
  confidence: RiskRecommendationConfidence;
  dataCoverage: RiskRecommendationDataCoverage;
  reasons: string[];
  missingInputs: string[];
  generatedAt: string;
  portfolioFingerprint: string;
  recommendationVersion: string;
  riskProfileConfigured: boolean;
  profilePortfolioFingerprint: string | null;
  portfolioChanged: boolean;
}

export interface RiskRecommendationOption {
  value: string;
  label: string;
  description: string;
}

export interface RiskRecommendationQuestion {
  id: keyof RiskRecommendationAnswers;
  prompt: string;
  options: RiskRecommendationOption[];
}

export interface RiskRecommendationQuestions {
  items: RiskRecommendationQuestion[];
}

export interface RiskRecommendationApplyInput {
  answers: RiskRecommendationAnswers;
  expectedPortfolioFingerprint: string;
  recommendationVersion: string;
  mode: "ALL" | "CHANGED_ONLY";
}

export interface RiskRecommendationApplyResponse {
  recommendation: RiskProfileRecommendation;
  profile: RiskProfile;
}

export interface ApiErrorIssue {
  location: string[];
  message: string;
  type: string;
}

export interface ApiError {
  code: string;
  message: string;
  details: {
    issues?: ApiErrorIssue[];
    [key: string]: unknown;
  };
}

export interface ApiErrorResponse {
  error: ApiError;
}

export interface SystemInfo {
  environment: string;
  databaseConfigured: boolean;
  databaseReachable: boolean;
  databaseType: "NOT_CONFIGURED" | "SQLITE" | "POSTGRESQL" | "OTHER";
  emailConfigured: boolean;
  schedulerConfigured: boolean;
  marketProvidersConfigured: boolean;
  newsProvidersConfigured: boolean;
  retentionCleanupEnabled: boolean;
  newsConfigured: boolean;
  newsSyncEnabled: boolean;
  newsProviderStatus: string;
  configuredNewsSourceCount: number;
  enabledNewsSourceCount: number;
  lastNewsSyncAt: string | null;
  lastSuccessfulNewsSyncAt: string | null;
  newsDatabaseCount: number;
  duplicateNewsCount: number;
  staleReusedCount: number;
  correctedNewsCount: number;
  deniedNewsCount: number;
  rawNewsTtlHours: number;
  emailProviderStatus: string;
  lastEmailSentAt: string | null;
  monthlyAppEmailSentCount: number;
  lastRadarCycleAt: string | null;
  averageRunDurationSeconds: number | null;
  collectionSuccessRate: number | null;
  delayedRunCount: number;
  databaseBytesAvailability: Availability;
  databaseBytes: number | null;
  operatingMode: OperatingMode;
  budgetConfigured: boolean;
  retentionAutoConfirm: boolean;
  lastCleanupAt: string | null;
  nextCleanupScheduled: boolean;
  githubActionsUsageConnected: boolean;
  marketCalendarConfigured: boolean;
  krxCalendarStatus: MarketScheduleStatus;
  nasdaqCalendarStatus: MarketScheduleStatus;
  nextMarketBriefing: string | null;
  enabledMarketBriefingCount: number;
  lastKrxBriefing: string | null;
  lastNasdaqBriefing: string | null;
  riskProfileConfigured: boolean;
  riskRecommendationAvailable: boolean;
  riskRecommendationConfidence: RiskRecommendationConfidence | null;
  riskRecommendationStale: boolean;
  portfolioFingerprintChanged: boolean;
  openDartConfigured: boolean;
  secConfigured: boolean;
  openDartStatus: string;
  secStatus: string;
  upbitPublicQuoteStatus: string;
  binancePublicQuoteStatus: string;
  lastProviderSyncAt: string | null;
  providerSuccessRate: number | null;
  latestQuoteCount: number;
  verifiedMappingCount: number;
  unresolvedMappingCount: number;
  staleMappingCount: number;
  disclosureDatabaseCount: number;
  eventCount: number;
  aiAutomationEnabled: false;
  automaticTradingEnabled: false;
  version: string;
  time: string;
}

export interface ProviderStatus {
  provider: string;
  capability: string;
  configured: boolean;
  status: string;
  lastSuccessAt: string | null;
  lastErrorCode: string | null;
  consecutiveFailures: number;
  requestCount: number;
  successCount: number;
}

export interface ProviderStatusList {
  items: ProviderStatus[];
  verifiedMappingCount: number;
  unresolvedMappingCount: number;
  conflictingMappingCount: number;
  staleMappingCount: number;
  recentDisclosureCount: number;
  latestQuoteCount: number;
}

export interface InstrumentMapping {
  id: string;
  instrumentId: string;
  provider: string;
  providerInstrumentId: string;
  providerSymbol: string | null;
  cik: string | null;
  corpCode: string | null;
  stockCode: string | null;
  canonicalSymbol: string;
  exchange: string | null;
  officialName: string | null;
  mappingStatus: string;
  matchMethod: string;
  confidence: number;
  sourceUrl: string;
  sourceUpdatedAt: string | null;
  verifiedAt: string | null;
  lastCheckedAt: string | null;
  conflictReason: string | null;
}

export interface PublicQuoteSnapshot {
  id: string;
  instrumentId: string;
  provider: string;
  providerSymbol: string;
  price: string;
  quoteCurrency: Currency;
  providerEventAt: string;
  fetchedAt: string;
  freshnessStatus: "LIVE" | "RECENT" | "DELAYED" | "STALE" | "UNAVAILABLE";
  sourceStatus: string;
  sequence: number;
}

export interface PortfolioQuote {
  portfolioId: string;
  quoteStatus: string;
  providerConfigured: boolean;
  quote: PublicQuoteSnapshot | null;
}

export interface RelatedInstrument {
  id: string;
  canonicalSymbol: string;
  displayName: string;
  market: string;
}

export interface OfficialReference {
  id: string;
  title: string;
  officialUrl: string;
  provider: string;
}

export interface NewsReference {
  id: string;
  title: string;
  sourceName: string;
  sourceDomain: string;
  sourceGrade: SourceGrade;
  originalUrl: string;
  canonicalUrl: string;
  publishedAt: string;
  firstSeenAt: string;
  lastSeenAt: string;
  shortSummary: string | null;
  summaryStatus: string;
  primaryClaim: string;
  certaintyLevel: CertaintyLevel;
  verificationStatus: VerificationStatus;
  trustScore: number;
  trustScoreExplanation: string;
  independentOrigin: boolean;
  duplicateOfId: string | null;
  materialChange: boolean;
  staleReused: boolean;
  lifecycleStatus: LifecycleStatus;
  informationEventId: string;
  relatedInstrument: RelatedInstrument | null;
  officialReferences: OfficialReference[];
  changedFacts: Array<Record<string, unknown>>;
}

export interface NewsListResponse {
  items: NewsReference[];
  total: number;
  limit: number;
  offset: number;
}

export interface ImportantInformationImportInput {
  sourceUrl: string;
  publisherName: string;
  title: string;
  publishedAt: string;
  primaryClaim: string;
  publicSummary: string | null;
  portfolioItemId: string;
  language: string;
  materialChange: boolean;
  confirm: boolean;
}

export interface ImportantInformationImportPortfolioItem {
  id: string;
  symbol: string;
  name: string;
  market: string;
}

export interface ImportantInformationImportDuplicate {
  duplicate: boolean;
  existingReferenceId: string | null;
}

export interface ImportantInformationImportClassification {
  sourceName: string;
  sourceDomain: string;
  sourceGrade: SourceGrade;
  officialSource: boolean;
  predictedVerificationStatus: VerificationStatus;
}

export interface ImportantInformationImportPreview {
  normalizedUrl: string;
  portfolioItem: ImportantInformationImportPortfolioItem;
  duplicate: ImportantInformationImportDuplicate;
  classification: ImportantInformationImportClassification;
  wouldCreateSource: boolean;
  wouldCreateInstrument: boolean;
  validationWarnings: string[];
  wouldCreate: boolean;
  confirmed: false;
}

export interface ImportantInformationImportConfirmed {
  normalizedUrl: string;
  reference: NewsReference;
  informationEventId: string;
  sourceCreated: boolean;
  instrumentCreated: boolean;
  validationWarnings: string[];
  confirmed: true;
}

export type ImportantInformationImportResult =
  | ImportantInformationImportPreview
  | ImportantInformationImportConfirmed;


export interface OfficialDisclosureImportInput {
  officialUrl: string;
  title: string;
  publishedAt: string;
  claim: string;
  summary: string | null;
  portfolioItemId: string;
  formType: string | null;
  materialChange: boolean;
  confirm: boolean;
}

export interface OfficialDisclosureImportPortfolioItem {
  id: string;
  symbol: string;
  name: string;
  market: string;
}

export interface OfficialDisclosureImportDuplicate {
  duplicate: boolean;
  existingDisclosureId: string | null;
}

export interface OfficialDisclosureImportClassification {
  provider: "OPENDART" | "SEC_EDGAR";
  providerLabel: string;
  sourceGrade: SourceGrade;
  predictedVerificationStatus: VerificationStatus;
}

export interface OfficialDisclosureImportPreview {
  normalizedUrl: string;
  providerDocumentId: string;
  portfolioItem: OfficialDisclosureImportPortfolioItem;
  duplicate: OfficialDisclosureImportDuplicate;
  classification: OfficialDisclosureImportClassification;
  wouldCreateInstrument: boolean;
  validationWarnings: string[];
  wouldCreate: boolean;
  confirmed: false;
}

export interface OfficialDisclosureImportConfirmed {
  normalizedUrl: string;
  disclosure: Disclosure;
  informationEventId: string;
  instrumentCreated: boolean;
  validationWarnings: string[];
  confirmed: true;
}

export type OfficialDisclosureImportResult =
  | OfficialDisclosureImportPreview
  | OfficialDisclosureImportConfirmed;

export interface Disclosure {
  id: string;
  eventId: string;
  provider: string;
  formType: string | null;
  reportType: string | null;
  title: string;
  companyName: string;
  officialUrl: string;
  publishedAt: string;
  verificationStatus: VerificationStatus;
  sourceGrade: SourceGrade;
  summary: string | null;
  summaryStatus: string;
  keyFacts: Array<Record<string, unknown>>;
  materialChange: boolean;
  correctionOfId: string | null;
  lifecycleStatus: LifecycleStatus;
  relatedInstrument: RelatedInstrument | null;
  relatedPortfolioItems: Array<{
    id: string;
    name: string;
    symbol: string;
    positionStatus: PositionStatus;
    trackingStatus: TrackingStatus;
  }>;
}

export interface DisclosureListResponse {
  items: Disclosure[];
  total: number;
  limit: number;
  offset: number;
}

export interface InformationEvent {
  id: string;
  eventType: string;
  normalizedClaim: string;
  firstSeenAt: string;
  lastSeenAt: string;
  latestMaterialChangeAt: string | null;
  lifecycleStatus: LifecycleStatus;
  verificationStatus: VerificationStatus;
  sourceCount: number;
  officialSourceCount: number;
  newsReferenceCount: number;
  independentOriginCount: number;
  staleReuseCount: number;
  latestNewsAt: string | null;
  latestOfficialAt: string | null;
  changedFacts: Array<Record<string, unknown>>;
  correctedAt: string | null;
  deniedAt: string | null;
  currentSummary: string | null;
  materialChange: boolean;
  relatedInstrument?: RelatedInstrument | null;
  officialReferences?: Disclosure[];
  newsReferences?: Array<{
    id: string;
    title: string;
    sourceName: string;
    canonicalUrl: string;
    publishedAt: string;
    verificationStatus: VerificationStatus;
    materialChange: boolean;
    staleReused: boolean;
    independentOrigin: boolean;
  }>;
}

export interface EventListResponse {
  items: InformationEvent[];
  total: number;
  limit: number;
  offset: number;
}

export type BriefingStatus =
  | "DRAFT"
  | "READY"
  | "SKIPPED_NO_CHANGE"
  | "SENT"
  | "PARTIALLY_SENT"
  | "FAILED"
  | "EXPIRED";
export type OperatingMode =
  | "NORMAL"
  | "WARNING"
  | "SAVING"
  | "MINIMAL"
  | "PAUSED";
export type Availability =
  | "AVAILABLE"
  | "ESTIMATED"
  | "NOT_CONFIGURED"
  | "NOT_AVAILABLE";

export interface BriefingItem {
  id: string;
  informationEventId: string;
  priority: number;
  category: string;
  headline: string;
  shortSummary: string;
  verificationStatus: VerificationStatus;
  trustScore: number;
  trustScoreExplanation: string;
  materialChange: boolean;
  changedFacts: Array<Record<string, unknown>>;
  sourceLinks: Array<{ title: string; url: string }>;
  officialReferenceLinks: Array<{ title: string; url: string }>;
  publishedAt: string;
  portfolioItemId: string | null;
  portfolioName: string | null;
  currentStatus: string | null;
  managementDirection: DecisionDirection;
  importance: number;
  whatHappened: string;
  officialConfirmation: string;
  thesisEffect: string;
  positiveFactors: string[];
  negativeFactors: string[];
  conditionsToAdd: string[];
  conditionsToReduce: string[];
  conditionsToExit: string[];
  nextInformation: string[];
  invalidationConditions: string[];
  informationValidUntil: string | null;
  humanDecisionRequired: true;
}

export interface Briefing {
  id: string;
  briefingType: string;
  status: BriefingStatus;
  periodStart: string;
  periodEnd: string;
  generatedAt: string;
  title: string;
  compactSummary: string;
  itemCount: number;
  materialChangeCount: number;
  correctionCount: number;
  denialCount: number;
  officialConfirmedCount: number;
  needsVerificationCount: number;
  relatedInstrumentIds: string[];
  validUntil: string;
  items: BriefingItem[];
}

export interface BriefingListResponse {
  items: Briefing[];
  total: number;
  limit: number;
  offset: number;
  emailConfigured: boolean;
}



export interface BriefingGenerationInput {
  periodStart: string;
  periodEnd: string;
  minimumPriority: number;
  includedItemsConfirmed: boolean;
  confirm: boolean;
}

export interface BriefingGenerationPreview {
  briefing: Briefing;
  excludedDuplicates: number;
  existingBriefingId: string | null;
  wouldCreate: boolean;
  canConfirm: boolean;
  confirmed: false;
  persisted: false;
  emailDeliveryCreated: false;
}

export interface BriefingGenerationConfirmed {
  briefing: Briefing;
  excludedDuplicates: number;
  created: true;
  confirmed: true;
  persisted: true;
  emailDeliveryCreated: false;
}

export type BriefingGenerationResult =
  | BriefingGenerationPreview
  | BriefingGenerationConfirmed;


export interface NotificationPreferenceInput {
  enabled: boolean;
  hourlyChangeBriefingEnabled: boolean;
  dailyDigestEnabled: boolean;
  krxPreOpenEnabled: boolean;
  krxPostCloseEnabled: boolean;
  nasdaqPreOpenEnabled: boolean;
  nasdaqPostCloseEnabled: boolean;
  immediateMaterialChangeEnabled: boolean;
  correctionNoticeEnabled: boolean;
  providerFailureNoticeEnabled: boolean;
  recipientEmail?: string | null;
  timezone: string;
  dailyDigestHour: number;
  minimumPriority: number;
  includeWatchlist: boolean;
  includeReentryWatch: boolean;
  includeSold: boolean;
  sendNoMaterialChangeBriefing: boolean;
  krxPreOpenOffsetMinutes: number;
  krxPostCloseOffsetMinutes: number;
  nasdaqPreOpenOffsetMinutes: number;
  nasdaqPostCloseOffsetMinutes: number;
}

export interface NotificationPreference {
  configured: boolean;
  emailProviderStatus: string;
  enabled: boolean;
  hourlyChangeBriefingEnabled: boolean;
  dailyDigestEnabled: boolean;
  krxPreOpenEnabled: boolean;
  krxPostCloseEnabled: boolean;
  nasdaqPreOpenEnabled: boolean;
  nasdaqPostCloseEnabled: boolean;
  immediateMaterialChangeEnabled: boolean;
  correctionNoticeEnabled: boolean;
  providerFailureNoticeEnabled: boolean;
  recipientEmailMasked: string | null;
  timezone: string;
  dailyDigestHour: number;
  minimumPriority: number;
  includeWatchlist: boolean;
  includeReentryWatch: boolean;
  includeSold: boolean;
  includeHoldings: true;
  sendNoMaterialChangeBriefing: boolean;
  krxPreOpenOffsetMinutes: number;
  krxPostCloseOffsetMinutes: number;
  nasdaqPreOpenOffsetMinutes: number;
  nasdaqPostCloseOffsetMinutes: number;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface UsageSnapshot {
  id: string | null;
  period: string;
  collectedAt: string;
  actionMinutesAvailability: Availability;
  providerReportedActionMinutes: number | null;
  locallyEstimatedComputeMinutes: number;
  databaseBytesAvailability: Availability;
  databaseBytes: number | null;
  emailCountAvailability: Availability;
  emailSentCount: number;
  collectionSuccessRate: number | null;
  scheduledRunCount: number;
  delayedRunCount: number;
  failedRunCount: number;
  averageDurationSeconds: number | null;
  operatingMode: OperatingMode;
  budgetConfigured: boolean;
  successRateFormula: string;
}

export interface UsageSnapshotList {
  items: UsageSnapshot[];
  total: number;
  limit: number;
  offset: number;
}

export interface OperationStatus {
  emailConfigured: boolean;
  emailProviderStatus: string;
  lastEmailSentAt: string | null;
  monthlyAppEmailSentCount: number;
  lastRadarCycleAt: string | null;
  lastCleanupAt: string | null;
  retentionCleanupEnabled: boolean;
  retentionAutoConfirm: boolean;
  budgetConfigured: boolean;
  actionMinutesAvailability: Availability;
  operatingMode: OperatingMode;
  githubActionsUsageConnected: boolean;
  automaticTradingEnabled: false;
  aiAutomationEnabled: false;
}

export interface NextMarketBriefing {
  briefingType: MarketBriefingType;
  market: MarketCode;
  sessionDate: string;
  marketTimezone: string;
  scheduleStatus: MarketScheduleStatus;
  scheduledAt: string | null;
  scheduledAtKst: string | null;
  offsetMinutes: number;
  enabled: boolean;
  holiday: boolean;
  earlyClose: boolean;
  source: string | null;
}

export interface NextMarketBriefingList {
  items: NextMarketBriefing[];
  calendarConfigured: boolean;
}

export interface MarketBriefingPreview {
  status: "PREVIEW";
  briefingType: MarketBriefingType;
  market: MarketCode;
  sessionDate: string;
  scheduleStatus: MarketScheduleStatus;
  investigationStart: string;
  investigationEnd: string;
  relatedInstrumentCount: number;
  officialDisclosureCount: number;
  newsReferenceCount: number;
  materialChangeCount: number;
  dataMissing: boolean;
  dataStatusMessage: string;
  emailSubject: string;
  bodySections: Array<{ title: string; content: string }>;
  sourceLinks: Array<{ title: string; url: string }>;
  persisted: false;
  deliveryCreated: false;
}

export interface MarketBriefingStatus {
  calendarConfigured: boolean;
  krxCalendarStatus: MarketScheduleStatus;
  nasdaqCalendarStatus: MarketScheduleStatus;
  nextMarketBriefing: NextMarketBriefing | null;
  enabledMarketBriefingCount: number;
  emailProviderStatus: string;
  schedulerConfigured: boolean;
  lastKrxBriefing: string | null;
  lastNasdaqBriefing: string | null;
  actualEmailSentCount: number;
}

export type AnalystPublisherType =
  | "BROKER"
  | "RESEARCH_HOUSE"
  | "FINANCIAL_MEDIA"
  | "INSTITUTION"
  | "OTHER";

export type AnalystAccessType =
  | "PUBLIC"
  | "LOGIN_REQUIRED"
  | "PAYWALLED"
  | "UNKNOWN";

export type AnalystDocumentType =
  | "REPORT"
  | "COMMENTARY"
  | "INTERVIEW"
  | "CONSENSUS"
  | "OTHER";

export type AnalystFreshnessStatus =
  | "CURRENT"
  | "AGING"
  | "STALE"
  | "UNKNOWN";

export type AnalystRelationType =
  | "PRIMARY"
  | "MENTIONED";

export type AnalystMappingConfidence =
  | "VERIFIED"
  | "NEEDS_REVIEW";

export type AnalystIngestMode =
  | "MANUAL"
  | "AUTOMATIC";

export type AnalystUserState =
  | "NEW"
  | "READ"
  | "ARCHIVED"
  | "HIDDEN";

export type ReferenceSubjectType =
  | "EXPERT"
  | "INSTITUTION"
  | "PUBLISHER";

export type ReferenceMatchMode =
  | "ALL_SOURCE"
  | "AUTHOR"
  | "KEYWORD";

export interface ReferenceSubscriptionSource {
  id: string;
  name: string;
  sourceType: string;
  sourceGrade: SourceGrade;
  domain: string;
  official: boolean;
  enabled: boolean;
  feedUrl: string | null;
  providerType: string | null;
  language: string;
  requestIntervalSeconds: number;
  timeoutSeconds: number;
  maxItems: number;
}

export interface ReferenceSubscriptionSourceListResponse {
  items: ReferenceSubscriptionSource[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReferenceSubscription {
  id: string;
  sourceId: string;
  subjectType: ReferenceSubjectType;
  displayName: string;
  matchMode: ReferenceMatchMode;
  matchTerms: string[];
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
  automaticReferenceCount: number;
  source: ReferenceSubscriptionSource;
}

export interface ReferenceSubscriptionUpdateInput {
  displayName?: string;
  matchMode?: ReferenceMatchMode;
  matchTerms?: string[];
  enabled?: boolean;
}

export interface ReferenceSubscriptionListResponse {
  items: ReferenceSubscription[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReferenceSubscriptionImportInput {
  sourceId: string;
  subjectType: ReferenceSubjectType;
  displayName: string;
  matchMode: ReferenceMatchMode;
  matchTerms: string[];
  confirm: boolean;
}

export interface ReferenceSubscriptionImportDuplicate {
  duplicate: boolean;
  existingSubscriptionId: string | null;
}

export interface ReferenceSubscriptionImportResultBase {
  normalizedDisplayName: string;
  normalizedMatchTerms: string[];
  source: ReferenceSubscriptionSource | null;
  validationWarnings: string[];
}

export interface ReferenceSubscriptionImportPreview
  extends ReferenceSubscriptionImportResultBase {
  duplicate: ReferenceSubscriptionImportDuplicate;
  wouldCreate: boolean;
  confirmed: false;
}

export interface ReferenceSubscriptionImportConfirmed
  extends ReferenceSubscriptionImportResultBase {
  subscription: ReferenceSubscription;
  confirmed: true;
}

export type ReferenceSubscriptionImportResult =
  | ReferenceSubscriptionImportPreview
  | ReferenceSubscriptionImportConfirmed;

export interface AnalystReferenceCoverage {
  id: string;
  analystReferenceId: string;
  portfolioItemId: string;
  relationType: AnalystRelationType;
  mappingConfidence: AnalystMappingConfidence;
  humanReviewRequired: boolean;
  createdAt: string;
}

export interface AnalystReference {
  id: string;
  sourceId: string | null;
  subscriptionId: string | null;
  providerItemId: string | null;
  ingestMode: AnalystIngestMode;
  userState: AnalystUserState;
  discoveredAt: string;
  publisherName: string;
  publisherType: AnalystPublisherType;
  title: string;
  analystName: string | null;
  publishedAt: string;
  canonicalUrl: string;
  accessType: AnalystAccessType;
  documentType: AnalystDocumentType;
  publisherRatingRaw: string | null;
  publisherTargetPriceRaw: string | null;
  targetCurrency: string | null;
  publicAbstract: string | null;
  sourceLanguage: string;
  translatedTitleKo: string | null;
  translatedAbstractKo: string | null;
  translationStatus: string;
  translationProvider: string | null;
  translationError: string | null;
  translatedAt: string | null;
  sourceRetrievedAt: string | null;
  sourceFingerprint: string;
  freshnessStatus: AnalystFreshnessStatus;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  coverages: AnalystReferenceCoverage[];
}

export interface AnalystReferenceListResponse {
  items: AnalystReference[];
  total: number;
  limit: number;
  offset: number;
}

export interface AnalystReferenceImportLinkInput {
  sourceUrl: string;
  publisherName: string;
  publisherType: AnalystPublisherType;
  title: string;
  analystName: string | null;
  publishedAt: string;
  accessType: AnalystAccessType;
  documentType: AnalystDocumentType;
  publisherRatingRaw: string | null;
  publisherTargetPriceRaw: string | null;
  targetCurrency: string | null;
  publicAbstract: string | null;
  portfolioItemIds: string[];
  confirm: boolean;
}

export interface AnalystReferenceImportPortfolioItem {
  id: string;
  symbol: string;
  name: string;
  market: string;
  isArchived: boolean;
}

export interface AnalystReferenceImportDuplicate {
  canonicalUrlDuplicate: boolean;
  sourceFingerprintDuplicate: boolean;
  canonicalUrlReferenceId: string | null;
  sourceFingerprintReferenceId: string | null;
}

export interface AnalystReferenceImportLinkResultBase {
  normalizedUrl: string;
  sourceFingerprint: string;
  portfolioItems: AnalystReferenceImportPortfolioItem[];
  validationWarnings: string[];
}

export interface AnalystReferenceImportLinkPreview
  extends AnalystReferenceImportLinkResultBase {
  duplicate: AnalystReferenceImportDuplicate;
  wouldCreate: boolean;
  confirmed: false;
}

export interface AnalystReferenceImportLinkConfirmed
  extends AnalystReferenceImportLinkResultBase {
  reference: AnalystReference;
  coverages: AnalystReferenceCoverage[];
  confirmed: true;
}

export type AnalystReferenceImportLinkResult =
  | AnalystReferenceImportLinkPreview
  | AnalystReferenceImportLinkConfirmed;


export interface ReferenceSourceInput {
  name: string;
  sourceGrade: SourceGrade;
  domain: string;
  official: boolean;
  enabled: boolean;
  feedUrl: string | null;
  providerType: string | null;
  language: string;
  requestIntervalSeconds: number;
  timeoutSeconds: number;
  maxItems: number;
  originalSourceName: string | null;
}

export interface ReferenceSource
  extends ReferenceSourceInput {
  id: string;
  sourceType: string;
  createdAt: string;
  updatedAt: string;
  activeSubscriptionCount: number;
  totalSubscriptionCount: number;
}

export interface ReferenceSourceListResponse {
  items: ReferenceSource[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReferenceSourceDuplicate {
  duplicate: boolean;
  existingSourceId: string | null;
  matchedFields: string[];
}

export interface ReferenceSourceImportInput
  extends ReferenceSourceInput {
  feedUrl: string;
  providerType: string;
  confirm: boolean;
}

export interface ReferenceSourceImportPreview {
  normalizedSource: ReferenceSourceInput;
  validationWarnings: string[];
  duplicate: ReferenceSourceDuplicate;
  wouldCreate: boolean;
  confirmed: false;
}

export interface ReferenceSourceImportConfirmed {
  source: ReferenceSource;
  validationWarnings: string[];
  confirmed: true;
}

export type ReferenceSourceImportResult =
  | ReferenceSourceImportPreview
  | ReferenceSourceImportConfirmed;

export interface ReferenceSourceUpdateInput {
  name?: string;
  sourceGrade?: SourceGrade;
  domain?: string;
  official?: boolean;
  enabled?: boolean;
  feedUrl?: string | null;
  providerType?: string | null;
  language?: string;
  requestIntervalSeconds?: number;
  timeoutSeconds?: number;
  maxItems?: number;
  originalSourceName?: string | null;
}

export type ReferenceSourceChangeOperation =
  | "CREATE"
  | "UPDATE";

export interface ReferenceSourceHistorySource {
  id: string;
  name: string;
  domain: string;
  official: boolean;
  enabled: boolean;
}

export interface ReferenceSourceHistorySourceListResponse {
  items: ReferenceSourceHistorySource[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReferenceSourceChange {
  id: string;
  sourceId: string;
  operation: ReferenceSourceChangeOperation;
  changedFields: string[];
  beforeValues: Record<string, unknown> | null;
  afterValues: Record<string, unknown>;
  backupPath: string | null;
  createdAt: string;
}

export interface ReferenceSourceChangeListResponse {
  items: ReferenceSourceChange[];
  total: number;
  limit: number;
  offset: number;
}

export type ReferenceDiscoveryCandidateStatus =
  | "DATE_UNVERIFIED"
  | "DATE_VERIFIED"
  | "PROMOTED"
  | "DISMISSED";

export interface ReferenceDiscoveryCandidateSource {
  id: string;
  name: string;
  domain: string;
  sourceGrade: SourceGrade;
  official: boolean;
  enabled: boolean;
  feedUrl: string | null;
}

export interface ReferenceDiscoveryCandidateSubscription {
  id: string;
  displayName: string;
  subjectType: ReferenceSubjectType;
  matchMode: ReferenceMatchMode;
  enabled: boolean;
}

export interface ReferenceDiscoveryCandidate {
  id: string;
  sourceId: string;
  subscriptionId: string;
  providerItemId: string;
  publisherName: string;
  title: string;
  analystName: string | null;
  canonicalUrl: string;
  publishedAt: string | null;
  verificationStatus: ReferenceDiscoveryCandidateStatus;
  firstSeenAt: string;
  lastSeenAt: string;
  seenCount: number;
  publicAbstract: string | null;
  publisherType: AnalystPublisherType;
  accessType: AnalystAccessType;
  documentType: AnalystDocumentType;
  promotedReferenceId: string | null;
  reviewedAt: string | null;
  createdAt: string;
  updatedAt: string;
  source: ReferenceDiscoveryCandidateSource;
  subscription: ReferenceDiscoveryCandidateSubscription;
}

export interface ReferenceDiscoveryCandidateListResponse {
  items: ReferenceDiscoveryCandidate[];
  total: number;
  limit: number;
  offset: number;
}


export type ReferenceDiscoveryCandidateReviewAction =
  | "VERIFY_DATE"
  | "PROMOTE"
  | "DISMISS";

export interface ReferenceDiscoveryCandidateVerifyDateInput {
  publishedAt: string;
  reason?: string | null;
}

export interface ReferenceDiscoveryCandidatePromoteInput {
  confirm: boolean;
  reason?: string | null;
}

export interface ReferenceDiscoveryCandidateDismissInput {
  confirm: boolean;
  reason: string;
}

export interface ReferenceDiscoveryCandidateReviewHistory {
  id: string;
  candidateId: string;
  action: ReferenceDiscoveryCandidateReviewAction;
  previousStatus: ReferenceDiscoveryCandidateStatus;
  newStatus: ReferenceDiscoveryCandidateStatus;
  verifiedPublishedAt: string | null;
  promotedReferenceId: string | null;
  reason: string | null;
  createdAt: string;
}

export interface ReferenceDiscoveryCandidateReviewHistoryListResponse {
  items: ReferenceDiscoveryCandidateReviewHistory[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReferenceDiscoveryCandidateReviewResult {
  candidate: ReferenceDiscoveryCandidate;
  history: ReferenceDiscoveryCandidateReviewHistory;
  referenceId: string | null;
  referenceCreated: boolean;
  referenceDuplicate: boolean;
}
