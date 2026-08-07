import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const componentPath = new URL(
  "../src/components/news/important-information-import-dialog.tsx",
  import.meta.url,
);
const clientPath = new URL(
  "../src/components/news/news-client.tsx",
  import.meta.url,
);
const apiPath = new URL(
  "../src/lib/api/news.ts",
  import.meta.url,
);

test("important information registration uses preview and final confirmation", async () => {
  const [component, client, api] = await Promise.all([
    readFile(componentPath, "utf8"),
    readFile(clientPath, "utf8"),
    readFile(apiPath, "utf8"),
  ]);

  assert.match(component, /중요 정보 등록/);
  assert.match(component, /등록 전 검증/);
  assert.match(component, /최종 등록/);
  assert.match(component, /기사 전문은 저장하지 않으며/);
  assert.match(component, /외부 사이트에도 접속하지 않았습니다/);
  assert.match(component, /중요 변경으로 표시/);
  assert.match(client, /ImportantInformationImportDialog/);
  assert.match(client, /중요 정보 등록/);
  assert.match(api, /\/api\/v1\/news\/import-link/);
});
