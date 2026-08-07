"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  listReferenceSourceChangeHistory,
  listReferenceSourceHistorySources,
} from "@/lib/api/reference-source-history";
import { ApiClientError } from "@/lib/api/client";
import type {
  ReferenceSourceChange,
  ReferenceSourceChangeListResponse,
  ReferenceSourceHistorySource,
} from "@/types/api";

const K = {
  title:
    "\uacf5\uc2dd \ucd9c\ucc98 \ubcc0\uacbd \uc774\ub825",
  description:
    "\uacf5\uc2dd \ucd9c\ucc98\uc758 \ub4f1\ub85d\uacfc \uc6b4\uc601 \uc124\uc815 \ubcc0\uacbd \uae30\ub85d\uc744 \uc77d\uae30 \uc804\uc6a9\uc73c\ub85c \ud655\uc778\ud569\ub2c8\ub2e4. \ubc31\uc5c5 \ud30c\uc77c\uc740 \ube0c\ub77c\uc6b0\uc800\uc5d0\uc11c \uc5f4\uac70\ub098 \ub2e4\uc6b4\ub85c\ub4dc\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  refresh:
    "\uc774\ub825 \uc0c8\ub85c\uace0\uce68",
  refreshing:
    "\uc0c8\ub85c\uace0\uce68 \uc911\u2026",
  sourceLabel:
    "\ud655\uc778\ud560 \uacf5\uc2dd \ucd9c\ucc98",
  noSource:
    "\ub4f1\ub85d\ub41c \uacf5\uc2dd \ucd9c\ucc98 \uc5c6\uc74c",
  active:
    "\ud65c\uc131",
  inactive:
    "\uc911\uc9c0",
  sourceLoading:
    "\uacf5\uc2dd \ucd9c\ucc98 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\u2026",
  historyLoading:
    "\ubcc0\uacbd \uc774\ub825\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\u2026",
  sourceLoadError:
    "\uacf5\uc2dd \ucd9c\ucc98 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
  historyLoadError:
    "\uacf5\uc2dd \ucd9c\ucc98 \ubcc0\uacbd \uc774\ub825\uc744 \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
  emptyTitle:
    "\uc544\uc9c1 \uae30\ub85d\ub41c \ubcc0\uacbd \uc774\ub825\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.",
  emptyDescription:
    "\uae30\uc874 Oaktree \ucd9c\ucc98\ub294 \uc774\ub825 \uae30\ub2a5 \ub3c4\uc785 \uc804\uc5d0 \ub4f1\ub85d\ub418\uc5b4 CREATE \uae30\ub85d\uc774 \uc5c6\uc2b5\ub2c8\ub2e4. \uc774\ud6c4 \uc2e4\uc81c \uc124\uc815 \ubcc0\uacbd\ubd80\ud130 \uc790\ub3d9\uc73c\ub85c \uae30\ub85d\ub429\ub2c8\ub2e4.",
  recentHistory:
    "\ucd5c\uadfc \ubcc0\uacbd \uc774\ub825",
  count:
    "\uac74",
  created:
    "\uc2e0\uaddc \ub4f1\ub85d",
  updated:
    "\uc124\uc815 \ubcc0\uacbd",
  fieldCount:
    "\uac1c \ud56d\ubaa9",
  before:
    "\ubcc0\uacbd \uc804",
  after:
    "\ubcc0\uacbd \ud6c4",
  backup:
    "\ubcc0\uacbd \uc9c1\uc804 \ubc31\uc5c5 \uae30\ub85d",
  noBackup:
    "\ubc31\uc5c5 \uacbd\ub85c \uae30\ub85d \uc5c6\uc74c",
  readOnly:
    "\uc774 \uc601\uc5ed\uc740 \uc870\ud68c \uc804\uc6a9\uc785\ub2c8\ub2e4. \ubcc0\uacbd \uc774\ub825\uacfc \ubc31\uc5c5 \uae30\ub85d\uc744 \uc0ad\uc81c\ud558\uac70\ub098 \ubc31\uc5c5 \ud30c\uc77c\uc744 \uc2e4\ud589\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  yes:
    "\uc608",
  no:
    "\uc544\ub2c8\uc694",
  none:
    "\uc5c6\uc74c",
  emptyValue:
    "\ube48 \uac12",
  separator:
    " \u00b7 ",
} as const;

const FIELD_LABELS: Record<string, string> = {
  name: "\ucd9c\ucc98 \uc774\ub984",
  source_grade: "\ucd9c\ucc98 \ub4f1\uae09",
  domain: "\uacf5\uc2dd \ub3c4\uba54\uc778",
  official: "\uacf5\uc2dd \ucd9c\ucc98 \uc5ec\ubd80",
  enabled: "\ud65c\uc131 \uc0c1\ud0dc",
  feed_url: "수집 주소(URL)",
  provider_type: "수집 방식",
  language: "\uc5b8\uc5b4 \ucf54\ub4dc",
  request_interval_seconds: "\uc694\uccad \uc8fc\uae30(\ucd08)",
  timeout_seconds: "\ud0c0\uc784\uc544\uc6c3(\ucd08)",
  max_items: "\ucd5c\ub300 \uc218\uc9d1 \uac74\uc218",
  original_source_name: "\uc6d0\ub798 \ucd9c\ucc98 \uc774\ub984",
};

function errorMessage(
  reason: unknown,
  fallback: string,
): string {
  return reason instanceof ApiClientError
    ? reason.message
    : fallback;
}

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) {
    return K.none;
  }

  if (typeof value === "boolean") {
    return value ? K.yes : K.no;
  }

  if (typeof value === "string") {
    const labels: Record<string, string> = {
      REFERENCE_INDEX: "공개자료 목록",
      en: "영어",
      ko: "한국어",
    };

    return (labels[value] ?? value) || K.emptyValue;
  }

  if (
    typeof value === "number" ||
    typeof value === "bigint"
  ) {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatCreatedAt(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("ko-KR");
}

function operationLabel(
  item: ReferenceSourceChange,
): string {
  return item.operation === "CREATE"
    ? K.created
    : K.updated;
}

export function ReferenceSourceHistoryPanel() {
  const [sources, setSources] = useState<
    ReferenceSourceHistorySource[]
  >([]);
  const [selectedSourceId, setSelectedSourceId] =
    useState("");
  const [history, setHistory] =
    useState<ReferenceSourceChangeListResponse | null>(
      null,
    );
  const [sourcesLoading, setSourcesLoading] =
    useState(true);
  const [historyLoading, setHistoryLoading] =
    useState(false);
  const [error, setError] = useState("");

  const selectedSource = useMemo(
    () =>
      sources.find(
        (source) =>
          source.id === selectedSourceId,
      ) ?? null,
    [selectedSourceId, sources],
  );

  const loadHistory = useCallback(
    async (
      sourceId: string,
      signal?: AbortSignal,
    ) => {
      if (!sourceId) {
        setHistory(null);
        return;
      }

      setHistoryLoading(true);

      try {
        const response =
          await listReferenceSourceChangeHistory(
            sourceId,
            {
              limit: 50,
              offset: 0,
            },
            signal,
          );

        if (signal?.aborted) {
          return;
        }

        setHistory(response);
        setError("");
      } catch (reason: unknown) {
        if (
          reason instanceof ApiClientError &&
          reason.kind === "cancelled"
        ) {
          return;
        }

        setError(
          errorMessage(
            reason,
            K.historyLoadError,
          ),
        );
      } finally {
        if (!signal?.aborted) {
          setHistoryLoading(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();

    listReferenceSourceHistorySources(
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) {
          return;
        }

        setSources(response.items);
        setSelectedSourceId((current) => {
          if (
            current &&
            response.items.some(
              (source) => source.id === current,
            )
          ) {
            return current;
          }

          return response.items[0]?.id ?? "";
        });
        setError("");
      })
      .catch((reason: unknown) => {
        if (
          reason instanceof ApiClientError &&
          reason.kind === "cancelled"
        ) {
          return;
        }

        setError(
          errorMessage(
            reason,
            K.sourceLoadError,
          ),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setSourcesLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedSourceId) {
      return;
    }

    const controller = new AbortController();

    listReferenceSourceChangeHistory(
      selectedSourceId,
      {
        limit: 50,
        offset: 0,
      },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) {
          return;
        }

        setHistory(response);
        setError("");
      })
      .catch((reason: unknown) => {
        if (
          reason instanceof ApiClientError &&
          reason.kind === "cancelled"
        ) {
          return;
        }

        if (!controller.signal.aborted) {
          setError(
            errorMessage(
              reason,
              K.historyLoadError,
            ),
          );
        }
      });

    return () => controller.abort();
  }, [selectedSourceId]);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold tracking-[0.18em] text-gold">
            출처 변경 이력
          </p>

          <h2 className="mt-2 text-xl font-bold">
            {K.title}
          </h2>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {K.description}
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            void loadHistory(selectedSourceId);
          }}
          disabled={
            !selectedSourceId ||
            sourcesLoading ||
            historyLoading
          }
          className="inline-flex min-h-10 items-center justify-center rounded-xl border border-gold/50 px-4 text-sm font-bold text-gold hover:bg-gold/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {historyLoading
            ? K.refreshing
            : K.refresh}
        </button>
      </div>

      <div className="mt-5">
        <label className="block max-w-xl text-sm font-semibold">
          {K.sourceLabel}

          <select
            value={selectedSourceId}
            onChange={(event) => {
              setSelectedSourceId(
                event.target.value,
              );
              setHistory(null);
              setError("");
            }}
            disabled={
              sourcesLoading || !sources.length
            }
            className="mt-2 min-h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:border-gold disabled:opacity-60"
          >
            {!sources.length ? (
              <option value="">
                {K.noSource}
              </option>
            ) : null}

            {sources.map((source) => (
              <option
                key={source.id}
                value={source.id}
              >
                {source.name}
                {K.separator}
                {source.domain}
              </option>
            ))}
          </select>
        </label>

        {selectedSource ? (
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-border px-3 py-1 font-semibold text-secondary">
              {selectedSource.domain}
            </span>

            <span
              className={
                selectedSource.enabled
                  ? "rounded-full border border-green/40 bg-green/10 px-3 py-1 font-bold text-green"
                  : "rounded-full border border-red/40 bg-red/10 px-3 py-1 font-bold text-red"
              }
            >
              {selectedSource.enabled
                ? K.active
                : K.inactive}
            </span>
          </div>
        ) : null}
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-5 rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red"
        >
          {error}
        </p>
      ) : null}

      {sourcesLoading ? (
        <div className="mt-5 rounded-xl border border-border bg-background p-6 text-center text-sm text-muted">
          {K.sourceLoading}
        </div>
      ) : null}

      {!sourcesLoading &&
      selectedSourceId &&
      historyLoading &&
      !history ? (
        <div className="mt-5 rounded-xl border border-border bg-background p-6 text-center text-sm text-muted">
          {K.historyLoading}
        </div>
      ) : null}

      {!sourcesLoading &&
      selectedSourceId &&
      !historyLoading &&
      history?.items.length === 0 ? (
        <div className="mt-5 rounded-xl border border-border bg-background p-6">
          <p className="font-bold">
            {K.emptyTitle}
          </p>

          <p className="mt-2 text-sm leading-6 text-muted">
            {K.emptyDescription}
          </p>
        </div>
      ) : null}

      {history?.items.length ? (
        <div className="mt-5 space-y-4">
          <p className="text-sm text-muted">
            {K.recentHistory}{" "}
            <strong className="text-foreground">
              {history.total}
              {K.count}
            </strong>
          </p>

          {history.items.map((item) => (
            <article
              key={item.id}
              className="rounded-2xl border border-border bg-background p-4 sm:p-5"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={
                      item.operation === "CREATE"
                        ? "rounded-full border border-green/40 bg-green/10 px-3 py-1 text-xs font-bold text-green"
                        : "rounded-full border border-gold/40 bg-gold/10 px-3 py-1 text-xs font-bold text-gold"
                    }
                  >
                    {operationLabel(item)}
                  </span>

                  <span className="text-sm font-semibold">
                    {item.changedFields.length}
                    {K.fieldCount}
                  </span>
                </div>

                <time className="text-xs text-muted">
                  {formatCreatedAt(item.createdAt)}
                </time>
              </div>

              <div className="mt-4 space-y-3">
                {item.changedFields.map((field) => (
                  <div
                    key={field}
                    className="rounded-xl border border-border p-3"
                  >
                    <p className="text-xs font-bold text-secondary">
                      {fieldLabel(field)}
                    </p>

                    <div className="mt-2 grid gap-3 text-sm sm:grid-cols-2">
                      <div>
                        <p className="text-xs text-muted">
                          {K.before}
                        </p>
                        <p className="mt-1 break-all font-semibold">
                          {item.beforeValues
                            ? displayValue(
                                item.beforeValues[
                                  field
                                ],
                              )
                            : K.none}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs text-muted">
                          {K.after}
                        </p>
                        <p className="mt-1 break-all font-semibold">
                          {displayValue(
                            item.afterValues[field],
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-xl border border-border bg-card p-3">
                <p className="text-xs text-muted">
                  {K.backup}
                </p>

                <p className="mt-1 break-all font-mono text-xs text-secondary">
                  {item.backupPath ? "백업 기록 생성됨" : K.noBackup}
                </p>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      <p className="mt-5 rounded-xl border border-border bg-background p-3 text-xs leading-5 text-muted">
        {K.readOnly}
      </p>
    </section>
  );
}
