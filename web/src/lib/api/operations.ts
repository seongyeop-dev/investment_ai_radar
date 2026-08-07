import { requestJson } from "@/lib/api/client";
import type {
  BriefingGenerationInput,
  BriefingGenerationResult,
  BriefingListResponse,
  NotificationPreference,
  NotificationPreferenceInput,
  MarketBriefingPreview,
  MarketBriefingStatus,
  MarketBriefingType,
  NextMarketBriefingList,
  OperationStatus,
  UsageSnapshotList,
} from "@/types/api";

export function getBriefings(signal?: AbortSignal): Promise<BriefingListResponse> {
  return requestJson<BriefingListResponse>("/api/v1/briefings?limit=50", {
    signal,
  });
}



export function generateBriefing(
  input: BriefingGenerationInput,
  signal?: AbortSignal,
): Promise<BriefingGenerationResult> {
  return requestJson<BriefingGenerationResult>(
    "/api/v1/briefings/generate",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function getNotificationPreference(
  signal?: AbortSignal,
): Promise<NotificationPreference> {
  return requestJson<NotificationPreference>(
    "/api/v1/notification-preferences",
    { signal },
  );
}

export function saveNotificationPreference(
  payload: NotificationPreferenceInput,
): Promise<NotificationPreference> {
  return requestJson<NotificationPreference>(
    "/api/v1/notification-preferences",
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export function getOperationStatus(
  signal?: AbortSignal,
): Promise<OperationStatus> {
  return requestJson<OperationStatus>("/api/v1/operations/status", { signal });
}

export function getUsage(signal?: AbortSignal): Promise<UsageSnapshotList> {
  return requestJson<UsageSnapshotList>("/api/v1/operations/usage?limit=1", {
    signal,
  });
}

export function getNextMarketBriefings(
  signal?: AbortSignal,
): Promise<NextMarketBriefingList> {
  return requestJson<NextMarketBriefingList>(
    "/api/v1/market-sessions/next",
    { signal },
  );
}

export function getMarketBriefingPreview(
  briefingType: MarketBriefingType,
  signal?: AbortSignal,
): Promise<MarketBriefingPreview> {
  const params = new URLSearchParams({ briefingType });
  return requestJson<MarketBriefingPreview>(
    `/api/v1/briefings/market-preview?${params.toString()}`,
    { signal },
  );
}

export function getMarketBriefingStatus(
  signal?: AbortSignal,
): Promise<MarketBriefingStatus> {
  return requestJson<MarketBriefingStatus>(
    "/api/v1/operations/market-briefing-status",
    { signal },
  );
}
