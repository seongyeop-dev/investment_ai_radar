import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("official disclosure registration uses preview and final confirmation", async () => {
  const dialog = await readFile(
    new URL(
      "../src/components/disclosures/official-disclosure-import-dialog.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const client = await readFile(
    new URL(
      "../src/components/disclosures/disclosure-client.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const api = await readFile(
    new URL("../src/lib/api/news.ts", import.meta.url),
    "utf8",
  );
  const types = await readFile(
    new URL("../src/types/api.ts", import.meta.url),
    "utf8",
  );

  assert.match(client, /공식 공시 등록/);
  assert.match(client, /OfficialDisclosureImportDialog/);
  assert.match(dialog, /SEC 또는 OpenDART 공식 주소/);
  assert.match(dialog, /등록 전 검증/);
  assert.match(dialog, /최종 등록/);
  assert.match(dialog, /공시 전문은 저장하지 않으며/);
  assert.match(dialog, /preview\.wouldCreate/);
  assert.match(dialog, /preview\.duplicate\.duplicate/);
  assert.match(dialog, /predictedVerificationStatus/);
  assert.match(api, /\/api\/v1\/disclosures\/import-link/);
  assert.match(api, /method: "POST"/);
  assert.match(types, /OfficialDisclosureImportPreview/);
  assert.match(types, /confirmed: false/);
  assert.match(types, /confirmed: true/);
});
