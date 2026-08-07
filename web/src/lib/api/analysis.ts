import { requestJson } from "@/lib/api/client";
import type {
  AnalysisPacket,
  DecisionReview,
  EconomicEvent,
  EconomicEventImportInput,
  EconomicEventImportResult,
  InvestmentThesis,
  InvestmentThesisInput,
  PortfolioImpact,
} from "@/types/api";

export function getThesis(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<InvestmentThesis> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/thesis`, { signal });
}

export function saveThesis(
  portfolioId: string,
  input: InvestmentThesisInput,
  signal?: AbortSignal,
): Promise<InvestmentThesis> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/thesis`, {
    method: "PUT",
    body: JSON.stringify(input),
    signal,
  });
}

export async function getImpacts(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<PortfolioImpact[]> {
  const response = await requestJson<{ items: PortfolioImpact[] }>(
    `/api/v1/portfolio/${portfolioId}/impacts`,
    { signal },
  );
  return response.items;
}

export async function getAllImpacts(
  signal?: AbortSignal,
): Promise<PortfolioImpact[]> {
  const response = await requestJson<{ items: PortfolioImpact[] }>(
    "/api/v1/impacts",
    { signal },
  );
  return response.items;
}

export function getDecisionReview(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<DecisionReview> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/decision-review`, {
    signal,
  });
}

export async function getDecisionReviews(
  signal?: AbortSignal,
): Promise<DecisionReview[]> {
  const response = await requestJson<{ items: DecisionReview[] }>(
    "/api/v1/decision-reviews",
    { signal },
  );
  return response.items;
}

export function refreshDecisionReview(
  portfolioId: string,
  manualReferencePrice: string | null = null,
  signal?: AbortSignal,
): Promise<DecisionReview> {
  return requestJson(
    `/api/v1/portfolio/${portfolioId}/decision-review/refresh`,
    {
      method: "POST",
      body: JSON.stringify({ manualReferencePrice }),
      signal,
    },
  );
}

export function acknowledgeDecisionReview(
  portfolioId: string,
  userDecision: string,
  signal?: AbortSignal,
): Promise<DecisionReview> {
  return requestJson(
    `/api/v1/portfolio/${portfolioId}/decision-review/acknowledge`,
    {
      method: "POST",
      body: JSON.stringify({ userDecision }),
      signal,
    },
  );
}

export function getAnalysisPacket(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<AnalysisPacket> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/analysis-packet`, {
    signal,
  });
}

export async function getEconomicEvents(
  upcoming = false,
  signal?: AbortSignal,
): Promise<EconomicEvent[]> {
  const suffix = upcoming ? "/upcoming" : "";
  const response = await requestJson<{ items: EconomicEvent[] }>(
    `/api/v1/economic-events${suffix}`,
    { signal },
  );
  return response.items;
}

export function importEconomicEvent(
  input: EconomicEventImportInput,
  signal?: AbortSignal,
): Promise<EconomicEventImportResult> {
  return requestJson<EconomicEventImportResult>(
    "/api/v1/economic-events/import-link",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}
