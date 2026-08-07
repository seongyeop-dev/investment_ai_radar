export interface OffsetPage<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface OffsetPageRequest {
  limit: number;
  offset: number;
}

export interface PaginationSummary {
  start: number;
  end: number;
  page: number;
  pageCount: number;
  hasPrevious: boolean;
  hasNext: boolean;
}

interface CollectPaginatedItemsOptions {
  pageSize: number;
  signal?: AbortSignal;
}

export function lastValidOffset(
  total: number,
  pageSize: number,
): number {
  if (total <= 0) {
    return 0;
  }

  return (
    Math.floor((total - 1) / pageSize) *
    pageSize
  );
}

export function normalizeOffset(
  total: number,
  pageSize: number,
  requestedOffset: number,
): number {
  const pageOffset =
    Math.floor(
      Math.max(requestedOffset, 0) /
        pageSize,
    ) * pageSize;

  return Math.min(
    pageOffset,
    lastValidOffset(total, pageSize),
  );
}

export function paginationSummary(
  total: number,
  pageSize: number,
  offset: number,
  itemCount: number,
): PaginationSummary {
  const validOffset = normalizeOffset(
    total,
    pageSize,
    offset,
  );
  const pageCount = Math.max(
    1,
    Math.ceil(total / pageSize),
  );

  return {
    start: total === 0 ? 0 : validOffset + 1,
    end:
      total === 0
        ? 0
        : Math.min(
            validOffset + itemCount,
            total,
          ),
    page:
      Math.floor(validOffset / pageSize) + 1,
    pageCount,
    hasPrevious: validOffset > 0,
    hasNext:
      validOffset + itemCount < total,
  };
}

export function previousOffset(
  offset: number,
  pageSize: number,
): number {
  return Math.max(0, offset - pageSize);
}

export function nextOffset(
  total: number,
  pageSize: number,
  offset: number,
): number {
  return Math.min(
    offset + pageSize,
    lastValidOffset(total, pageSize),
  );
}

export function resetOffset(): number {
  return 0;
}

export function selectionForPage<
  T extends { id: string },
>(
  selectedId: string | null,
  items: T[],
): string | null {
  if (
    selectedId &&
    !items.some(
      (item) => item.id === selectedId,
    )
  ) {
    return null;
  }

  return selectedId;
}

export async function collectPaginatedItems<
  T extends { id: string },
>(
  fetchPage: (
    request: OffsetPageRequest,
    signal?: AbortSignal,
  ) => Promise<OffsetPage<T>>,
  options: CollectPaginatedItemsOptions,
): Promise<T[]> {
  const itemsById = new Map<string, T>();
  let offset = 0;

  while (true) {
    options.signal?.throwIfAborted();

    const page = await fetchPage(
      {
        limit: options.pageSize,
        offset,
      },
      options.signal,
    );

    options.signal?.throwIfAborted();

    if (page.offset !== offset) {
      throw new Error(
        "Paginated response offset does not match the request.",
      );
    }

    for (const item of page.items) {
      if (!itemsById.has(item.id)) {
        itemsById.set(item.id, item);
      }
    }

    const returnedCount = page.items.length;

    if (
      returnedCount === 0 ||
      returnedCount < options.pageSize
    ) {
      break;
    }

    const nextPageOffset =
      offset + returnedCount;

    if (nextPageOffset >= page.total) {
      break;
    }

    offset = nextPageOffset;
  }

  return [...itemsById.values()];
}
