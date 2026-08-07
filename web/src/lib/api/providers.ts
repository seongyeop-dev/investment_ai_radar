import { requestJson } from "@/lib/api/client";
import type {
  InstrumentMapping,
  PortfolioQuote,
  ProviderStatusList,
} from "@/types/api";

export function getProviderStatus(
  signal?: AbortSignal,
): Promise<ProviderStatusList> {
  return requestJson<ProviderStatusList>("/api/v1/providers/status", { signal });
}

export function getPortfolioMappings(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<InstrumentMapping[]> {
  return requestJson<InstrumentMapping[]>(
    `/api/v1/portfolio/${portfolioId}/mappings`,
    { signal },
  );
}

export function getPortfolioQuote(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<PortfolioQuote> {
  return requestJson<PortfolioQuote>(
    `/api/v1/portfolio/${portfolioId}/quote`,
    { signal },
  );
}
