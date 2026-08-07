"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  listAnalystReferences,
} from "@/lib/api/analyst-references";
import {
  ApiClientError,
} from "@/lib/api/client";
import type {
  AnalystAccessType,
  AnalystDocumentType,
  AnalystFreshnessStatus,
  AnalystReference,
  AnalystUserState,
} from "@/types/api";


const K = {
  report: "\uBCF4\uACE0\uC11C",
  commentary: "\uBA54\uBAA8\xB7\uB17C\uD3C9",
  interview: "\uC778\uD130\uBDF0",
  consensus: "\uCEE8\uC13C\uC11C\uC2A4",
  otherDocument: "\uAE30\uD0C0 \uC790\uB8CC",

  publicAccess: "\uACF5\uAC1C",
  loginRequired: "\uB85C\uADF8\uC778 \uD544\uC694",
  paywalled: "\uC720\uB8CC",
  accessUnknown:
    "\uC811\uADFC \uC0C1\uD0DC \uBBF8\uD655\uC778",

  current: "\uCD5C\uC2E0",
  aging: "\uACBD\uACFC",
  stale: "\uC624\uB798\uB428",
  freshnessUnknown:
    "\uC2E0\uC120\uB3C4 \uBBF8\uD655\uC778",

  newState: "\uC2E0\uADDC",
  readState: "\uC77D\uC74C",
  archivedState: "\uBCF4\uAD00",
  hiddenState: "\uC228\uAE40",

  automatic: "\uC790\uB3D9 \uBC1C\uACAC",
  manual: "\uC9C1\uC811 \uB4F1\uB85D",
  openOriginal:
    "\uC6D0\uBB38 \uC5F4\uAE30 \u2197",
  originalTitle: "\uC6D0\uBB38",

  publisher: "\uBC1C\uD589\uAE30\uAD00",
  analyst: "\uC804\uBB38\uAC00\xB7\uC800\uC790",
  metadataMissing:
    "\uACF5\uAC1C \uBA54\uD0C0\uB370\uC774\uD130 \uC5C6\uC74C",
  publishedDate: "\uACF5\uAC1C\uC77C",
  documentCategory: "\uC790\uB8CC \uAD6C\uBD84",
  relatedStocks: "\uC5F0\uACB0 \uC885\uBAA9",
  itemUnit: "\uAC1C",
  itemCount: "\uAC74",
  noCoverage: "\uC5F0\uACB0 \uC5C6\uC74C",
  collectionMethod: "\uC218\uC9D1 \uBC29\uC2DD",
  automaticMethod:
    "\uACF5\uC2DD \uACF5\uAC1C \uCD9C\uCC98 \uC790\uB3D9 \uD655\uC778",
  manualMethod:
    "\uC0AC\uC6A9\uC790 \uC9C1\uC811 \uB4F1\uB85D",

  loadError:
    "\uCC38\uACE0\uC790\uB8CC \uBAA9\uB85D\uC744 \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.",
  libraryTitle:
    "\uCC38\uACE0\uC790\uB8CC \uBCF4\uAD00\uD568",
  libraryDescription:
    "\uACF5\uC2DD \uCD9C\uCC98\uC5D0\uC11C \uC790\uB3D9\uC73C\uB85C \uBC1C\uACAC\uD55C \uC790\uB8CC\uC640 \uC9C1\uC811 \uB4F1\uB85D\uD55C \uACF5\uAC1C \uCC38\uACE0\uC790\uB8CC\uB97C \uD568\uAED8 \uD655\uC778\uD569\uB2C8\uB2E4. \uC81C\uBAA9\xB7\uB0A0\uC9DC\xB7\uB9C1\uD06C \uB4F1 \uACF5\uAC1C \uBA54\uD0C0\uB370\uC774\uD130\uB9CC \uBCF4\uAD00\uD569\uB2C8\uB2E4.",

  refreshing:
    "\uC0C8\uB85C\uACE0\uCE68 \uC911\u2026",
  refreshList:
    "\uBAA9\uB85D \uC0C8\uB85C\uACE0\uCE68",
  total: "\uC804\uCCB4",

  automaticGroup:
    "\uC790\uB3D9 \uBC1C\uACAC \uCC38\uACE0\uC790\uB8CC",
  automaticGroupDescription:
    "\uB4F1\uB85D\uD55C \uC804\uBB38\uAC00\xB7\uAE30\uAD00\uC758 \uACF5\uC2DD \uACF5\uAC1C \uCD9C\uCC98\uC5D0\uC11C \uD655\uC778\uB41C \uC2E0\uADDC \uC790\uB8CC\uC785\uB2C8\uB2E4.",
  noAutomatic:
    "\uC790\uB3D9\uC73C\uB85C \uBC1C\uACAC\uB41C \uCC38\uACE0\uC790\uB8CC\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4.",

  manualGroup:
    "\uC9C1\uC811 \uB4F1\uB85D \uCC38\uACE0\uC790\uB8CC",
  manualGroupDescription:
    "\uACF5\uAC1C \uB9C1\uD06C\uC640 \uAC80\uC99D \uAC00\uB2A5\uD55C \uBA54\uD0C0\uB370\uC774\uD130\uB97C \uC0AC\uC6A9\uC790\uAC00 \uC9C1\uC811 \uB4F1\uB85D\uD55C \uC790\uB8CC\uC785\uB2C8\uB2E4.",
  noManual:
    "\uC9C1\uC811 \uB4F1\uB85D\uD55C \uCC38\uACE0\uC790\uB8CC\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4.",

  loading:
    "\uCC38\uACE0\uC790\uB8CC \uBAA9\uB85D\uC744 \uBD88\uB7EC\uC624\uB294 \uC911\u2026",
  isolationNotice:
    "\uCC38\uACE0\uC790\uB8CC\uB294 \uCD9C\uCC98 \uD655\uC778\uACFC \uC5F4\uB78C\uC744 \uC704\uD55C \uBCC4\uB3C4 \uC601\uC5ED\uC785\uB2C8\uB2E4. \uC790\uB3D9 \uBD84\uC11D, \uC885\uBAA9 \uAD00\uB9AC \uBC29\uD5A5, \uBAA9\uD45C\uAC00, \uD22C\uC790 \uD310\uB2E8 \uACC4\uC0B0\uC5D0\uB294 \uC0AC\uC6A9\uB418\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4.",
} as const;


const documentTypeLabels: Record<
  AnalystDocumentType,
  string
> = {
  REPORT: K.report,
  COMMENTARY: K.commentary,
  INTERVIEW: K.interview,
  CONSENSUS: K.consensus,
  OTHER: K.otherDocument,
};

const accessTypeLabels: Record<
  AnalystAccessType,
  string
> = {
  PUBLIC: K.publicAccess,
  LOGIN_REQUIRED: K.loginRequired,
  PAYWALLED: K.paywalled,
  UNKNOWN: K.accessUnknown,
};

const freshnessLabels: Record<
  AnalystFreshnessStatus,
  string
> = {
  CURRENT: K.current,
  AGING: K.aging,
  STALE: K.stale,
  UNKNOWN: K.freshnessUnknown,
};

const userStateLabels: Record<
  AnalystUserState,
  string
> = {
  NEW: K.newState,
  READ: K.readState,
  ARCHIVED: K.archivedState,
  HIDDEN: K.hiddenState,
};


function formatDate(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "ko-KR",
    {
      year: "numeric",
      month: "long",
      day: "numeric",
      timeZone: "Asia/Seoul",
    },
  ).format(parsed);
}


function ReferenceCard({
  item,
}: {
  item: AnalystReference;
}) {
  const automatic =
    item.ingestMode === "AUTOMATIC";

  const translatedTitle =
    item.translationStatus === "COMPLETED" &&
    item.translatedTitleKo?.trim()
      ? item.translatedTitleKo.trim()
      : null;

  return (
    <article className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2">
            <span
              className={
                automatic
                  ? "rounded-full border border-green/30 bg-green/10 px-2.5 py-1 text-xs font-bold text-green"
                  : "rounded-full border border-cyan/30 bg-cyan/10 px-2.5 py-1 text-xs font-bold text-cyan"
              }
            >
              {automatic
                ? K.automatic
                : K.manual}
            </span>

            <span className="rounded-full border border-border bg-background px-2.5 py-1 text-xs font-semibold text-secondary">
              {userStateLabels[item.userState]}
            </span>

            <span className="rounded-full border border-border bg-background px-2.5 py-1 text-xs font-semibold text-secondary">
              {freshnessLabels[
                item.freshnessStatus
              ]}
            </span>
          </div>

          <h3 className="mt-3 break-words text-base font-bold leading-6">
            {translatedTitle ?? item.title}
          </h3>

          {translatedTitle &&
          translatedTitle !== item.title ? (
            <p className="mt-1 break-words text-xs leading-5 text-muted">
              {K.originalTitle}: {item.title}
            </p>
          ) : null}
        </div>

        <a
          href={item.canonicalUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-cyan/40 px-3.5 text-xs font-bold text-cyan transition hover:bg-cyan/10"
        >
          {K.openOriginal}
        </a>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-muted">
            {K.publisher}
          </dt>
          <dd className="mt-1 font-semibold">
            {item.publisherName}
          </dd>
        </div>

        <div>
          <dt className="text-xs text-muted">
            {K.analyst}
          </dt>
          <dd className="mt-1 font-semibold">
            {item.analystName ||
              K.metadataMissing}
          </dd>
        </div>

        <div>
          <dt className="text-xs text-muted">
            {K.publishedDate}
          </dt>
          <dd className="mt-1 font-semibold">
            {formatDate(item.publishedAt)}
          </dd>
        </div>

        <div>
          <dt className="text-xs text-muted">
            {K.documentCategory}
          </dt>
          <dd className="mt-1 font-semibold">
            {documentTypeLabels[
              item.documentType
            ]}
            {" \u00B7 "}
            {accessTypeLabels[
              item.accessType
            ]}
          </dd>
        </div>

        <div>
          <dt className="text-xs text-muted">
            {K.relatedStocks}
          </dt>
          <dd className="mt-1 font-semibold">
            {item.coverages.length
              ? `${item.coverages.length}${K.itemUnit}`
              : K.noCoverage}
          </dd>
        </div>

        <div>
          <dt className="text-xs text-muted">
            {K.collectionMethod}
          </dt>
          <dd className="mt-1 font-semibold">
            {automatic
              ? K.automaticMethod
              : K.manualMethod}
          </dd>
        </div>
      </dl>
    </article>
  );
}


function ReferenceGroup({
  title,
  description,
  items,
  emptyMessage,
}: {
  title: string;
  description: string;
  items: AnalystReference[];
  emptyMessage: string;
}) {
  return (
    <section>
      <h3 className="text-base font-bold">
        {title}
      </h3>

      <p className="mt-1 text-sm leading-6 text-muted">
        {description}
      </p>

      {items.length ? (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {items.map((item) => (
            <ReferenceCard
              key={item.id}
              item={item}
            />
          ))}
        </div>
      ) : (
        <div className="mt-3 rounded-xl border border-border bg-card px-4 py-8 text-center text-sm text-muted">
          {emptyMessage}
        </div>
      )}
    </section>
  );
}


export function AnalystReferenceListPanel() {
  const [items, setItems] = useState<
    AnalystReference[]
  >([]);
  const [loading, setLoading] =
    useState(true);
  const [refreshing, setRefreshing] =
    useState(false);
  const [error, setError] =
    useState("");

  const refresh = useCallback(async () => {
    setRefreshing(true);

    try {
      const response =
        await listAnalystReferences({
          includeInactive: false,
          limit: 100,
          offset: 0,
        });

      setItems(response.items);
      setError("");
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : K.loadError,
      );
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const controller =
      new AbortController();

    listAnalystReferences(
      {
        includeInactive: false,
        limit: 100,
        offset: 0,
      },
      controller.signal,
    )
      .then((response) => {
        setItems(response.items);
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
          reason instanceof ApiClientError
            ? reason.message
            : K.loadError,
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  const automaticItems = items.filter(
    (item) =>
      item.ingestMode === "AUTOMATIC",
  );

  const manualItems = items.filter(
    (item) =>
      item.ingestMode === "MANUAL",
  );

  return (
    <section className="rounded-2xl border border-cyan/30 bg-cyan/5 p-4 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan">
            참고자료 보관함
          </p>

          <h2 className="mt-1 text-lg font-bold">
            {K.libraryTitle}
          </h2>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary">
            {K.libraryDescription}
          </p>
        </div>

        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading || refreshing}
          className="inline-flex min-h-11 w-full shrink-0 items-center justify-center rounded-xl border border-cyan/40 px-4 text-sm font-bold text-cyan disabled:opacity-60 sm:w-auto"
        >
          {refreshing
            ? K.refreshing
            : K.refreshList}
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="rounded-full border border-green/30 bg-green/10 px-3 py-1.5 text-xs font-bold text-green">
          {K.automatic}{" "}
          {automaticItems.length}
          {K.itemCount}
        </span>

        <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1.5 text-xs font-bold text-cyan">
          {K.manual}{" "}
          {manualItems.length}
          {K.itemCount}
        </span>

        <span className="rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold text-secondary">
          {K.total} {items.length}
          {K.itemCount}
        </span>
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red"
        >
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="mt-5 rounded-xl border border-border bg-card px-4 py-10 text-center text-sm text-muted">
          {K.loading}
        </div>
      ) : (
        <div className="mt-6 space-y-7">
            <ReferenceGroup
              title={K.automaticGroup}
              description={K.automaticGroupDescription}
              items={automaticItems.filter(
                (item) =>
                  item.freshnessStatus !== "STALE",
              )}
              emptyMessage={"\ucd5c\uadfc 90\uc77c \uc774\ub0b4 \uc790\ub3d9 \ubc1c\uacac \ucc38\uace0\uc790\ub8cc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."}
            />

            {automaticItems.some(
              (item) =>
                item.freshnessStatus === "STALE",
            ) ? (
              <details className="rounded-xl border border-border bg-background">
                <summary className="cursor-pointer list-none px-4 py-3 text-sm font-bold text-secondary transition hover:text-primary">
                  {"\uc624\ub798\ub41c \uc790\ub8cc \u0020"}
                  {
                    automaticItems.filter(
                      (item) =>
                        item.freshnessStatus ===
                        "STALE",
                    ).length
                  }
                  {"\uac74 \ubcf4\uae30"}
                </summary>

                <div className="border-t border-border p-4">
                  <ReferenceGroup
                    title={"\uc624\ub798\ub41c \uc790\ub3d9 \ubc1c\uacac \ucc38\uace0\uc790\ub8cc"}
                    description={"\uacf5\uac1c \ud6c4 90\uc77c\uc774 \uc9c0\ub09c \uc790\ub8cc\uc785\ub2c8\ub2e4. \uae30\ub85d\uacfc \uc911\ubcf5 \ubc29\uc9c0\ub97c \uc704\ud574 \ubcf4\uad00\ud569\ub2c8\ub2e4."}
                    items={automaticItems.filter(
                      (item) =>
                        item.freshnessStatus ===
                        "STALE",
                    )}
                    emptyMessage={"\uc624\ub798\ub41c \uc790\ub3d9 \ubc1c\uacac \ucc38\uace0\uc790\ub8cc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."}
                  />
                </div>
              </details>
            ) : null}

          <ReferenceGroup
            title={K.manualGroup}
            description={
              K.manualGroupDescription
            }
            items={manualItems}
            emptyMessage={K.noManual}
          />
        </div>
      )}

      <p className="mt-6 rounded-xl border border-border bg-background px-4 py-3 text-xs leading-5 text-muted">
        {K.isolationNotice}
      </p>
    </section>
  );
}
