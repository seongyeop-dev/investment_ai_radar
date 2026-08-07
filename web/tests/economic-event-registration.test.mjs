import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("economic event registration uses preview and final confirmation", async () => {
  const dialog = await readFile(
    new URL(
      "../src/components/macro/economic-event-import-dialog.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const page = await readFile(
    new URL("../src/app/macro/page.tsx", import.meta.url),
    "utf8",
  );
  const api = await readFile(
    new URL("../src/lib/api/analysis.ts", import.meta.url),
    "utf8",
  );

  assert.match(dialog, /공식 일정 등록/);
  assert.match(dialog, /등록 전 확인/);
  assert.match(dialog, /최종 등록/);
  assert.match(dialog, /외부 사이트에 접속하지 않으며/);
  assert.match(dialog, /공식 원문과 발표 예정 시각을 직접 확인했습니다/);
  assert.match(dialog, /예상 영향 경로/);
  assert.match(page, /EconomicEventImportDialog/);
  assert.match(page, /공식 일정 등록/);
  assert.match(api, /\/api\/v1\/economic-events\/import-link/);
});
