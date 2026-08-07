"use client";

import { useState } from "react";

import {
  AnalystReferenceImportDialog,
} from "@/components/sources/analyst-reference-import-dialog";

export function AnalystReferenceImportLauncher() {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <section className="mb-5 rounded-2xl border border-cyan/30 bg-cyan/5 p-4 sm:flex sm:items-center sm:justify-between sm:gap-5 sm:p-5">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan">
            전문가 참고자료
          </p>
          <h2 className="mt-1 text-lg font-bold">
            애널리스트 참고자료
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary">
            공개된 링크·제목·발행사·날짜와 공개 메타데이터만
            수동으로 등록합니다. 참고자료는 자동 분석, 관리 방향,
            투자 판단 계산에 사용되지 않습니다.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="mt-4 inline-flex min-h-11 w-full shrink-0 items-center justify-center rounded-xl bg-cyan px-5 text-sm font-bold text-background sm:mt-0 sm:w-auto"
        >
          참고자료 링크 등록
        </button>
      </section>

      {dialogOpen ? (
        <AnalystReferenceImportDialog
          onClose={() => setDialogOpen(false)}
        />
      ) : null}
    </>
  );
}
