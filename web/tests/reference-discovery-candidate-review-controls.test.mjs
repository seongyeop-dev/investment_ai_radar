import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const controlsUrl = new URL(
  "../src/components/sources/reference-discovery-candidate-review-controls.tsx",
  import.meta.url,
);

const panelUrl = new URL(
  "../src/components/sources/reference-discovery-candidate-panel.tsx",
  import.meta.url,
);

test(
  "candidate review controls use the dedicated API wrappers",
  async () => {
    const source = await readFile(
      controlsUrl,
      "utf8",
    );

    for (const functionName of [
      "verifyReferenceDiscoveryCandidateDate",
      "promoteReferenceDiscoveryCandidate",
      "dismissReferenceDiscoveryCandidate",
      "listReferenceDiscoveryCandidateReviewHistory",
    ]) {
      assert.match(
        source,
        new RegExp(functionName),
      );
    }

    assert.doesNotMatch(
      source,
      /\bfetch\s*\(/,
    );
    assert.doesNotMatch(
      source,
      /window\.open\s*\(/,
    );
    assert.doesNotMatch(
      source,
      /location\.href\s*=/,
    );
  },
);

test(
  "candidate review controls require date, confirmation, and dismissal reason",
  async () => {
    const source = await readFile(
      controlsUrl,
      "utf8",
    );

    for (const token of [
      'type="datetime-local"',
      "promoteConfirmed",
      "dismissConfirmed",
      "dismissReason",
      "referenceDuplicate",
      "historyRefreshKey",
      "DATE_VERIFIED",
      "PROMOTED",
      "DISMISSED",
    ]) {
      assert.ok(
        source.includes(token),
        token,
      );
    }

    assert.match(
      source,
      /maxLength=\{1000\}/,
    );
  },
);

test(
  "candidate panel replaces its read-only notice with review controls",
  async () => {
    const source = await readFile(
      panelUrl,
      "utf8",
    );

    assert.match(
      source,
      /ReferenceDiscoveryCandidateReviewControls/,
    );
    assert.match(
      source,
      /handleCandidateReviewed/,
    );
    assert.doesNotMatch(
      source,
      /\uc774 \ud654\uba74\uc740 \uc77d\uae30 \uc804\uc6a9\uc785\ub2c8\ub2e4\./,
    );
  },
);
