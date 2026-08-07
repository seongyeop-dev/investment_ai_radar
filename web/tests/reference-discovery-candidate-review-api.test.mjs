import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const typesUrl = new URL(
  "../src/types/api.ts",
  import.meta.url,
);

const apiUrl = new URL(
  "../src/lib/api/analyst-references.ts",
  import.meta.url,
);

const clientUrl = new URL(
  "../src/lib/api/client.ts",
  import.meta.url,
);

test(
  "candidate review types expose requests, history, and result contracts",
  async () => {
    const source = await readFile(
      typesUrl,
      "utf8",
    );

    for (const symbol of [
      "ReferenceDiscoveryCandidateReviewAction",
      "ReferenceDiscoveryCandidateVerifyDateInput",
      "ReferenceDiscoveryCandidatePromoteInput",
      "ReferenceDiscoveryCandidateDismissInput",
      "ReferenceDiscoveryCandidateReviewHistory",
      "ReferenceDiscoveryCandidateReviewHistoryListResponse",
      "ReferenceDiscoveryCandidateReviewResult",
      "referenceCreated",
      "referenceDuplicate",
      "promotedReferenceId",
    ]) {
      assert.match(
        source,
        new RegExp(symbol),
      );
    }
  },
);

test(
  "candidate read type exposes 0017 review metadata",
  async () => {
    const source = await readFile(
      typesUrl,
      "utf8",
    );

    for (const symbol of [
      "publicAbstract",
      "publisherType",
      "accessType",
      "documentType",
      "promotedReferenceId",
      "reviewedAt",
    ]) {
      assert.match(
        source,
        new RegExp(symbol),
      );
    }
  },
);

test(
  "candidate review API isolates all write requests in the API module",
  async () => {
    const source = await readFile(
      apiUrl,
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
        new RegExp(
          `export function ${functionName}\\(`,
        ),
      );
    }

    for (const route of [
      "/verify-date",
      "/promote",
      "/dismiss",
      "/review-history",
    ]) {
      assert.ok(
        source.includes(route),
        route,
      );
    }

    assert.equal(
      (
        source.match(
          /method:\s*["']POST["']/g,
        ) ?? []
      ).length >= 3,
      true,
    );
  },
);

test(
  "API client converts FastAPI detail errors into ApiClientError",
  async () => {
    const source = await readFile(
      clientUrl,
      "utf8",
    );

    assert.match(
      source,
      /interface FastApiDetailErrorResponse/,
    );
    assert.match(
      source,
      /function isFastApiDetailErrorResponse\(/,
    );
    assert.match(
      source,
      /isFastApiDetailErrorResponse\(body\)/,
    );
    assert.match(
      source,
      /const\s*\{\s*code,\s*message,\s*\.\.\.details\s*\}\s*=\s*body\.detail/s,
    );
  },
);
