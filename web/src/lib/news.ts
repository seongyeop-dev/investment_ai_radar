import type {
  CertaintyLevel,
  LifecycleStatus,
  VerificationStatus,
} from "@/types/api";

export const TRUST_SCORE_EXPLANATION =
  "현재 확보된 증거 강도이며 사실일 확률이 아닙니다.";

export const verificationLabels: Record<VerificationStatus, string> = {
  OFFICIAL_CONFIRMED: "공식 확인",
  MULTI_SOURCE_CONFIRMED: "복수 독립 출처 확인",
  NEEDS_VERIFICATION: "추가 검증 필요",
  UNVERIFIED: "검증 불가",
  CONFLICTING: "공식 표현과 충돌",
  OFFICIALLY_DENIED: "공식 부인",
  CORRECTED: "정정됨",
  STALE_REUSED: "과거 기사 재활용",
};

export const certaintyLabels: Record<CertaintyLevel, string> = {
  CONFIRMED: "확정",
  ANNOUNCED: "발표",
  PLANNED: "계획",
  UNDER_REVIEW: "검토 중",
  PROPOSED: "제안",
  POSSIBLE: "가능성",
  SPECULATIVE: "추정",
  UNSUPPORTED: "근거 부족",
};

export const lifecycleLabels: Record<LifecycleStatus, string> = {
  ACTIVE: "활성",
  UPDATED: "새 사실 추가",
  CORRECTED: "정정",
  DENIED: "공식 부인",
  STALE: "재탕",
  ARCHIVED: "보관",
};
