import { PageHeader } from "@/components/common/ui";
import { RiskProfileSettings } from "@/components/settings/risk-profile-settings";
import { NotificationSettings } from "@/components/settings/notification-settings";

export default function SettingsPage() {
  return (
    <>
      <PageHeader
        eyebrow="개인 설정"
        title="개인 설정"
        description="추천 검토에 사용할 위험 한도를 관리합니다. API 키나 계좌 비밀정보는 브라우저에 입력하지 않습니다."
      />
      <div className="space-y-6">
        <RiskProfileSettings />
        <NotificationSettings />
      </div>
    </>
  );
}
