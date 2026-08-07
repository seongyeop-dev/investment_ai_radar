"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  ReferenceSubscriptionImportDialog,
} from "@/components/sources/reference-subscription-import-dialog";
import {
  listReferenceSubscriptions,
  updateReferenceSubscription,
} from "@/lib/api/analyst-references";
import { ApiClientError } from "@/lib/api/client";
import type {
  ReferenceMatchMode,
  ReferenceSubjectType,
  ReferenceSubscription,
  ReferenceSubscriptionUpdateInput,
} from "@/types/api";

const K = {
  expert: "\uC804\uBB38\uAC00",
  institution: "\uAE30\uAD00",
  publisher: "\uBC1C\uD589\uC0AC",
  allSource: "\uCD9C\uCC98 \uC804\uCCB4",
  authorMatch: "\uC800\uC790\uBA85 \uC77C\uCE58",
  keywordMatch: "\uD0A4\uC6CC\uB4DC \uC77C\uCE58",
  loadError:
    "\uAD00\uC2EC \uC804\uBB38\uAC00 \uAD6C\uB3C5\uC744 \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.",
  nameRequired:
    "\uD45C\uC2DC \uC774\uB984\uC744 \uC785\uB825\uD574\uC57C \uD569\uB2C8\uB2E4.",
  termsRequired:
    "\uC800\uC790\uBA85 \uB610\uB294 \uD0A4\uC6CC\uB4DC \uBC29\uC2DD\uC740 \uAC80\uC0C9\uC5B4\uAC00 \uD55C \uAC1C \uC774\uC0C1 \uD544\uC694\uD569\uB2C8\uB2E4.",
  saveDone:
    "\uAD6C\uB3C5 \uC124\uC815\uC744 \uC800\uC7A5\uD588\uC2B5\uB2C8\uB2E4.",
  saveError:
    "\uAD6C\uB3C5 \uC124\uC815\uC744 \uC800\uC7A5\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.",
  resumeDone:
    "\uC790\uB3D9 \uD655\uC778\uC744 \uB2E4\uC2DC \uC2DC\uC791\uD588\uC2B5\uB2C8\uB2E4.",
  pauseDone:
    "\uC790\uB3D9 \uD655\uC778\uC744 \uC911\uC9C0\uD588\uC2B5\uB2C8\uB2E4.",
  resumeError:
    "\uC790\uB3D9 \uD655\uC778\uC744 \uB2E4\uC2DC \uC2DC\uC791\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.",
  pauseError:
    "\uC790\uB3D9 \uD655\uC778\uC744 \uC911\uC9C0\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.",
  title:
    "\uAD00\uC2EC \uC804\uBB38\uAC00\u00B7\uAE30\uAD00 \uC790\uB3D9 \uAD6C\uB3C5",
  description:
    "\uB4F1\uB85D\uD55C \uC804\uBB38\uAC00\u00B7\uAE30\uAD00\uC758 \uACF5\uC2DD \uACF5\uAC1C \uCD9C\uCC98\uB97C \uB9E4\uC77C \uD655\uC778\uD569\uB2C8\uB2E4. \uBC1C\uACAC\uB41C \uC790\uB8CC\uB294 \uCC38\uACE0\uC790\uB8CC \uC601\uC5ED\uC5D0\uB9CC \uD45C\uC2DC\uB418\uBA70 \uC790\uB3D9 \uBD84\uC11D, \uC885\uBAA9 \uAD00\uB9AC \uBC29\uD5A5, \uBAA9\uD45C\uAC00 \uB610\uB294 \uD22C\uC790 \uD310\uB2E8 \uACC4\uC0B0\uC5D0\uB294 \uC0AC\uC6A9\uB418\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4.",
  register: "\uAD00\uC2EC \uB300\uC0C1 \uB4F1\uB85D",
  loading:
    "\uAD6C\uB3C5 \uBAA9\uB85D\uC744 \uBD88\uB7EC\uC624\uB294 \uC911\u2026",
  active: "\uC790\uB3D9 \uD655\uC778 \uC911",
  paused: "\uC790\uB3D9 \uD655\uC778 \uC911\uC9C0",
  autoCollected: "\uC790\uB3D9 \uC218\uC9D1",
  count: "\uAC74",
  cancelEdit: "\uC218\uC815 \uCDE8\uC18C",
  edit: "\uC124\uC815 \uC218\uC815",
  processing: "\uCC98\uB9AC \uC911\u2026",
  restore: "\uC790\uB3D9 \uD655\uC778 \uBCF5\uAD6C",
  source: "\uACF5\uC2DD \uCD9C\uCC98",
  domain: "\uCD9C\uCC98 \uB3C4\uBA54\uC778",
  matchMode: "\uAC80\uC0C9 \uBC29\uC2DD",
  autoReference:
    "\uC790\uB3D9 \uC218\uC9D1 \uCC38\uACE0\uC790\uB8CC",
  terms: "\uAC80\uC0C9\uC5B4",
  allPublic:
    "\uCD9C\uCC98\uC758 \uBAA8\uB4E0 \uACF5\uAC1C \uC790\uB8CC",
  updated:
    "\uB9C8\uC9C0\uB9C9 \uC124\uC815 \uBCC0\uACBD",
  editTitle:
    "\uAD6C\uB3C5 \uC124\uC815 \uC218\uC815",
  displayName: "\uD45C\uC2DC \uC774\uB984",
  allSourcePlaceholder:
    "\uCD9C\uCC98 \uC804\uCCB4 \uBC29\uC2DD\uC5D0\uC11C\uB294 \uAC80\uC0C9\uC5B4\uB97C \uC0AC\uC6A9\uD558\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4.",
  termsPlaceholder:
    "\uAC80\uC0C9\uC5B4\uB97C \uC904\uBC14\uAFC8 \uB610\uB294 \uC27C\uD45C\uB85C \uAD6C\uBD84\uD558\uC138\uC694.",
  dedupeHint:
    "\uC911\uBCF5 \uAC80\uC0C9\uC5B4\uB294 \uC800\uC7A5 \uC2DC \uC790\uB3D9\uC73C\uB85C \uC81C\uAC70\uB429\uB2C8\uB2E4.",
  cancel: "\uCDE8\uC18C",
  saving: "\uC800\uC7A5 \uC911\u2026",
  save: "\uBCC0\uACBD \uC800\uC7A5",
  empty:
    "\uB4F1\uB85D\uB41C \uAD00\uC2EC \uC804\uBB38\uAC00\u00B7\uAE30\uAD00\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.",
  emptyDescription:
    "\uACF5\uC2DD \uACF5\uAC1C \uCD9C\uCC98\uAC00 \uC900\uBE44\uB41C \uC804\uBB38\uAC00 \uB610\uB294 \uAE30\uAD00\uC744 \uB4F1\uB85D\uD558\uBA74 \uB9E4\uC77C \uC790\uB3D9\uC73C\uB85C \uC2E0\uADDC \uCC38\uACE0\uC790\uB8CC\uB97C \uD655\uC778\uD569\uB2C8\uB2E4.",
  created:
    "\uAD00\uC2EC \uB300\uC0C1 \uB4F1\uB85D\uC744 \uC644\uB8CC\uD588\uC2B5\uB2C8\uB2E4.",
} as const;

const subjectLabels: Record<
  ReferenceSubjectType,
  string
> = {
  EXPERT: K.expert,
  INSTITUTION: K.institution,
  PUBLISHER: K.publisher,
};

const matchModeLabels: Record<
  ReferenceMatchMode,
  string
> = {
  ALL_SOURCE: K.allSource,
  AUTHOR: K.authorMatch,
  KEYWORD: K.keywordMatch,
};

interface EditDraft {
  displayName: string;
  matchMode: ReferenceMatchMode;
  matchTermsText: string;
}

function errorMessage(
  reason: unknown,
  fallback: string,
): string {
  return reason instanceof ApiClientError
    ? reason.message
    : fallback;
}

function normalizeTerms(
  value: string,
): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];

  for (const rawTerm of value.split(/[\n,]/)) {
    const term = rawTerm.trim();

    if (!term) {
      continue;
    }

    const key = term.toLocaleLowerCase();

    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    normalized.push(term);
  }

  return normalized;
}

function formatUpdatedAt(
  value: string,
): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("ko-KR");
}

export function ReferenceSubscriptionPanel() {
  const [items, setItems] = useState<
    ReferenceSubscription[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dialogOpen, setDialogOpen] =
    useState(false);
  const [editingId, setEditingId] = useState<
    string | null
  >(null);
  const [draft, setDraft] =
    useState<EditDraft | null>(null);
  const [savingId, setSavingId] = useState<
    string | null
  >(null);

  useEffect(() => {
    const controller = new AbortController();

    listReferenceSubscriptions(
      {
        limit: 100,
        offset: 0,
      },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) {
          return;
        }

        setItems(response.items);
        setError("");
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            errorMessage(
              reason,
              K.loadError,
            ),
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  async function refreshSubscriptions() {
    setLoading(true);

    try {
      const response =
        await listReferenceSubscriptions({
          limit: 100,
          offset: 0,
        });

      setItems(response.items);
      setError("");
    } catch (reason: unknown) {
      setError(
        errorMessage(
          reason,
          K.loadError,
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  function beginEdit(
    item: ReferenceSubscription,
  ) {
    setEditingId(item.id);
    setDraft({
      displayName: item.displayName,
      matchMode: item.matchMode,
      matchTermsText:
        item.matchTerms.join("\n"),
    });
    setError("");
    setNotice("");
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft(null);
    setError("");
  }

  async function saveEdit(
    item: ReferenceSubscription,
  ) {
    if (!draft) {
      return;
    }

    const displayName =
      draft.displayName.trim();

    if (!displayName) {
      setError(K.nameRequired);
      return;
    }

    const matchTerms =
      draft.matchMode === "ALL_SOURCE"
        ? []
        : normalizeTerms(
            draft.matchTermsText,
          );

    if (
      draft.matchMode !== "ALL_SOURCE" &&
      matchTerms.length === 0
    ) {
      setError(K.termsRequired);
      return;
    }

    const input:
      ReferenceSubscriptionUpdateInput = {
        displayName,
        matchMode: draft.matchMode,
        matchTerms,
      };

    setSavingId(item.id);
    setError("");
    setNotice("");

    try {
      const updated =
        await updateReferenceSubscription(
          item.id,
          input,
        );

      setItems((current) =>
        current.map((candidate) =>
          candidate.id === updated.id
            ? updated
            : candidate,
        ),
      );

      setEditingId(null);
      setDraft(null);
      setNotice(
        `${updated.displayName} ${K.saveDone}`,
      );
    } catch (reason: unknown) {
      setError(
        errorMessage(
          reason,
          K.saveError,
        ),
      );
    } finally {
      setSavingId(null);
    }
  }

  async function toggleSubscription(
    item: ReferenceSubscription,
  ) {
    const nextEnabled = !item.enabled;

    setSavingId(item.id);
    setError("");
    setNotice("");

    try {
      const updated =
        await updateReferenceSubscription(
          item.id,
          {
            enabled: nextEnabled,
          },
        );

      setItems((current) =>
        current.map((candidate) =>
          candidate.id === updated.id
            ? updated
            : candidate,
        ),
      );

      if (editingId === item.id) {
        setEditingId(null);
        setDraft(null);
      }

      setNotice(
        `${updated.displayName} ${
          nextEnabled
            ? K.resumeDone
            : K.pauseDone
        }`,
      );
    } catch (reason: unknown) {
      setError(
        errorMessage(
          reason,
          nextEnabled
            ? K.resumeError
            : K.pauseError,
        ),
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <>
      <section className="rounded-2xl border border-cyan/30 bg-cyan/5 p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan">
              관심 출처 자동 확인
            </p>

            <h2 className="mt-1 text-lg font-bold">
              {K.title}
            </h2>

            <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary">
              {K.description}
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              setDialogOpen(true);
              setError("");
              setNotice("");
            }}
            disabled={savingId !== null}
            className="inline-flex min-h-11 w-full shrink-0 items-center justify-center rounded-xl bg-cyan px-5 text-sm font-bold text-background disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {K.register}
          </button>
        </div>

        {error ? (
          <p
            role="alert"
            className="mt-4 rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red"
          >
            {error}
          </p>
        ) : null}

        {notice ? (
          <p
            role="status"
            className="mt-4 rounded-xl border border-green/30 bg-green/10 p-3 text-sm text-green"
          >
            {notice}
          </p>
        ) : null}

        <div className="mt-5">
          {loading ? (
            <div className="rounded-xl border border-border bg-card px-4 py-8 text-center text-sm text-muted">
              {K.loading}
            </div>
          ) : items.length ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {items.map((item) => {
                const editing =
                  editingId === item.id &&
                  draft !== null;
                const saving =
                  savingId === item.id;

                return (
                  <article
                    key={item.id}
                    className="rounded-xl border border-border bg-card p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap gap-2">
                          <span className="rounded-full border border-cyan/30 bg-cyan/10 px-2.5 py-1 text-xs font-bold text-cyan">
                            {
                              subjectLabels[
                                item.subjectType
                              ]
                            }
                          </span>

                          <span
                            className={
                              item.enabled
                                ? "rounded-full border border-green/30 bg-green/10 px-2.5 py-1 text-xs font-bold text-green"
                                : "rounded-full border border-border px-2.5 py-1 text-xs font-bold text-muted"
                            }
                          >
                            {item.enabled
                              ? K.active
                              : K.paused}
                          </span>

                          <span className="rounded-full border border-border bg-background px-2.5 py-1 text-xs font-bold text-secondary">
                            {K.autoCollected}{" "}
                            {
                              item.automaticReferenceCount
                            }
                            {K.count}
                          </span>
                        </div>

                        <h3 className="mt-3 break-words text-base font-bold">
                          {item.displayName}
                        </h3>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            editing
                              ? cancelEdit()
                              : beginEdit(item)
                          }
                          disabled={
                            savingId !== null &&
                            !saving
                          }
                          className="inline-flex min-h-9 items-center justify-center rounded-lg border border-border px-3 text-xs font-bold text-secondary hover:border-cyan/50 hover:text-cyan disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {editing
                            ? K.cancelEdit
                            : K.edit}
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            void toggleSubscription(
                              item,
                            );
                          }}
                          disabled={
                            savingId !== null
                          }
                          className={
                            item.enabled
                              ? "inline-flex min-h-9 items-center justify-center rounded-lg border border-red/40 px-3 text-xs font-bold text-red hover:bg-red/10 disabled:cursor-not-allowed disabled:opacity-50"
                              : "inline-flex min-h-9 items-center justify-center rounded-lg border border-green/40 px-3 text-xs font-bold text-green hover:bg-green/10 disabled:cursor-not-allowed disabled:opacity-50"
                          }
                        >
                          {saving
                            ? K.processing
                            : item.enabled
                              ? K.paused
                              : K.restore}
                        </button>
                      </div>
                    </div>

                    <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-xs text-muted">
                          {K.source}
                        </dt>
                        <dd className="mt-1 break-words font-semibold">
                          {item.source.name}
                        </dd>
                      </div>

                      <div>
                        <dt className="text-xs text-muted">
                          {K.domain}
                        </dt>
                        <dd className="mt-1 break-all font-semibold">
                          {item.source.domain}
                        </dd>
                      </div>

                      <div>
                        <dt className="text-xs text-muted">
                          {K.matchMode}
                        </dt>
                        <dd className="mt-1 font-semibold">
                          {
                            matchModeLabels[
                              item.matchMode
                            ]
                          }
                        </dd>
                      </div>

                      <div>
                        <dt className="text-xs text-muted">
                          {K.autoReference}
                        </dt>
                        <dd className="mt-1 font-semibold">
                          {
                            item.automaticReferenceCount
                          }
                          {K.count}
                        </dd>
                      </div>

                      <div className="sm:col-span-2">
                        <dt className="text-xs text-muted">
                          {K.terms}
                        </dt>
                        <dd className="mt-1 break-words font-semibold">
                          {item.matchTerms.length
                            ? item.matchTerms.join(
                                ", ",
                              )
                            : K.allPublic}
                        </dd>
                      </div>

                      <div className="sm:col-span-2">
                        <dt className="text-xs text-muted">
                          {K.updated}
                        </dt>
                        <dd className="mt-1 text-secondary">
                          {formatUpdatedAt(
                            item.updatedAt,
                          )}
                        </dd>
                      </div>
                    </dl>

                    {editing && draft ? (
                      <div className="mt-5 rounded-xl border border-cyan/30 bg-background p-4">
                        <h4 className="text-sm font-bold">
                          {K.editTitle}
                        </h4>

                        <div className="mt-4 space-y-4">
                          <label className="block">
                            <span className="text-xs font-semibold text-secondary">
                              {K.displayName}
                            </span>

                            <input
                              type="text"
                              value={
                                draft.displayName
                              }
                              onChange={(event) =>
                                setDraft({
                                  ...draft,
                                  displayName:
                                    event.target
                                      .value,
                                })
                              }
                              disabled={saving}
                              maxLength={200}
                              className="mt-2 min-h-11 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-cyan disabled:opacity-60"
                            />
                          </label>

                          <label className="block">
                            <span className="text-xs font-semibold text-secondary">
                              {K.matchMode}
                            </span>

                            <select
                              value={
                                draft.matchMode
                              }
                              onChange={(event) =>
                                setDraft({
                                  ...draft,
                                  matchMode:
                                    event.target
                                      .value as ReferenceMatchMode,
                                })
                              }
                              disabled={saving}
                              className="mt-2 min-h-11 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-cyan disabled:opacity-60"
                            >
                              <option value="ALL_SOURCE">
                                {K.allSource}
                              </option>
                              <option value="AUTHOR">
                                {K.authorMatch}
                              </option>
                              <option value="KEYWORD">
                                {K.keywordMatch}
                              </option>
                            </select>
                          </label>

                          <label className="block">
                            <span className="text-xs font-semibold text-secondary">
                              {K.terms}
                            </span>

                            <textarea
                              value={
                                draft.matchTermsText
                              }
                              onChange={(event) =>
                                setDraft({
                                  ...draft,
                                  matchTermsText:
                                    event.target
                                      .value,
                                })
                              }
                              disabled={
                                saving ||
                                draft.matchMode ===
                                  "ALL_SOURCE"
                              }
                              rows={4}
                              placeholder={
                                draft.matchMode ===
                                "ALL_SOURCE"
                                  ? K.allSourcePlaceholder
                                  : K.termsPlaceholder
                              }
                              className="mt-2 w-full rounded-xl border border-border bg-card px-3 py-3 text-sm leading-6 outline-none focus:border-cyan disabled:opacity-60"
                            />

                            <span className="mt-1 block text-xs leading-5 text-muted">
                              {K.dedupeHint}
                            </span>
                          </label>

                          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                            <button
                              type="button"
                              onClick={cancelEdit}
                              disabled={saving}
                              className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-bold text-secondary disabled:opacity-50"
                            >
                              {K.cancel}
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                void saveEdit(
                                  item,
                                );
                              }}
                              disabled={saving}
                              className="inline-flex min-h-10 items-center justify-center rounded-lg bg-cyan px-4 text-sm font-bold text-background disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {saving
                                ? K.saving
                                : K.save}
                            </button>
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card px-4 py-8 text-center">
              <p className="text-sm font-semibold">
                {K.empty}
              </p>

              <p className="mt-2 text-xs leading-5 text-muted">
                {K.emptyDescription}
              </p>
            </div>
          )}
        </div>
      </section>

      {dialogOpen ? (
        <ReferenceSubscriptionImportDialog
          onClose={() =>
            setDialogOpen(false)
          }
          onCreated={() => {
            setDialogOpen(false);
            setNotice(K.created);
            void refreshSubscriptions();
          }}
        />
      ) : null}
    </>
  );
}
