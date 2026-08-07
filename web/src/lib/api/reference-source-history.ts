import { requestJson } from "@/lib/api/client";
import type {
  ReferenceSourceChangeListResponse,
  ReferenceSourceHistorySourceListResponse,
} from "@/types/api";

const SOURCE_MANAGEMENT_PATH =
  "/api/v1/analyst-references/subscriptions/source-management";

export interface ReferenceSourceHistoryListFilters {
  limit?: number;
  offset?: number;
}

export function listReferenceSourceHistorySources(
  signal?: AbortSignal,
): Promise<ReferenceSourceHistorySourceListResponse> {
  const params = new URLSearchParams({
    limit: "100",
    offset: "0",
  });

  return requestJson<ReferenceSourceHistorySourceListResponse>(
    `${SOURCE_MANAGEMENT_PATH}?${params.toString()}`,
    { signal },
  );
}

export function listReferenceSourceChangeHistory(
  sourceId: string,
  filters: ReferenceSourceHistoryListFilters = {},
  signal?: AbortSignal,
): Promise<ReferenceSourceChangeListResponse> {
  const params = new URLSearchParams({
    limit: String(filters.limit ?? 50),
    offset: String(filters.offset ?? 0),
  });

  return requestJson<ReferenceSourceChangeListResponse>(
    `${SOURCE_MANAGEMENT_PATH}/${sourceId}/history?${params.toString()}`,
    { signal },
  );
}
