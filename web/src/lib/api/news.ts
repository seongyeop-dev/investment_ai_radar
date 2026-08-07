import { requestJson } from "@/lib/api/client";
import type {
  DisclosureListResponse,
  EventListResponse,
  ImportantInformationImportInput,
  ImportantInformationImportResult,
  InformationEvent,
  OfficialDisclosureImportInput,
  OfficialDisclosureImportResult,
  NewsListResponse,
  NewsReference,
} from "@/types/api";

function queryString(values: Record<string, string | number | boolean | undefined>) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export function listNews(
  filters: Record<string, string | number | boolean | undefined> = {},
  signal?: AbortSignal,
) {
  return requestJson<NewsListResponse>(`/api/v1/news${queryString(filters)}`, {
    signal,
  });
}

export function getNews(id: string, signal?: AbortSignal) {
  return requestJson<NewsReference>(`/api/v1/news/${id}`, { signal });
}

export function importImportantInformation(
  input: ImportantInformationImportInput,
  signal?: AbortSignal,
) {
  return requestJson<ImportantInformationImportResult>(
    "/api/v1/news/import-link",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}



export function importOfficialDisclosure(
  input: OfficialDisclosureImportInput,
  signal?: AbortSignal,
) {
  return requestJson<OfficialDisclosureImportResult>(
    "/api/v1/disclosures/import-link",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}
export function listDisclosures(signal?: AbortSignal) {
  return requestJson<DisclosureListResponse>("/api/v1/disclosures?limit=100", {
    signal,
  });
}

export function listEvents(signal?: AbortSignal) {
  return requestJson<EventListResponse>(
    "/api/v1/information-events?limit=100",
    { signal },
  );
}

export function getEvent(id: string, signal?: AbortSignal) {
  return requestJson<InformationEvent>(`/api/v1/information-events/${id}`, {
    signal,
  });
}
