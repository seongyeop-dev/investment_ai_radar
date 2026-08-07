import { PageHeader } from "@/components/common/ui";
import { RecommendationsStatus } from "@/components/recommendations/recommendations-status";

export default function RecommendationsPage() {
  return (
    <>
      <PageHeader
        eyebrow="관리 검토"
        title="종목 관리 방향"
        description="검증 정보와 사용자 투자근거를 바탕으로 규칙 기반 검토 방향만 표시합니다. 주문 명령이 아니며 최종 판단은 사용자에게 있습니다."
      />
      <RecommendationsStatus />
    </>
  );
}
