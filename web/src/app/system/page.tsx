import { PageHeader } from "@/components/common/ui";
import { SystemInfo } from "@/components/system/system-info";

export default function SystemPage() {
  return (
    <>
      <PageHeader
        eyebrow="시스템 상태"
        title="시스템 연결 상태"
        description="실제 서버가 보고한 구성 및 연결 상태입니다. 미구성 기능은 오류가 아닌 준비 전 상태로 표시합니다."
      />
      <SystemInfo />
    </>
  );
}
