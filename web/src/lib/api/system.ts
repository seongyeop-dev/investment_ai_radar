import { requestJson } from "@/lib/api/client";
import type { SystemInfo } from "@/types/api";

export function getSystemInfo(signal?: AbortSignal): Promise<SystemInfo> {
  return requestJson<SystemInfo>("/api/v1/system/info", { signal });
}
