import { PageHeader } from "@/components/common/ui";
import { DisclosureClient } from "@/components/disclosures/disclosure-client";

export default function DisclosuresPage() {
  return (
    <>
      <PageHeader
        eyebrow="공식 공시"
        title="공식 공시"
        description="OpenDART·SEC 공식 원문 링크를 웹에서 등록 전 확인하고, 구조화 요약·등록 종목·통합 사건 연결을 표시합니다."
      />
      <DisclosureClient />
    </>
  );
}
