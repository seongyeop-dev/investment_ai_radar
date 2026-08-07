import { PageHeader } from "@/components/common/ui";
import { EventsClient } from "@/components/events/events-client";

export default function EventsPage() {
  return (
    <>
      <PageHeader
        eyebrow="통합 사건"
        title="통합 사건"
        description="반복 보도와 공식 자료를 하나의 사건 타임라인으로 묶어 최초 발견, 새 사실, 정정과 부인을 확인합니다."
      />
      <EventsClient />
    </>
  );
}
