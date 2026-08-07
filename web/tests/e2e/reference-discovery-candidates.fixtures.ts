import {
  expect,
  test as base,
  type Page,
  type Request,
  type Route,
} from "@playwright/test";

import type {
  AnalystReferenceListResponse,
  PortfolioListResponse,
  ProviderStatusList,
  ReferenceDiscoveryCandidate,
  ReferenceDiscoveryCandidateListResponse,
  ReferenceDiscoveryCandidateReviewAction,
  ReferenceDiscoveryCandidateReviewHistory,
  ReferenceDiscoveryCandidateReviewHistoryListResponse,
  ReferenceDiscoveryCandidateReviewResult,
  ReferenceDiscoveryCandidateStatus,
  ReferenceSourceListResponse,
  ReferenceSubscription,
  ReferenceSubscriptionListResponse,
  ReferenceSubscriptionSource,
  ReferenceSubscriptionSourceListResponse,
} from "../../src/types/api";

const WEB_ORIGIN = "http://127.0.0.1:4173";
const API_PREFIX = "/__frz006_api";
const CANDIDATE_PATH =
  "/api/v1/analyst-references/discovery-candidates";
const SOURCE_MANAGEMENT_PATH =
  "/api/v1/analyst-references/subscriptions/source-management";

const FIXED_TIME = "2026-08-04T00:00:00Z";

export interface MockRequestRecord {
  method: string;
  path: string;
  query: string;
  body: unknown;
}

interface Deferred {
  promise: Promise<void>;
  resolve: () => void;
}

export interface RequestGate {
  waitForRequest: () => Promise<void>;
  release: () => void;
  waitForCompletion: () => Promise<void>;
}

interface InternalGate {
  entered: Deferred;
  released: Deferred;
  completed: Deferred;
}

function deferred(): Deferred {
  let resolve = () => {};
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function createGate(): InternalGate {
  return {
    entered: deferred(),
    released: deferred(),
    completed: deferred(),
  };
}

function publicGate(gate: InternalGate): RequestGate {
  return {
    waitForRequest: () => gate.entered.promise,
    release: gate.released.resolve,
    waitForCompletion: () => gate.completed.promise,
  };
}

function source(index: number): ReferenceSubscriptionSource {
  const id = String(index).padStart(3, "0");
  return {
    id: `source-${id}`,
    name: `FRZ 출처 ${id}`,
    sourceType: "RSS",
    sourceGrade: "A",
    domain:
      index === 1
        ? `${"very-long-domain-segment-".repeat(12)}example.com`
        : `source-${id}.example.test`,
    official: true,
    enabled: true,
    feedUrl: `https://source-${id}.example.test/feed.xml`,
    providerType: "RSS",
    language: "ko",
    requestIntervalSeconds: 3600,
    timeoutSeconds: 10,
    maxItems: 50,
  } satisfies ReferenceSubscriptionSource;
}

function subscription(
  index: number,
  sources: ReferenceSubscriptionSource[],
): ReferenceSubscription {
  const id = String(index).padStart(3, "0");
  return {
    id: `subscription-${id}`,
    sourceId: sources[index - 1].id,
    subjectType: "EXPERT",
    displayName: `FRZ 구독 ${id}`,
    matchMode: "KEYWORD",
    matchTerms: [`keyword-${id}`],
    enabled: true,
    createdAt: FIXED_TIME,
    updatedAt: FIXED_TIME,
    automaticReferenceCount: 0,
    source: sources[index - 1],
  } satisfies ReferenceSubscription;
}

function initialStatus(index: number): ReferenceDiscoveryCandidateStatus {
  if (index === 3) return "DATE_VERIFIED";
  if (index === 4) return "PROMOTED";
  if (index === 5) return "DISMISSED";
  return "DATE_UNVERIFIED";
}

function candidate(
  index: number,
  sources: ReferenceSubscriptionSource[],
  subscriptions: ReferenceSubscription[],
): ReferenceDiscoveryCandidate {
  const id = String(index).padStart(3, "0");
  const verificationStatus = initialStatus(index);
  const title =
    index === 7
      ? "first-search 오래된 결과"
      : index === 8
        ? "second-search 최신 결과"
        : `FRZ 후보 ${id}`;

  return {
    id: `candidate-${id}`,
    sourceId: sources[index - 1].id,
    subscriptionId: subscriptions[index - 1].id,
    providerItemId:
      index === 1
        ? `provider-${"unbroken-segment-".repeat(24)}`
        : `provider-item-${id}`,
    publisherName: sources[index - 1].name,
    title,
    analystName: `검증 전문가 ${id}`,
    canonicalUrl:
      index === 1
        ? `https://example.test/${"very-long-url-segment-".repeat(28)}`
        : `https://example.test/references/${id}`,
    publishedAt:
      verificationStatus === "DATE_UNVERIFIED"
        ? null
        : "2026-08-03T15:30:00Z",
    verificationStatus,
    firstSeenAt: FIXED_TIME,
    lastSeenAt: FIXED_TIME,
    seenCount: index,
    publicAbstract: `공개 요약 ${id}`,
    publisherType: "RESEARCH_HOUSE",
    accessType: "PUBLIC",
    documentType: "REPORT",
    promotedReferenceId:
      verificationStatus === "PROMOTED"
        ? `reference-${id}`
        : null,
    reviewedAt:
      verificationStatus === "DATE_UNVERIFIED"
        ? null
        : FIXED_TIME,
    createdAt: FIXED_TIME,
    updatedAt: FIXED_TIME,
    source: {
      id: sources[index - 1].id,
      name: sources[index - 1].name,
      domain: sources[index - 1].domain,
      sourceGrade: sources[index - 1].sourceGrade,
      official: sources[index - 1].official,
      enabled: sources[index - 1].enabled,
      feedUrl: sources[index - 1].feedUrl,
    },
    subscription: {
      id: subscriptions[index - 1].id,
      displayName: subscriptions[index - 1].displayName,
      subjectType: subscriptions[index - 1].subjectType,
      matchMode: subscriptions[index - 1].matchMode,
      enabled: subscriptions[index - 1].enabled,
    },
  } satisfies ReferenceDiscoveryCandidate;
}

function historyItem({
  candidateId,
  action,
  previousStatus,
  newStatus,
  sequence,
  publishedAt = null,
  promotedReferenceId = null,
  reason = null,
}: {
  candidateId: string;
  action: ReferenceDiscoveryCandidateReviewAction;
  previousStatus: ReferenceDiscoveryCandidateStatus;
  newStatus: ReferenceDiscoveryCandidateStatus;
  sequence: number;
  publishedAt?: string | null;
  promotedReferenceId?: string | null;
  reason?: string | null;
}): ReferenceDiscoveryCandidateReviewHistory {
  return {
    id: `history-${candidateId}-${sequence}`,
    candidateId,
    action,
    previousStatus,
    newStatus,
    verifiedPublishedAt: publishedAt,
    promotedReferenceId,
    reason,
    createdAt: `2026-08-04T00:${String(sequence).padStart(2, "0")}:00Z`,
  } satisfies ReferenceDiscoveryCandidateReviewHistory;
}

function initialHistory(
  item: ReferenceDiscoveryCandidate,
): ReferenceDiscoveryCandidateReviewHistory[] {
  if (item.verificationStatus === "DATE_VERIFIED") {
    return [
      historyItem({
        candidateId: item.id,
        action: "VERIFY_DATE",
        previousStatus: "DATE_UNVERIFIED",
        newStatus: "DATE_VERIFIED",
        sequence: 1,
        publishedAt: item.publishedAt,
      }),
    ];
  }
  if (item.verificationStatus === "PROMOTED") {
    return [
      historyItem({
        candidateId: item.id,
        action: "VERIFY_DATE",
        previousStatus: "DATE_UNVERIFIED",
        newStatus: "DATE_VERIFIED",
        sequence: 1,
        publishedAt: item.publishedAt,
      }),
      historyItem({
        candidateId: item.id,
        action: "PROMOTE",
        previousStatus: "DATE_VERIFIED",
        newStatus: "PROMOTED",
        sequence: 2,
        promotedReferenceId: item.promotedReferenceId,
      }),
    ];
  }
  if (item.verificationStatus === "DISMISSED") {
    return [
      historyItem({
        candidateId: item.id,
        action: "DISMISS",
        previousStatus: "DATE_UNVERIFIED",
        newStatus: "DISMISSED",
        sequence: 1,
        reason: "초기 제외 fixture",
      }),
    ];
  }
  return [];
}

export class MockCandidateApi {
  readonly requests: MockRequestRecord[] = [];
  readonly unexpectedRequests: string[] = [];
  readonly externalRequests: string[] = [];
  readonly failedRequests: string[] = [];
  readonly sources = Array.from({ length: 51 }, (_, index) =>
    source(index + 1),
  );
  readonly subscriptions = Array.from({ length: 51 }, (_, index) =>
    subscription(index + 1, this.sources),
  );
  readonly candidates = Array.from({ length: 51 }, (_, index) =>
    candidate(index + 1, this.sources, this.subscriptions),
  );
  readonly history = new Map<
    string,
    ReferenceDiscoveryCandidateReviewHistory[]
  >(
    this.candidates.map((item) => [item.id, initialHistory(item)]),
  );

  candidateTotalCap: number | null = null;
  private readonly candidateGates = new Map<string, InternalGate>();
  private readonly actionGates = new Map<string, InternalGate>();

  candidateById(id: string): ReferenceDiscoveryCandidate {
    const item = this.candidates.find((value) => value.id === id);
    if (!item) throw new Error(`Unknown candidate fixture: ${id}`);
    return item;
  }

  holdCandidateQuery(query: string): RequestGate {
    const gate = createGate();
    this.candidateGates.set(query, gate);
    return publicGate(gate);
  }

  holdAction(
    action: "verify-date" | "promote" | "dismiss",
    candidateId: string,
  ): RequestGate {
    const gate = createGate();
    this.actionGates.set(`${action}:${candidateId}`, gate);
    return publicGate(gate);
  }

  requestCount(method: string, path: string): number {
    return this.requests.filter(
      (request) => request.method === method && request.path === path,
    ).length;
  }

  candidateListRequests(): MockRequestRecord[] {
    return this.requests.filter(
      (request) =>
        request.method === "GET" && request.path === CANDIDATE_PATH,
    );
  }

  async install(page: Page): Promise<void> {
    page.on("requestfailed", (request) => {
      if (request.url().startsWith(`${WEB_ORIGIN}${API_PREFIX}`)) {
        this.failedRequests.push(request.url());
      }
    });

    await page.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());

      if (url.origin !== WEB_ORIGIN) {
        if (["http:", "https:"].includes(url.protocol)) {
          this.externalRequests.push(request.url());
          await route.abort("blockedbyclient");
          return;
        }
        await route.continue();
        return;
      }

      if (!url.pathname.startsWith(`${API_PREFIX}/`)) {
        await route.continue();
        return;
      }

      await this.handleApiRoute(route, request, url);
    });
  }

  private async handleApiRoute(
    route: Route,
    request: Request,
    url: URL,
  ): Promise<void> {
    const path = url.pathname.slice(API_PREFIX.length);
    const method = request.method();
    let body: unknown = null;
    if (request.postData()) {
      try {
        body = request.postDataJSON();
      } catch {
        body = request.postData();
      }
    }
    this.requests.push({ method, path, query: url.search, body });

    if (method === "GET" && path === "/api/v1/providers/status") {
      await this.fulfill(
        route,
        {
          items: [],
          verifiedMappingCount: 0,
          unresolvedMappingCount: 0,
          conflictingMappingCount: 0,
          staleMappingCount: 0,
          recentDisclosureCount: 0,
          latestQuoteCount: 0,
        } satisfies ProviderStatusList,
      );
      return;
    }

    if (method === "GET" && path === "/api/v1/analyst-references") {
      await this.fulfill(
        route,
        { items: [], total: 0, limit: 50, offset: 0 } satisfies AnalystReferenceListResponse,
      );
      return;
    }

    if (method === "GET" && path === "/api/v1/portfolio") {
      await this.fulfill(
        route,
        { items: [], total: 0, limit: 100, offset: 0 } satisfies PortfolioListResponse,
      );
      return;
    }

    if (method === "GET" && path === SOURCE_MANAGEMENT_PATH) {
      await this.fulfill(
        route,
        { items: [], total: 0, limit: 50, offset: 0 } satisfies ReferenceSourceListResponse,
      );
      return;
    }

    if (
      method === "GET" &&
      new RegExp(`^${SOURCE_MANAGEMENT_PATH}/[^/]+/history$`).test(path)
    ) {
      await this.fulfill(
        route,
        { items: [], total: 0, limit: 50, offset: 0 },
      );
      return;
    }

    if (
      method === "GET" &&
      path === "/api/v1/analyst-references/subscriptions/sources"
    ) {
      const limit = Number(url.searchParams.get("limit") ?? 50);
      const offset = Number(url.searchParams.get("offset") ?? 0);
      await this.fulfill(
        route,
        {
          items: this.sources.slice(offset, offset + limit),
          total: this.sources.length,
          limit,
          offset,
        } satisfies ReferenceSubscriptionSourceListResponse,
      );
      return;
    }

    if (
      method === "GET" &&
      path === "/api/v1/analyst-references/subscriptions"
    ) {
      const limit = Number(url.searchParams.get("limit") ?? 50);
      const offset = Number(url.searchParams.get("offset") ?? 0);
      await this.fulfill(
        route,
        {
          items: this.subscriptions.slice(offset, offset + limit),
          total: this.subscriptions.length,
          limit,
          offset,
        } satisfies ReferenceSubscriptionListResponse,
      );
      return;
    }

    if (method === "GET" && path === CANDIDATE_PATH) {
      await this.handleCandidateList(route, url);
      return;
    }

    const historyMatch = path.match(
      new RegExp(`^${CANDIDATE_PATH}/([^/]+)/review-history$`),
    );
    if (method === "GET" && historyMatch) {
      const items = this.history.get(decodeURIComponent(historyMatch[1])) ?? [];
      await this.fulfill(
        route,
        {
          items,
          total: items.length,
          limit: 50,
          offset: 0,
        } satisfies ReferenceDiscoveryCandidateReviewHistoryListResponse,
      );
      return;
    }

    const actionMatch = path.match(
      new RegExp(`^${CANDIDATE_PATH}/([^/]+)/(verify-date|promote|dismiss)$`),
    );
    if (method === "POST" && actionMatch) {
      await this.handleAction(
        route,
        decodeURIComponent(actionMatch[1]),
        actionMatch[2] as "verify-date" | "promote" | "dismiss",
        body,
      );
      return;
    }

    const detailMatch = path.match(
      new RegExp(`^${CANDIDATE_PATH}/([^/]+)$`),
    );
    if (method === "GET" && detailMatch) {
      await this.fulfill(
        route,
        this.candidateById(decodeURIComponent(detailMatch[1])),
      );
      return;
    }

    this.unexpectedRequests.push(`${method} ${path}${url.search}`);
    await route.abort("failed");
  }

  private async handleCandidateList(route: Route, url: URL): Promise<void> {
    const query = url.searchParams.get("query")?.trim().toLowerCase() ?? "";
    const gate = this.candidateGates.get(query);
    if (gate) {
      gate.entered.resolve();
      await gate.released.promise;
    }

    const sourceId = url.searchParams.get("sourceId");
    const subscriptionId = url.searchParams.get("subscriptionId");
    const status = url.searchParams.get("verificationStatus");
    const limit = Number(url.searchParams.get("limit") ?? 50);
    const offset = Number(url.searchParams.get("offset") ?? 0);

    let items = this.candidates.filter((item) => {
      if (sourceId && item.sourceId !== sourceId) return false;
      if (subscriptionId && item.subscriptionId !== subscriptionId) return false;
      if (status && item.verificationStatus !== status) return false;
      if (!query) return true;
      return [item.title, item.analystName, item.source.domain]
        .filter(Boolean)
        .some((value) => value?.toLowerCase().includes(query));
    });
    if (this.candidateTotalCap !== null) {
      items = items.slice(0, this.candidateTotalCap);
    }

    const response = {
      items: items.slice(offset, offset + limit),
      total: items.length,
      limit,
      offset,
    } satisfies ReferenceDiscoveryCandidateListResponse;

    try {
      await this.fulfill(route, response);
    } finally {
      gate?.completed.resolve();
      if (gate) this.candidateGates.delete(query);
    }
  }

  private async handleAction(
    route: Route,
    candidateId: string,
    action: "verify-date" | "promote" | "dismiss",
    body: unknown,
  ): Promise<void> {
    const gateKey = `${action}:${candidateId}`;
    const gate = this.actionGates.get(gateKey);
    if (gate) {
      gate.entered.resolve();
      await gate.released.promise;
    }

    try {
      if (candidateId === "candidate-006") {
        await this.fulfill(
          route,
          {
            detail: {
              code: "REFERENCE_DISCOVERY_CANDIDATE_CONFLICT",
              message:
                "Reference discovery candidate was modified by another review operation.",
              reason: "STALE_VERIFICATION_STATUS",
            },
          },
          409,
        );
        return;
      }

      const item = this.candidateById(candidateId);
      const previousStatus = item.verificationStatus;
      const historyItems = this.history.get(candidateId) ?? [];
      const sequence = historyItems.length + 1;
      let history: ReferenceDiscoveryCandidateReviewHistory;

      if (action === "verify-date") {
        const input = body as { publishedAt: string; reason?: string | null };
        item.publishedAt = input.publishedAt;
        item.verificationStatus = "DATE_VERIFIED";
        item.reviewedAt = FIXED_TIME;
        item.updatedAt = `2026-08-04T01:${String(sequence).padStart(2, "0")}:00Z`;
        history = historyItem({
          candidateId,
          action: "VERIFY_DATE",
          previousStatus,
          newStatus: "DATE_VERIFIED",
          sequence,
          publishedAt: input.publishedAt,
          reason: input.reason,
        });
      } else if (action === "promote") {
        item.verificationStatus = "PROMOTED";
        item.promotedReferenceId = `reference-promoted-${candidateId}`;
        item.reviewedAt = FIXED_TIME;
        item.updatedAt = `2026-08-04T02:${String(sequence).padStart(2, "0")}:00Z`;
        history = historyItem({
          candidateId,
          action: "PROMOTE",
          previousStatus,
          newStatus: "PROMOTED",
          sequence,
          promotedReferenceId: item.promotedReferenceId,
          reason: (body as { reason?: string | null }).reason,
        });
      } else {
        item.verificationStatus = "DISMISSED";
        item.reviewedAt = FIXED_TIME;
        item.updatedAt = `2026-08-04T03:${String(sequence).padStart(2, "0")}:00Z`;
        history = historyItem({
          candidateId,
          action: "DISMISS",
          previousStatus,
          newStatus: "DISMISSED",
          sequence,
          reason: (body as { reason: string }).reason,
        });
      }

      historyItems.push(history);
      this.history.set(candidateId, historyItems);
      await this.fulfill(
        route,
        {
          candidate: item,
          history,
          referenceId: item.promotedReferenceId,
          referenceCreated: action === "promote",
          referenceDuplicate: false,
        } satisfies ReferenceDiscoveryCandidateReviewResult,
      );
    } finally {
      gate?.completed.resolve();
      this.actionGates.delete(gateKey);
    }
  }

  private async fulfill(
    route: Route,
    body: unknown,
    status = 200,
  ): Promise<void> {
    await route.fulfill({
      status,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(body),
    });
  }
}

export const test = base.extend<{ mockApi: MockCandidateApi }>({
  mockApi: async ({ page }, provide) => {
    const mockApi = new MockCandidateApi();
    await mockApi.install(page);
    await provide(mockApi);
    expect(mockApi.unexpectedRequests).toEqual([]);
    expect(mockApi.externalRequests).toEqual([]);
  },
});

export { expect };
