import { requestJson } from "@/lib/api/client";
import type {
  AnalystReference,
  AnalystReferenceImportLinkInput,
  AnalystReferenceImportLinkResult,
  AnalystReferenceListResponse,
  ReferenceDiscoveryCandidate,
  ReferenceDiscoveryCandidateDismissInput,
  ReferenceDiscoveryCandidateListResponse,
  ReferenceDiscoveryCandidatePromoteInput,
  ReferenceDiscoveryCandidateReviewHistoryListResponse,
  ReferenceDiscoveryCandidateReviewResult,
  ReferenceDiscoveryCandidateStatus,
  ReferenceDiscoveryCandidateVerifyDateInput,
  ReferenceMatchMode,
  ReferenceSubjectType,
  ReferenceSubscription,
  ReferenceSubscriptionImportInput,
  ReferenceSubscriptionUpdateInput,
  ReferenceSubscriptionImportResult,
  ReferenceSubscriptionListResponse,
  ReferenceSubscriptionSourceListResponse,
  ReferenceSource,
  ReferenceSourceImportInput,
  ReferenceSourceImportResult,
  ReferenceSourceListResponse,
  ReferenceSourceUpdateInput,
} from "@/types/api";

export interface AnalystReferenceListFilters {
  portfolioItemId?: string;
  publisherType?: string;
  accessType?: string;
  documentType?: string;
  freshnessStatus?: string;
  includeInactive?: boolean;
  query?: string;
  limit?: number;
  offset?: number;
}

export function importAnalystReferenceLink(
  input: AnalystReferenceImportLinkInput,
  signal?: AbortSignal,
): Promise<AnalystReferenceImportLinkResult> {
  return requestJson<AnalystReferenceImportLinkResult>(
    "/api/v1/analyst-references/import-link",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export interface ReferenceSubscriptionListFilters {
  subjectType?: ReferenceSubjectType | "";
  matchMode?: ReferenceMatchMode | "";
  enabled?: boolean;
  query?: string;
  limit?: number;
  offset?: number;
}

export interface ReferenceSubscriptionSourceListFilters {
  query?: string;
  limit?: number;
  offset?: number;
}

export function importReferenceSubscription(
  input: ReferenceSubscriptionImportInput,
  signal?: AbortSignal,
): Promise<ReferenceSubscriptionImportResult> {
  return requestJson<ReferenceSubscriptionImportResult>(
    "/api/v1/analyst-references/subscriptions/import",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function listReferenceSubscriptionSources(
  filters: ReferenceSubscriptionSourceListFilters = {},
  signal?: AbortSignal,
): Promise<ReferenceSubscriptionSourceListResponse> {
  const params = new URLSearchParams();

  if (filters.query?.trim()) {
    params.set("query", filters.query.trim());
  }

  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));

  return requestJson<ReferenceSubscriptionSourceListResponse>(
    `/api/v1/analyst-references/subscriptions/sources?${params.toString()}`,
    { signal },
  );
}

export function listReferenceSubscriptions(
  filters: ReferenceSubscriptionListFilters = {},
  signal?: AbortSignal,
): Promise<ReferenceSubscriptionListResponse> {
  const params = new URLSearchParams();

  if (filters.subjectType) {
    params.set("subjectType", filters.subjectType);
  }

  if (filters.matchMode) {
    params.set("matchMode", filters.matchMode);
  }

  if (typeof filters.enabled === "boolean") {
    params.set("enabled", String(filters.enabled));
  }

  if (filters.query?.trim()) {
    params.set("query", filters.query.trim());
  }

  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));

  return requestJson<ReferenceSubscriptionListResponse>(
    `/api/v1/analyst-references/subscriptions?${params.toString()}`,
    { signal },
  );
}

export function getReferenceSubscription(
  subscriptionId: string,
  signal?: AbortSignal,
): Promise<ReferenceSubscription> {
  return requestJson<ReferenceSubscription>(
    `/api/v1/analyst-references/subscriptions/${subscriptionId}`,
    { signal },
  );
}

export function updateReferenceSubscription(
  subscriptionId: string,
  input: ReferenceSubscriptionUpdateInput,
  signal?: AbortSignal,
): Promise<ReferenceSubscription> {
  return requestJson<ReferenceSubscription>(
    `/api/v1/analyst-references/subscriptions/${subscriptionId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function listAnalystReferences(
  filters: AnalystReferenceListFilters = {},
  signal?: AbortSignal,
): Promise<AnalystReferenceListResponse> {
  const params = new URLSearchParams();

  if (filters.portfolioItemId) {
    params.set("portfolioItemId", filters.portfolioItemId);
  }
  if (filters.publisherType) {
    params.set("publisherType", filters.publisherType);
  }
  if (filters.accessType) {
    params.set("accessType", filters.accessType);
  }
  if (filters.documentType) {
    params.set("documentType", filters.documentType);
  }
  if (filters.freshnessStatus) {
    params.set("freshnessStatus", filters.freshnessStatus);
  }
  if (filters.includeInactive) {
    params.set("includeInactive", "true");
  }
  if (filters.query?.trim()) {
    params.set("query", filters.query.trim());
  }

  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));

  return requestJson<AnalystReferenceListResponse>(
    `/api/v1/analyst-references?${params.toString()}`,
    { signal },
  );
}

export function getAnalystReference(
  referenceId: string,
  signal?: AbortSignal,
): Promise<AnalystReference> {
  return requestJson<AnalystReference>(
    `/api/v1/analyst-references/${referenceId}`,
    { signal },
  );
}

export function getPortfolioAnalystReferences(
  portfolioItemId: string,
  signal?: AbortSignal,
): Promise<AnalystReferenceListResponse> {
  return requestJson<AnalystReferenceListResponse>(
    `/api/v1/analyst-references/portfolio/${portfolioItemId}`,
    { signal },
  );
}


export interface ReferenceSourceManagementListFilters {
  query?: string;
  official?: boolean;
  enabled?: boolean;
  limit?: number;
  offset?: number;
}

const REFERENCE_SOURCE_MANAGEMENT_PATH =
  "/api/v1/analyst-references/subscriptions/source-management";

export function listReferenceSourcesForManagement(
  filters: ReferenceSourceManagementListFilters = {},
  signal?: AbortSignal,
): Promise<ReferenceSourceListResponse> {
  const params = new URLSearchParams();

  if (filters.query?.trim()) {
    params.set("query", filters.query.trim());
  }

  if (typeof filters.official === "boolean") {
    params.set(
      "official",
      String(filters.official),
    );
  }

  if (typeof filters.enabled === "boolean") {
    params.set(
      "enabled",
      String(filters.enabled),
    );
  }

  params.set(
    "limit",
    String(filters.limit ?? 50),
  );
  params.set(
    "offset",
    String(filters.offset ?? 0),
  );

  return requestJson<ReferenceSourceListResponse>(
    `${REFERENCE_SOURCE_MANAGEMENT_PATH}?${params.toString()}`,
    { signal },
  );
}

export function getReferenceSourceForManagement(
  sourceId: string,
  signal?: AbortSignal,
): Promise<ReferenceSource> {
  return requestJson<ReferenceSource>(
    `${REFERENCE_SOURCE_MANAGEMENT_PATH}/${sourceId}`,
    { signal },
  );
}

export function importReferenceSource(
  input: ReferenceSourceImportInput,
  signal?: AbortSignal,
): Promise<ReferenceSourceImportResult> {
  return requestJson<ReferenceSourceImportResult>(
    `${REFERENCE_SOURCE_MANAGEMENT_PATH}/import`,
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function updateReferenceSource(
  sourceId: string,
  input: ReferenceSourceUpdateInput,
  signal?: AbortSignal,
): Promise<ReferenceSource> {
  return requestJson<ReferenceSource>(
    `${REFERENCE_SOURCE_MANAGEMENT_PATH}/${sourceId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export interface ReferenceDiscoveryCandidateListFilters {
  sourceId?: string;
  subscriptionId?: string;
  verificationStatus?: ReferenceDiscoveryCandidateStatus | "";
  query?: string;
  limit?: number;
  offset?: number;
}

const REFERENCE_DISCOVERY_CANDIDATE_PATH =
  "/api/v1/analyst-references/discovery-candidates";

export function listReferenceDiscoveryCandidates(
  filters: ReferenceDiscoveryCandidateListFilters = {},
  signal?: AbortSignal,
): Promise<ReferenceDiscoveryCandidateListResponse> {
  const params = new URLSearchParams();

  if (filters.sourceId) {
    params.set("sourceId", filters.sourceId);
  }

  if (filters.subscriptionId) {
    params.set(
      "subscriptionId",
      filters.subscriptionId,
    );
  }

  if (filters.verificationStatus) {
    params.set(
      "verificationStatus",
      filters.verificationStatus,
    );
  }

  if (filters.query?.trim()) {
    params.set("query", filters.query.trim());
  }

  params.set(
    "limit",
    String(filters.limit ?? 50),
  );
  params.set(
    "offset",
    String(filters.offset ?? 0),
  );

  return requestJson<ReferenceDiscoveryCandidateListResponse>(
    `${REFERENCE_DISCOVERY_CANDIDATE_PATH}?${params.toString()}`,
    { signal },
  );
}

export function getReferenceDiscoveryCandidate(
  candidateId: string,
  signal?: AbortSignal,
): Promise<ReferenceDiscoveryCandidate> {
  return requestJson<ReferenceDiscoveryCandidate>(
    `${REFERENCE_DISCOVERY_CANDIDATE_PATH}/${candidateId}`,
    { signal },
  );
}


export function verifyReferenceDiscoveryCandidateDate(
  candidateId: string,
  input: ReferenceDiscoveryCandidateVerifyDateInput,
  signal?: AbortSignal,
): Promise<ReferenceDiscoveryCandidateReviewResult> {
  return requestJson<ReferenceDiscoveryCandidateReviewResult>(
    `${REFERENCE_DISCOVERY_CANDIDATE_PATH}/${candidateId}/verify-date`,
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function promoteReferenceDiscoveryCandidate(
  candidateId: string,
  input: ReferenceDiscoveryCandidatePromoteInput,
  signal?: AbortSignal,
): Promise<ReferenceDiscoveryCandidateReviewResult> {
  return requestJson<ReferenceDiscoveryCandidateReviewResult>(
    `${REFERENCE_DISCOVERY_CANDIDATE_PATH}/${candidateId}/promote`,
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function dismissReferenceDiscoveryCandidate(
  candidateId: string,
  input: ReferenceDiscoveryCandidateDismissInput,
  signal?: AbortSignal,
): Promise<ReferenceDiscoveryCandidateReviewResult> {
  return requestJson<ReferenceDiscoveryCandidateReviewResult>(
    `${REFERENCE_DISCOVERY_CANDIDATE_PATH}/${candidateId}/dismiss`,
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export interface ReferenceDiscoveryCandidateReviewHistoryFilters {
  limit?: number;
  offset?: number;
}

export function listReferenceDiscoveryCandidateReviewHistory(
  candidateId: string,
  filters: ReferenceDiscoveryCandidateReviewHistoryFilters = {},
  signal?: AbortSignal,
): Promise<ReferenceDiscoveryCandidateReviewHistoryListResponse> {
  const params = new URLSearchParams();

  params.set(
    "limit",
    String(filters.limit ?? 50),
  );
  params.set(
    "offset",
    String(filters.offset ?? 0),
  );

  return requestJson<ReferenceDiscoveryCandidateReviewHistoryListResponse>(
    `${REFERENCE_DISCOVERY_CANDIDATE_PATH}/${candidateId}/review-history?${params.toString()}`,
    { signal },
  );
}
