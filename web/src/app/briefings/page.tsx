import { BriefingsClient } from "@/components/briefings/briefings-client";
import { PageHeader } from "@/components/common/ui";

export default function BriefingsPage() {
  return (
    <>
      <PageHeader
        eyebrow="브리핑"
        title="변경 기반 브리핑"
        description="새로운 중요 변경과 정정·공식 부인만 묶어 표시합니다. 기사 전문은 복사하지 않습니다."
      />
      <BriefingsClient />
    </>
  );
}
