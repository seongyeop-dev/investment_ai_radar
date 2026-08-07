import { PageHeader } from "@/components/common/ui";
import { NewsClient } from "@/components/news/news-client";

export default function NewsPage() {
  return (
    <>
      <PageHeader
        eyebrow="중요 정보"
        title="중요 정보와 검증 상태"
        description="공개 정보와 핵심 주장을 웹에서 등록하고, 출처 등급·중복·공식 자료 교차검증과 통합 사건 연결을 확인합니다."
      />
      <NewsClient />
    </>
  );
}
