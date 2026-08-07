import { PageHeader } from "@/components/common/ui";
import { EventDetailClient } from "@/components/events/event-detail-client";

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <>
      <PageHeader
        eyebrow="사건 타임라인"
        title="사건 상세"
        description="뉴스 재게시, 새 사실, 공식 공시와 정정·부인 상태를 시간순으로 확인합니다."
      />
      <EventDetailClient id={id} />
    </>
  );
}
