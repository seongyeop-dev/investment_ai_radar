import { requestJson } from "@/lib/api/client";
import type {
  HistoricalPortfolioInput,
  HistoricalPortfolioResponse,
  PortfolioCreateInput,
  PortfolioContextInput,
  PortfolioItem,
  PortfolioListFilters,
  PortfolioListResponse,
  PortfolioSummary,
  PortfolioUpdateInput,
  HistoricalTransactionInput,
  PositionSummary,
  PositionTransaction,
  PositionTransactionInput,
  PositionTransactionListResponse,
  PositionTransactionUpdateInput,
  SaleCreateInput,
  SaleListResponse,
  SaleSummary,
  SaleTransaction,
  SaleUpdateInput,
} from "@/types/api";

export function listPortfolio(
  filters: PortfolioListFilters = {},
  signal?: AbortSignal,
): Promise<PortfolioListResponse> {
  const params = new URLSearchParams();
  if (filters.holdingStatus) {
    params.set("holdingStatus", filters.holdingStatus);
  }
  if (filters.positionStatus) {
    params.set("positionStatus", filters.positionStatus);
  }
  if (filters.trackingStatus) {
    params.set("trackingStatus", filters.trackingStatus);
  }
  if (filters.market?.trim()) {
    params.set("market", filters.market.trim());
  }
  if (filters.query?.trim()) {
    params.set("query", filters.query.trim());
  }
  if (filters.includeArchived) {
    params.set("includeArchived", "true");
  }
  params.set("limit", String(filters.limit ?? 100));
  params.set("offset", String(filters.offset ?? 0));
  const query = params.toString();
  return requestJson<PortfolioListResponse>(
    `/api/v1/portfolio${query ? `?${query}` : ""}`,
    { signal },
  );
}

export function getPortfolioSummary(
  signal?: AbortSignal,
): Promise<PortfolioSummary> {
  return requestJson<PortfolioSummary>("/api/v1/portfolio/summary", { signal });
}

export function updatePortfolioContext(
  id: string,
  input: PortfolioContextInput,
  signal?: AbortSignal,
): Promise<PortfolioItem> {
  return requestJson<PortfolioItem>(`/api/v1/portfolio/${id}/context`, {
    method: "PATCH",
    body: JSON.stringify(input),
    signal,
  });
}

export function createPortfolio(
  input: PortfolioCreateInput,
  signal?: AbortSignal,
): Promise<PortfolioItem> {
  return requestJson<PortfolioItem>("/api/v1/portfolio", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function getPortfolio(
  id: string,
  signal?: AbortSignal,
): Promise<PortfolioItem> {
  return requestJson<PortfolioItem>(`/api/v1/portfolio/${id}`, { signal });
}

export function updatePortfolio(
  id: string,
  input: PortfolioUpdateInput,
  signal?: AbortSignal,
): Promise<PortfolioItem> {
  return requestJson<PortfolioItem>(`/api/v1/portfolio/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
    signal,
  });
}

export function archivePortfolio(
  id: string,
  signal?: AbortSignal,
): Promise<void> {
  return requestJson<void>(`/api/v1/portfolio/${id}`, {
    method: "DELETE",
    signal,
  });
}

export function restorePortfolio(
  id: string,
  signal?: AbortSignal,
): Promise<PortfolioItem> {
  return requestJson<PortfolioItem>(`/api/v1/portfolio/${id}/restore`, {
    method: "POST",
    signal,
  });
}

export function listSales(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<SaleListResponse> {
  return requestJson<SaleListResponse>(
    `/api/v1/portfolio/${portfolioId}/sales`,
    { signal },
  );
}

export function createSale(
  portfolioId: string,
  input: SaleCreateInput,
  signal?: AbortSignal,
): Promise<SaleTransaction> {
  return requestJson<SaleTransaction>(
    `/api/v1/portfolio/${portfolioId}/sales`,
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function createHistoricalSale(
  portfolioId: string,
  input: SaleCreateInput,
  signal?: AbortSignal,
): Promise<SaleTransaction> {
  return requestJson<SaleTransaction>(
    `/api/v1/portfolio/${portfolioId}/historical-sales`,
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function updateSale(
  portfolioId: string,
  saleId: string,
  input: SaleUpdateInput,
  signal?: AbortSignal,
): Promise<SaleTransaction> {
  return requestJson<SaleTransaction>(
    `/api/v1/portfolio/${portfolioId}/sales/${saleId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function voidSale(
  portfolioId: string,
  saleId: string,
  reason: string,
  signal?: AbortSignal,
): Promise<SaleTransaction> {
  return requestJson<SaleTransaction>(
    `/api/v1/portfolio/${portfolioId}/sales/${saleId}/void`,
    {
      method: "POST",
      body: JSON.stringify({ reason }),
      signal,
    },
  );
}

export function getSaleSummary(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<SaleSummary> {
  return requestJson<SaleSummary>(
    `/api/v1/portfolio/${portfolioId}/sale-summary`,
    { signal },
  );
}

export function createHistoricalPortfolio(
  input: HistoricalPortfolioInput,
  signal?: AbortSignal,
): Promise<HistoricalPortfolioResponse> {
  return requestJson<HistoricalPortfolioResponse>(
    "/api/v1/portfolio/historical-sale",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function listPositionTransactions(
  portfolioId: string,
  includeVoided = false,
  signal?: AbortSignal,
): Promise<PositionTransactionListResponse> {
  return requestJson<PositionTransactionListResponse>(
    `/api/v1/portfolio/${portfolioId}/transactions?includeVoided=${includeVoided}`,
    { signal },
  );
}

export function createBuyTransaction(
  portfolioId: string,
  input: PositionTransactionInput,
  signal?: AbortSignal,
): Promise<PositionTransaction> {
  return requestJson<PositionTransaction>(
    `/api/v1/portfolio/${portfolioId}/transactions/buys`,
    { method: "POST", body: JSON.stringify(input), signal },
  );
}

export function createSellTransaction(
  portfolioId: string,
  input: PositionTransactionInput,
  signal?: AbortSignal,
): Promise<PositionTransaction> {
  return requestJson<PositionTransaction>(
    `/api/v1/portfolio/${portfolioId}/transactions/sells`,
    { method: "POST", body: JSON.stringify(input), signal },
  );
}

export function updatePositionTransaction(
  portfolioId: string,
  transactionId: string,
  input: PositionTransactionUpdateInput,
  signal?: AbortSignal,
): Promise<PositionTransaction> {
  return requestJson<PositionTransaction>(
    `/api/v1/portfolio/${portfolioId}/transactions/${transactionId}`,
    { method: "PATCH", body: JSON.stringify(input), signal },
  );
}

export function voidPositionTransaction(
  portfolioId: string,
  transactionId: string,
  reason: string,
  signal?: AbortSignal,
): Promise<PositionTransaction> {
  return requestJson<PositionTransaction>(
    `/api/v1/portfolio/${portfolioId}/transactions/${transactionId}/void`,
    { method: "POST", body: JSON.stringify({ reason }), signal },
  );
}

export function importHistoricalTransactions(
  portfolioId: string,
  items: HistoricalTransactionInput[],
  signal?: AbortSignal,
): Promise<PositionTransactionListResponse> {
  return requestJson<PositionTransactionListResponse>(
    `/api/v1/portfolio/${portfolioId}/transactions/historical-import`,
    { method: "POST", body: JSON.stringify({ items }), signal },
  );
}

export function getPositionSummary(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<PositionSummary> {
  return requestJson<PositionSummary>(
    `/api/v1/portfolio/${portfolioId}/position-summary`,
    { signal },
  );
}
