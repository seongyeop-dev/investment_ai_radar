import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const panelUrl = new URL(
  "../src/components/sources/reference-discovery-candidate-panel.tsx",
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
  "candidate Web API exposes dedicated read-only list and detail routes",
  async () => {
    const source = await readFile(
      apiUrl,
      "utf8",
    );

    assert.match(
      source,
      /const REFERENCE_DISCOVERY_CANDIDATE_PATH\s*=\s*["']\/api\/v1\/analyst-references\/discovery-candidates["']/,
    );
    assert.match(
      source,
      /export function listReferenceDiscoveryCandidates\(/,
    );
    assert.match(
      source,
      /export function getReferenceDiscoveryCandidate\(/,
    );
  },
);

test(
  "candidate panel reads API data without external document access or write requests",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    assert.match(
      panel,
      /listReferenceDiscoveryCandidates\(/,
    );
    assert.match(
      panel,
      /getReferenceDiscoveryCandidate\(/,
    );
    assert.match(
      panel,
      /navigator\.clipboard\.writeText\(/,
    );

    assert.doesNotMatch(
      panel,
      /\bfetch\s*\(/,
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
      /href=\{[^}]*canonicalUrl[^}]*\}/,
    );
    assert.doesNotMatch(
      panel,
      /method:\s*["'](?:POST|PATCH|PUT|DELETE)["']/,
    );
  },
);

test(
  "candidate panel exposes required review metadata and filters",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    for (const token of [
      "sourceId",
      "subscriptionId",
      "verificationStatus",
      "appliedQuery",
      "publishedAt",
      "firstSeenAt",
      "lastSeenAt",
      "seenCount",
      "DATE_UNVERIFIED",
      "providerItemId",
    ]) {
      assert.match(
        panel,
        new RegExp(token),
      );
    }
  },
);

test(
  "candidate panel uses offset pagination without detail-triggered list reloads",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    assert.match(
      panel,
      /const CANDIDATE_PAGE_SIZE = 50;/,
    );
    assert.match(
      panel,
      /limit: CANDIDATE_PAGE_SIZE,\s*offset,/,
    );
    assert.match(
      panel,
      /appliedQuery,\s*offset,\s*refreshKey,\s*sourceId,\s*subscriptionId,\s*verificationStatus,/,
    );
    assert.match(
      panel,
      /aria-label="이전 후보 페이지"/,
    );
    assert.match(
      panel,
      /aria-label="다음 후보 페이지"/,
    );
    assert.match(
      panel,
      /전체 \{total\}건/,
    );
    assert.equal(
      (
        panel.match(
          /setOffset\(resetOffset\(\)\)/g,
        ) ?? []
      ).length,
      5,
    );
  },
);

test(
  "candidate filter options traverse all API pages",
  async () => {
    const panel = await readFile(
      panelUrl,
      "utf8",
    );

    assert.match(
      panel,
      /collectPaginatedItems\(\s*listReferenceSubscriptionSources,/,
    );
    assert.match(
      panel,
      /collectPaginatedItems\(\s*listReferenceSubscriptions,/,
    );
    assert.match(
      panel,
      /pageSize: OPTION_PAGE_SIZE/,
    );
  },
);

test(
  "sources page places pending review after subscriptions and before manual import",
  async () => {
    const page = await readFile(
      sourcesPageUrl,
      "utf8",
    );

    const subscriptionPosition =
      page.indexOf(
        "<ReferenceSubscriptionPanel",
      );
    const candidatePosition =
      page.indexOf(
        "<ReferenceDiscoveryCandidatePanel",
      );
    const importPosition =
      page.indexOf(
        "<AnalystReferenceImportLauncher",
      );

    assert.notEqual(
      subscriptionPosition,
      -1,
    );
    assert.notEqual(
      candidatePosition,
      -1,
    );
    assert.notEqual(
      importPosition,
      -1,
    );

    assert.ok(
      subscriptionPosition <
        candidatePosition,
    );
    assert.ok(
      candidatePosition <
        importPosition,
    );
  },
);
