import { PageHeader } from "@/components/common/ui";
import { RadarStatus } from "@/components/dashboard/radar-status";

export default function DashboardPage() {
  return (
    <>
      <PageHeader
        eyebrow="오늘의 분석"
        title="오늘의 분석"
        description="새 중요 정보, 종목별 관리 방향, 투자근거 재검토 상태와 수집 품질을 확인합니다."
      />
      <RadarStatus />
    </>
  );
}
