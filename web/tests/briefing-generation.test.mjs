import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const dialog = fs.readFileSync(
  new URL(
    "../src/components/briefings/briefing-generation-dialog.tsx",
    import.meta.url,
  ),
  "utf8",
);
const client = fs.readFileSync(
  new URL("../src/components/briefings/briefings-client.tsx", import.meta.url),
  "utf8",
);
const api = fs.readFileSync(
  new URL("../src/lib/api/operations.ts", import.meta.url),
  "utf8",
);
const types = fs.readFileSync(
  new URL("../src/types/api.ts", import.meta.url),
  "utf8",
);

test("briefing generation uses preview and final confirmation", () => {
  assert.match(dialog, /변경 기반 브리핑 만들기/);
  assert.match(dialog, /생성 전 확인/);
  assert.match(dialog, /최종 생성/);
  assert.match(dialog, /DB에 저장하지 않으며 이메일을 보내지 않습니다/);
  assert.match(dialog, /포함 항목과 기간을 직접 확인했습니다/);
  assert.match(client, /BriefingGenerationDialog/);
  assert.match(client, /브리핑 만들기/);
  assert.match(client, /briefingTypeText/);
  assert.doesNotMatch(client, /\{briefing\.briefingType\}/);
  assert.match(api, /\/api\/v1\/briefings\/generate/);
  assert.match(api, /method: "POST"/);
  assert.match(types, /BriefingGenerationPreview/);
  assert.match(types, /emailDeliveryCreated: false/);
});
