import { PageHeader } from "@/components/common/ui";
import { AnalystReferenceImportLauncher } from "@/components/sources/analyst-reference-import-launcher";
import { AnalystReferenceListPanel } from "@/components/sources/analyst-reference-list-panel";
import { ProviderStatusClient } from "@/components/sources/provider-status-client";
import { ReferenceSourceManagementPanel } from "@/components/sources/reference-source-management-panel";
import { ReferenceDiscoveryCandidatePanel } from "@/components/sources/reference-discovery-candidate-panel";
import { ReferenceSubscriptionPanel } from "@/components/sources/reference-subscription-panel";

import { ReferenceSourceHistoryPanel } from "@/components/sources/reference-source-history-panel";

export default function SourcesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="출처·검증"
        title="출처·검증 상태"
        description="공식 공시, 기업 IR·뉴스, 시장 캘린더의 실제 설정과 최근 성공 상태를 확인합니다."
      />
      <ReferenceSourceManagementPanel />
      <ReferenceSourceHistoryPanel />
      <ReferenceSubscriptionPanel />
      <ReferenceDiscoveryCandidatePanel />
      <AnalystReferenceImportLauncher />
      <AnalystReferenceListPanel />
      <ProviderStatusClient />
    </div>
  );
}
