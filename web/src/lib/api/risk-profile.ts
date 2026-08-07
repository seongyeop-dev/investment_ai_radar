import { requestJson } from "@/lib/api/client";
import type {
  RiskProfileInput,
  RiskProfileRecommendation,
  RiskProfileResponse,
  RiskRecommendationAnswers,
  RiskRecommendationApplyInput,
  RiskRecommendationApplyResponse,
  RiskRecommendationQuestions,
} from "@/types/api";

export function getRiskProfile(
  signal?: AbortSignal,
): Promise<RiskProfileResponse> {
  return requestJson<RiskProfileResponse>("/api/v1/risk-profile", { signal });
}

export function saveRiskProfile(
  input: RiskProfileInput,
  signal?: AbortSignal,
): Promise<RiskProfileResponse> {
  return requestJson<RiskProfileResponse>("/api/v1/risk-profile", {
    method: "PUT",
    body: JSON.stringify(input),
    signal,
  });
}

export function getRiskRecommendation(
  signal?: AbortSignal,
): Promise<RiskProfileRecommendation> {
  return requestJson<RiskProfileRecommendation>(
    "/api/v1/risk-profile/recommendation",
    { signal },
  );
}

export function refreshRiskRecommendation(
  answers: RiskRecommendationAnswers,
  signal?: AbortSignal,
): Promise<RiskProfileRecommendation> {
  return requestJson<RiskProfileRecommendation>(
    "/api/v1/risk-profile/recommendation/refresh",
    {
      method: "POST",
      body: JSON.stringify({ answers }),
      signal,
    },
  );
}

export function applyRiskRecommendation(
  input: RiskRecommendationApplyInput,
  signal?: AbortSignal,
): Promise<RiskRecommendationApplyResponse> {
  return requestJson<RiskRecommendationApplyResponse>(
    "/api/v1/risk-profile/recommendation/apply",
    {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    },
  );
}

export function getRiskRecommendationQuestions(
  signal?: AbortSignal,
): Promise<RiskRecommendationQuestions> {
  return requestJson<RiskRecommendationQuestions>(
    "/api/v1/risk-profile/recommendation/questions",
    { signal },
  );
}
