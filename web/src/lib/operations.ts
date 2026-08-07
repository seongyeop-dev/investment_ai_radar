import type {
  Availability,
  BriefingStatus,
  OperatingMode,
} from "@/types/api";

export const briefingStatusLabels: Record<BriefingStatus, string> = {
  DRAFT: "초안",
  READY: "발송 준비",
  SKIPPED_NO_CHANGE: "새 변경 없음",
  SENT: "발송 완료",
  PARTIALLY_SENT: "일부 발송",
  FAILED: "발송 실패",
  EXPIRED: "만료",
};

export const operatingModeLabels: Record<OperatingMode, string> = {
  NORMAL: "정상",
  WARNING: "경고",
  SAVING: "절약",
  MINIMAL: "최소",
  PAUSED: "자동 조사 중지",
};

export const availabilityLabels: Record<Availability, string> = {
  AVAILABLE: "실제 측정값",
  ESTIMATED: "로컬 추정값",
  NOT_CONFIGURED: "연결 안 됨",
  NOT_AVAILABLE: "측정 불가",
};

export function maskEmail(value: string): string {
  const [local, domain] = value.trim().toLowerCase().split("@");
  if (!local || !domain) return "";
  const visible = local.length > 2 ? local.slice(0, 2) : local.slice(0, 1);
  return `${visible}***@${domain}`;
}
