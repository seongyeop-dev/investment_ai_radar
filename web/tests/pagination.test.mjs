import assert from "node:assert/strict";
import test from "node:test";

import {
  collectPaginatedItems,
  lastValidOffset,
  nextOffset,
  normalizeOffset,
  paginationSummary,
  previousOffset,
  resetOffset,
  selectionForPage,
} from "../src/lib/pagination.ts";

function items(
  count,
  start = 0,
) {
  return Array.from(
    { length: count },
    (_, index) => ({
      id: `item-${start + index}`,
    }),
  );
}

test(
  "pagination summary covers empty, single, full, and partial pages",
  () => {
    assert.deepEqual(
      paginationSummary(0, 50, 0, 0),
      {
        start: 0,
        end: 0,
        page: 1,
        pageCount: 1,
        hasPrevious: false,
        hasNext: false,
      },
    );
    assert.deepEqual(
      paginationSummary(1, 50, 0, 1),
      {
        start: 1,
        end: 1,
        page: 1,
        pageCount: 1,
        hasPrevious: false,
        hasNext: false,
      },
    );
    assert.deepEqual(
      paginationSummary(50, 50, 0, 50),
      {
        start: 1,
        end: 50,
        page: 1,
        pageCount: 1,
        hasPrevious: false,
        hasNext: false,
      },
    );
    assert.deepEqual(
      paginationSummary(51, 50, 0, 50),
      {
        start: 1,
        end: 50,
        page: 1,
        pageCount: 2,
        hasPrevious: false,
        hasNext: true,
      },
    );
    assert.deepEqual(
      paginationSummary(51, 50, 50, 1),
      {
        start: 51,
        end: 51,
        page: 2,
        pageCount: 2,
        hasPrevious: true,
        hasNext: false,
      },
    );
  },
);

test(
  "offset calculations recover from totals and filter resets",
  () => {
    assert.equal(lastValidOffset(0, 50), 0);
    assert.equal(lastValidOffset(50, 50), 0);
    assert.equal(lastValidOffset(51, 50), 50);
    assert.equal(normalizeOffset(51, 50, 100), 50);
    assert.equal(normalizeOffset(50, 50, 50), 0);
    assert.equal(normalizeOffset(0, 50, 150), 0);
    assert.equal(previousOffset(50, 50), 0);
    assert.equal(nextOffset(51, 50, 0), 50);
    assert.equal(nextOffset(51, 50, 50), 50);
    assert.equal(resetOffset(), 0);
  },
);

test(
  "selection is cleared when the candidate is absent from the page",
  () => {
    assert.equal(
      selectionForPage(
        "candidate-1",
        [{ id: "candidate-1" }],
      ),
      "candidate-1",
    );
    assert.equal(
      selectionForPage(
        "candidate-1",
        [{ id: "candidate-2" }],
      ),
      null,
    );
    assert.equal(
      selectionForPage(
        null,
        [{ id: "candidate-2" }],
      ),
      null,
    );
  },
);

test(
  "collects 51 paginated options using returned item counts",
  async () => {
    const requests = [];

    const result = await collectPaginatedItems(
      async (request) => {
        requests.push(request);

        return request.offset === 0
          ? {
              items: items(50),
              total: 51,
              limit: 50,
              offset: 0,
            }
          : {
              items: items(1, 50),
              total: 51,
              limit: 50,
              offset: 50,
            };
      },
      { pageSize: 50 },
    );

    assert.equal(result.length, 51);
    assert.deepEqual(requests, [
      { limit: 50, offset: 0 },
      { limit: 50, offset: 50 },
    ]);
  },
);

test(
  "collects 51 subscription options across two pages",
  async () => {
    const result = await collectPaginatedItems(
      async (request) =>
        request.offset === 0
          ? {
              items: items(50),
              total: 51,
              limit: 50,
              offset: 0,
            }
          : {
              items: items(1, 50),
              total: 51,
              limit: 50,
              offset: 50,
            },
      { pageSize: 50 },
    );

    assert.equal(result.length, 51);
  },
);

test(
  "deduplicates option IDs while preserving first-seen order",
  async () => {
    const result = await collectPaginatedItems(
      async (request) =>
        request.offset === 0
          ? {
              items: items(50),
              total: 52,
              limit: 50,
              offset: 0,
            }
          : {
              items: [
                { id: "item-49" },
                { id: "item-50" },
              ],
              total: 52,
              limit: 50,
              offset: 50,
            },
      { pageSize: 50 },
    );

    assert.equal(result.length, 51);
    assert.equal(result[49].id, "item-49");
    assert.equal(result[50].id, "item-50");
  },
);

test(
  "stops when an empty page arrives before the reported total",
  async () => {
    let calls = 0;

    const result = await collectPaginatedItems(
      async (request) => {
        calls += 1;

        return request.offset === 0
          ? {
              items: items(50),
              total: 100,
              limit: 50,
              offset: 0,
            }
          : {
              items: [],
              total: 100,
              limit: 50,
              offset: 50,
            };
      },
      { pageSize: 50 },
    );

    assert.equal(calls, 2);
    assert.equal(result.length, 50);
  },
);

test(
  "stops on a short page even when totals are inconsistent",
  async () => {
    let calls = 0;

    const result = await collectPaginatedItems(
      async (request) => {
        calls += 1;

        return request.offset === 0
          ? {
              items: items(50),
              total: 1000,
              limit: 50,
              offset: 0,
            }
          : {
              items: items(1, 50),
              total: 9999,
              limit: 50,
              offset: 50,
            };
      },
      { pageSize: 50 },
    );

    assert.equal(calls, 2);
    assert.equal(result.length, 51);
  },
);

test(
  "passes one AbortSignal to every page and stops immediately on abort",
  async () => {
    const controller = new AbortController();
    const signals = [];

    await assert.rejects(
      collectPaginatedItems(
        async (request, signal) => {
          signals.push(signal);
          controller.abort();

          return {
            items: items(50),
            total: 100,
            limit: 50,
            offset: request.offset,
          };
        },
        {
          pageSize: 50,
          signal: controller.signal,
        },
      ),
      {
        name: "AbortError",
      },
    );

    assert.deepEqual(
      signals,
      [controller.signal],
    );
  },
);

test(
  "rejects a middle-page error instead of returning partial options",
  async () => {
    let calls = 0;

    await assert.rejects(
      collectPaginatedItems(
        async (request) => {
          calls += 1;

          if (request.offset === 50) {
            throw new Error(
              "middle page failed",
            );
          }

          return {
            items: items(50),
            total: 100,
            limit: 50,
            offset: 0,
          };
        },
        { pageSize: 50 },
      ),
      /middle page failed/,
    );

    assert.equal(calls, 2);
  },
);
