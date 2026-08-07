import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


const clientUrl = new URL(
  "../src/lib/api/client.ts",
  import.meta.url,
);

const panelUrl = new URL(
  "../src/components/sources/reference-source-management-panel.tsx",
  import.meta.url,
);

const apiUrl = new URL(
  "../src/lib/api/analyst-references.ts",
  import.meta.url,
);

const sourcesPageUrl = new URL(
  "../src/app/sources/page.tsx",
  import.meta.url,
);


test(
  "configured API base URL controls both real and validation Web instances",
  async () => {
    const originalValue =
      process.env.NEXT_PUBLIC_API_BASE_URL;

    try {
      process.env.NEXT_PUBLIC_API_BASE_URL =
        "http://127.0.0.1:8001/";

      const validationModuleUrl =
        new URL(clientUrl);

      validationModuleUrl.searchParams.set(
        "case",
        `validation-${Date.now()}`,
      );

      const validationClient =
        await import(
          validationModuleUrl.href
        );

      assert.equal(
        validationClient.resolveApiBaseUrl(
          "localhost",
        ),
        "http://127.0.0.1:8001",
      );

      assert.equal(
        validationClient.resolveApiBaseUrl(
          "192.168.10.240",
        ),
        "http://127.0.0.1:8001",
      );

      delete process.env
        .NEXT_PUBLIC_API_BASE_URL;

      const realModuleUrl =
        new URL(clientUrl);

      realModuleUrl.searchParams.set(
        "case",
        `real-${Date.now()}`,
      );

      const realClient =
        await import(realModuleUrl.href);

      assert.equal(
        realClient.resolveApiBaseUrl(
          "localhost",
        ),
        "http://127.0.0.1:8000",
      );
    } finally {
      if (originalValue === undefined) {
        delete process.env
          .NEXT_PUBLIC_API_BASE_URL;
      } else {
        process.env
          .NEXT_PUBLIC_API_BASE_URL =
          originalValue;
      }
    }
  },
);


test(
  "reference source API client keeps the dedicated management routes",
  async () => {
    const source = await readFile(
      apiUrl,
      "utf8",
    );

    assert.match(
      source,
      /const REFERENCE_SOURCE_MANAGEMENT_PATH\s*=\s*["']\/api\/v1\/analyst-references\/subscriptions\/source-management["']/,
    );

    assert.match(
      source,
      /export function listReferenceSourcesForManagement\(/,
    );

    assert.match(
      source,
      /export function getReferenceSourceForManagement\(/,
    );

    assert.match(
      source,
      /export function importReferenceSource\(/,
    );

    assert.match(
      source,
      /export function updateReferenceSource\(/,
    );

    assert.match(
      source,
      /method:\s*"POST"/,
    );

    assert.match(
      source,
      /method:\s*"PATCH"/,
    );
  },
);


test(
  "source import always previews before confirmation and only exposes confirm when allowed",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    assert.match(
      panel,
      /createImportPayload\(false\)/,
    );

    assert.match(
      panel,
      /createImportPayload\(true\)/,
    );

    assert.match(
      panel,
      /preview\?\.wouldCreate\s*\?\s*\(/,
    );

    assert.match(
      panel,
      /preview\.duplicate\.duplicate/,
    );

    assert.match(
      panel,
      /preview\.duplicate\.matchedFields/,
    );

    assert.match(
      panel,
      /preview\.validationWarnings/,
    );
  },
);


test(
  "active subscriptions block source disabling before any PATCH request",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    const toggleStart = panel.indexOf(
      "async function toggleSource",
    );

    const guardPosition = panel.indexOf(
      "source.activeSubscriptionCount > 0",
      toggleStart,
    );

    const updatePosition = panel.indexOf(
      "await updateReferenceSource(",
      toggleStart,
    );

    assert.notEqual(
      toggleStart,
      -1,
      "toggleSource function was not found",
    );

    assert.notEqual(
      guardPosition,
      -1,
      "active subscription guard was not found",
    );

    assert.notEqual(
      updatePosition,
      -1,
      "source PATCH call was not found",
    );

    assert.ok(
      guardPosition < updatePosition,
      "active subscription guard must run before the PATCH call",
    );

    assert.match(
      panel.slice(
        guardPosition,
        updatePosition,
      ),
      /return;/,
    );
  },
);


test(
  "operating settings update keeps every required source field",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    const saveStart = panel.indexOf(
      "async function saveEdit",
    );

    const toggleStart = panel.indexOf(
      "async function toggleSource",
      saveStart,
    );

    assert.notEqual(
      saveStart,
      -1,
      "saveEdit function was not found",
    );

    assert.notEqual(
      toggleStart,
      -1,
      "toggleSource function was not found",
    );

    const saveBlock = panel.slice(
      saveStart,
      toggleStart,
    );

    assert.match(
      saveBlock,
      /sourceGrade:/,
    );

    assert.match(
      saveBlock,
      /language:/,
    );

    assert.match(
      saveBlock,
      /requestIntervalSeconds/,
    );

    assert.match(
      saveBlock,
      /timeoutSeconds/,
    );

    assert.match(
      saveBlock,
      /maxItems/,
    );

    assert.match(
      saveBlock,
      /await updateReferenceSource\(/,
    );
  },
);


test(
  "source panel never opens or directly fetches an external Feed URL",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    assert.doesNotMatch(
      panel,
      /window\.open\s*\(/,
    );

    assert.doesNotMatch(
      panel,
      /location\.href\s*=/,
    );

    assert.doesNotMatch(
      panel,
      /fetch\s*\(/,
    );

    assert.doesNotMatch(
      panel,
      /href=\{source\.feedUrl\}/,
    );

    assert.match(
      panel,
      /importReferenceSource\(/,
    );
  },
);


test(
  "sources page renders source management before subscription management",
  async () => {
    const page = await readFile(
      sourcesPageUrl,
      "utf8",
    );

    const sourceManagementPosition =
      page.indexOf(
        "<ReferenceSourceManagementPanel",
      );

    const subscriptionPosition =
      page.indexOf(
        "<ReferenceSubscriptionPanel",
      );

    assert.notEqual(
      sourceManagementPosition,
      -1,
    );

    assert.notEqual(
      subscriptionPosition,
      -1,
    );

    assert.ok(
      sourceManagementPosition <
        subscriptionPosition,
      "official source management must appear before subscription management",
    );
  },
);
