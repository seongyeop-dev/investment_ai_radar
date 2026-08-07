import { Card, EmptyState, PageHeader } from "@/components/common/ui";

export function FeaturePage({
  eyebrow,
  title,
  description,
  safetyNote,
  emptyTitle,
  emptyDetail,
  actionHref,
  actionLabel,
}: {
  eyebrow: string;
  title: string;
  description: string;
  safetyNote?: string;
  emptyTitle?: string;
  emptyDetail?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <>
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <Card>
          <EmptyState
            title={emptyTitle}
            detail={emptyDetail}
            actionHref={actionHref}
            actionLabel={actionLabel}
          />
        </Card>
        <Card title="현재 단계">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-secondary">데이터</dt>
              <dd className="font-semibold">미연결</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-secondary">검증 상태</dt>
              <dd className="font-semibold">확인 전</dd>
            </div>
          </dl>
          <p className="mt-5 border-t border-border pt-4 text-xs leading-5 text-muted">
            {safetyNote ?? "실제 출처와 데이터 계약이 준비된 뒤 연결합니다."}
          </p>
        </Card>
      </div>
    </>
  );
}
