"use client";

import {
  type FormEvent,
  useEffect,
  useState,
} from "react";

import {
  importReferenceSource,
  listReferenceSourcesForManagement,
  updateReferenceSource,
} from "@/lib/api/analyst-references";
import { ApiClientError } from "@/lib/api/client";
import type {
  ReferenceSource,
  ReferenceSourceImportInput,
  ReferenceSourceImportPreview,
  ReferenceSourceUpdateInput,
  SourceGrade,
} from "@/types/api";

const K = {
  title: "\uacf5\uc2dd \ucd9c\ucc98 \uad00\ub9ac",
  description:
    "\uc804\ubb38\uac00\u00b7\uae30\uad00 \uc790\ub3d9 \uad6c\ub3c5\uc5d0\uc11c \uc0ac\uc6a9\ud558\ub294 \uacf5\uc2dd \uacf5\uac1c \ucd9c\ucc98\uc640 \uc218\uc9d1 \uc124\uc815\uc744 \uad00\ub9ac\ud569\ub2c8\ub2e4. \uc774 \ud654\uba74\uc740 수집 주소(URL) \ubb38\uc790\uc5f4\ub9cc \uac80\uc99d\ud558\uba70 \uc678\ubd80 \uc8fc\uc18c\ub97c \uc790\ub3d9\uc73c\ub85c \uc5f4\uac70\ub098 \ubb38\uc11c\ub97c \ub0b4\ub824\ubc1b\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  register: "\uacf5\uc2dd \ucd9c\ucc98 \ub4f1\ub85d",
  closeRegister: "\ub4f1\ub85d \ucc3d \ub2eb\uae30",
  loadError:
    "\uacf5\uc2dd \ucd9c\ucc98 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
  loading:
    "\uacf5\uc2dd \ucd9c\ucc98 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\u2026",
  empty:
    "\ub4f1\ub85d\ub41c \uacf5\uc2dd \ucd9c\ucc98\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.",
  emptyDescription:
    "\uacf5\uac1c \ucd9c\ucc98\uc758 \uba54\ud0c0\ub370\uc774\ud130\uc640 \uc218\uc9d1 \uc124\uc815\uc744 \uac80\uc99d\ud55c \ub4a4 \ub4f1\ub85d\ud574 \uc8fc\uc138\uc694.",
  newTitle:
    "\uc2e0\uaddc \uacf5\uc2dd \ucd9c\ucc98 \ub4f1\ub85d",
  newDescription:
    "\ub4f1\ub85d \uc804 \uac80\uc99d\uc740 \uc785\ub825 \ud615\uc2dd\uacfc \uc911\ubcf5\ub9cc \ud655\uc778\ud569\ub2c8\ub2e4. 수집 주소(URL)\ub85c \uc678\ubd80 \uc694\uccad\uc744 \ubcf4\ub0b4\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  officialActive:
    "\uacf5\uc2dd\u00b7\ud65c\uc131 \uc0c1\ud0dc\ub85c \ub4f1\ub85d",
  name: "\ucd9c\ucc98 \uc774\ub984",
  grade: "\ucd9c\ucc98 \ub4f1\uae09",
  domain: "\uacf5\uc2dd \ub3c4\uba54\uc778",
  provider: "수집 방식",
  feedUrl: "수집 주소(URL)",
  feedHint:
    "HTTPS \uacf5\uac1c \uc8fc\uc18c\ub9cc \ud5c8\uc6a9\ud569\ub2c8\ub2e4. \uc785\ub825\ud558\uac70\ub098 \uac80\uc99d\ud574\ub3c4 \ube0c\ub77c\uc6b0\uc800\uc5d0\uc11c \ud574\ub2f9 \uc8fc\uc18c\ub97c \uc5f4\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  language: "\uc5b8\uc5b4 \ucf54\ub4dc",
  originalName: "\uc6d0\ub798 \ucd9c\ucc98 \uc774\ub984",
  optional: "\uc120\ud0dd \uc785\ub825",
  interval: "\uc694\uccad \uc8fc\uae30(\ucd08)",
  timeout: "\ud0c0\uc784\uc544\uc6c3(\ucd08)",
  maxItems: "\ucd5c\ub300 \uc218\uc9d1 \uac74\uc218",
  cancel: "\ucde8\uc18c",
  previewing: "\uac80\uc99d \uc911\u2026",
  preview: "\ub4f1\ub85d \uc804 \uac80\uc99d",
  confirming: "\ub4f1\ub85d \uc911\u2026",
  confirm: "\ucd5c\uc885 \ub4f1\ub85d",
  previewTitle:
    "\ub4f1\ub85d \uc804 \uac80\uc99d \uacb0\uacfc",
  canCreate: "\ub4f1\ub85d \uac00\ub2a5",
  blocked: "\ub4f1\ub85d \ucc28\ub2e8",
  normalizedName:
    "\uc815\uaddc\ud654\ub41c \uc774\ub984",
  sameSource: "\ub3d9\uc77c \ucd9c\ucc98",
  exists: "\uc788\uc74c",
  none: "\uc5c6\uc74c",
  duplicateFields: "\uc911\ubcf5 \ud544\ub4dc",
  noWarnings:
    "\ucd94\uac00 \uac80\uc99d \uacbd\uace0\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.",
  previewOnly:
    "\ud604\uc7ac\ub294 \uac80\uc99d\ub9cc \uc218\ud589\ud588\uc2b5\ub2c8\ub2e4. DB\uc5d0\ub294 \uc800\uc7a5\ub418\uc9c0 \uc54a\uc558\uace0 외부 수집 주소\uc5d0\ub3c4 \uc811\uc18d\ud558\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4.",
  active: "\ud65c\uc131",
  stopped: "\uc911\uc9c0",
  official: "\uacf5\uc2dd \uc0c1\ud0dc",
  officialSource: "\uacf5\uc2dd \ucd9c\ucc98",
  unverified: "\ubbf8\ud655\uc778 \ucd9c\ucc98",
  requestInterval: "\uc694\uccad \uc8fc\uae30",
  seconds: "\ucd08",
  maxCollect: "\ucd5c\ub300 \uc218\uc9d1",
  count: "\uac74",
  activeSubscriptions: "\ud65c\uc131 \uad6c\ub3c5",
  totalSubscriptions: "\uc804\uccb4 \uad6c\ub3c5",
  edit: "\uc6b4\uc601 \uc124\uc815 \uc218\uc815",
  cancelEdit: "\uc218\uc815 \ucde8\uc18c",
  stopSource: "\ucd9c\ucc98 \uc911\uc9c0",
  restoreSource: "\ucd9c\ucc98 \ubcf5\uad6c",
  processing: "\ucc98\ub9ac \uc911\u2026",
  protection:
    "\ud65c\uc131 \uad6c\ub3c5\uc774 \uc5f0\uacb0\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. \ucd9c\ucc98\ub97c \uc911\uc9c0\ud558\ub824\uba74 \uba3c\uc800 \uc5f0\uacb0\ub41c \uad00\uc2ec \ub300\uc0c1\uc758 \uc790\ub3d9 \ud655\uc778\uc744 \ubaa8\ub450 \uc911\uc9c0\ud574\uc57c \ud569\ub2c8\ub2e4.",
  editTitle: "\uc6b4\uc601 \uc124\uc815 \uc218\uc815",
  save: "\ubcc0\uacbd \uc800\uc7a5",
  saving: "\uc800\uc7a5 \uc911\u2026",
  saved:
    "\uc6b4\uc601 \uc124\uc815\uc744 \uc800\uc7a5\ud588\uc2b5\ub2c8\ub2e4.",
  restored:
    "\ucd9c\ucc98\ub97c \ub2e4\uc2dc \ud65c\uc131\ud654\ud588\uc2b5\ub2c8\ub2e4.",
  sourceStopped:
    "\ucd9c\ucc98\ub97c \uc911\uc9c0\ud588\uc2b5\ub2c8\ub2e4.",
  created:
    "\uacf5\uc2dd \ucd9c\ucc98\ub97c \ub4f1\ub85d\ud588\uc2b5\ub2c8\ub2e4.",
  activeGuard:
    "\ud65c\uc131 \uad6c\ub3c5\uc774 \uc5f0\uacb0\ub41c \ucd9c\ucc98\ub294 \ubc14\ub85c \uc911\uc9c0\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4. \uba3c\uc800 \uc5f0\uacb0\ub41c \uad00\uc2ec \ub300\uc0c1\uc758 \uc790\ub3d9 \ud655\uc778\uc744 \ubaa8\ub450 \uc911\uc9c0\ud574 \uc8fc\uc138\uc694.",
  nameRequired:
    "\ucd9c\ucc98 \uc774\ub984\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  domainRequired:
    "\ucd9c\ucc98 \ub3c4\uba54\uc778\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  feedRequired:
    "수집 주소(URL)\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  providerRequired:
    "수집 방식\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  languageRequired:
    "\uc5b8\uc5b4 \ucf54\ub4dc\ub97c \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  intervalInvalid:
    "\uc694\uccad \uc8fc\uae30\ub294 60\ucd08 \uc774\uc0c1 604800\ucd08 \uc774\ud558\ub85c \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  timeoutInvalid:
    "\ud0c0\uc784\uc544\uc6c3\uc740 1\ucd08 \uc774\uc0c1 120\ucd08 \uc774\ud558\ub85c \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  maxInvalid:
    "\ucd5c\ub300 \uc218\uc9d1 \uac74\uc218\ub294 1\uac74 \uc774\uc0c1 500\uac74 \uc774\ud558\ub85c \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
  previewError:
    "\uacf5\uc2dd \ucd9c\ucc98 \ub4f1\ub85d \uc804 \uac80\uc99d\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.",
  createError:
    "\uacf5\uc2dd \ucd9c\ucc98\ub97c \ub4f1\ub85d\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
  saveError:
    "\uacf5\uc2dd \ucd9c\ucc98 \uc6b4\uc601 \uc124\uc815\uc744 \uc800\uc7a5\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
  restoreError:
    "\uacf5\uc2dd \ucd9c\ucc98\ub97c \ubcf5\uad6c\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
  stopError:
    "\uacf5\uc2dd \ucd9c\ucc98\ub97c \uc911\uc9c0\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
} as const;

const warningLabels: Record<
  string,
  string
> = {
  INVALID_DOMAIN:
    "\uacf5\uac1c \uc778\ud130\ub137 \ub3c4\uba54\uc778 \ud615\uc2dd\uc774 \uc544\ub2d9\ub2c8\ub2e4.",
  INVALID_FEED_URL:
    "수집 주소(URL) \ud615\uc2dd\uc744 \ud655\uc778\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.",
  INSECURE_FEED_URL:
    "수집 주소(URL)\uc740 HTTPS \uc8fc\uc18c\ub9cc \ud5c8\uc6a9\ub429\ub2c8\ub2e4.",
  UNSAFE_FEED_HOST:
    "\ub85c\uceec\u00b7\uc0ac\uc124 \ub124\ud2b8\uc6cc\ud06c \uc8fc\uc18c\ub294 \uc0ac\uc6a9\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.",
  FEED_DOMAIN_MISMATCH:
    "수집 주소(URL)\uc758 \ud638\uc2a4\ud2b8\uac00 \ub4f1\ub85d \ub3c4\uba54\uc778\uacfc \uc77c\uce58\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  FEED_URL_REQUIRED:
    "\ud65c\uc131 \ucd9c\ucc98\uc5d0\ub294 수집 주소(URL)\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
  PROVIDER_TYPE_REQUIRED:
    "\ud65c\uc131 \ucd9c\ucc98\uc5d0\ub294 수집 방식\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
  DUPLICATE_SOURCE_NAME:
    "\ub3d9\uc77c\ud55c \uc774\ub984\uc758 \ucd9c\ucc98\uac00 \uc774\ubbf8 \ub4f1\ub85d\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.",
  DUPLICATE_FEED_URL:
    "\ub3d9\uc77c\ud55c 수집 주소(URL)\uc758 \ucd9c\ucc98\uac00 \uc774\ubbf8 \ub4f1\ub85d\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.",
  SOURCE_NOT_OFFICIAL:
    "\uacf5\uc2dd \ucd9c\ucc98 \uc0c1\ud0dc\uac00 \uc544\ub2d9\ub2c8\ub2e4.",
  SOURCE_DISABLED:
    "\ucd9c\ucc98\uac00 \ube44\ud65c\uc131 \uc0c1\ud0dc\uc785\ub2c8\ub2e4.",
};

const gradeLabels: Record<
  SourceGrade,
  string
> = {
  A: "A \u00b7 1\ucc28 \uacf5\uc2dd \ucd9c\ucc98",
  B: "B \u00b7 \uc2e0\ub8b0\ub3c4 \ub192\uc740 \ubcf4\uc870 \ucd9c\ucc98",
  C: "C \u00b7 \ucd94\uac00 \ud655\uc778 \ud544\uc694",
  D: "D \u00b7 \ucc38\uace0\uc6a9",
};

const INPUT_CLASS =
  "min-h-11 w-full rounded-xl border border-border bg-card px-3 " +
  "text-sm text-foreground placeholder:text-muted outline-none " +
  "focus:border-cyan disabled:cursor-not-allowed disabled:opacity-60";

interface ImportDraft {
  name: string;
  sourceGrade: SourceGrade;
  domain: string;
  feedUrl: string;
  providerType: string;
  language: string;
  requestIntervalSeconds: string;
  timeoutSeconds: string;
  maxItems: string;
  originalSourceName: string;
}

interface EditDraft {
  sourceGrade: SourceGrade;
  language: string;
  requestIntervalSeconds: string;
  timeoutSeconds: string;
  maxItems: string;
}

const EMPTY_IMPORT_DRAFT: ImportDraft = {
  name: "",
  sourceGrade: "A",
  domain: "",
  feedUrl: "",
  providerType: "REFERENCE_INDEX",
  language: "en",
  requestIntervalSeconds: "21600",
  timeoutSeconds: "20",
  maxItems: "50",
  originalSourceName: "",
};

function errorMessage(
  reason: unknown,
  fallback: string,
): string {
  return reason instanceof ApiClientError
    ? reason.message
    : fallback;
}

function warningLabel(
  value: string,
): string {
  return warningLabels[value] ?? value;
}

const providerTypeLabels: Record<string, string> = {
  REFERENCE_INDEX: "공개자료 목록",
};

const languageLabels: Record<string, string> = {
  en: "영어",
  ko: "한국어",
};

function providerTypeLabel(
  value: string | null | undefined,
): string {
  if (!value) return K.none;
  return providerTypeLabels[value] ?? "기타 수집 방식";
}

function languageLabel(
  value: string | null | undefined,
): string {
  if (!value) return K.none;
  return languageLabels[value] ?? value;
}

function parseInteger(
  value: string,
): number {
  return Number.parseInt(
    value.trim(),
    10,
  );
}

function validateOperatingValues(
  requestIntervalSeconds: number,
  timeoutSeconds: number,
  maxItems: number,
): string {
  if (
    !Number.isInteger(
      requestIntervalSeconds,
    ) ||
    requestIntervalSeconds < 60 ||
    requestIntervalSeconds > 604800
  ) {
    return K.intervalInvalid;
  }

  if (
    !Number.isInteger(timeoutSeconds) ||
    timeoutSeconds < 1 ||
    timeoutSeconds > 120
  ) {
    return K.timeoutInvalid;
  }

  if (
    !Number.isInteger(maxItems) ||
    maxItems < 1 ||
    maxItems > 500
  ) {
    return K.maxInvalid;
  }

  return "";
}

export function ReferenceSourceManagementPanel() {
  const [items, setItems] = useState<
    ReferenceSource[]
  >([]);
  const [loading, setLoading] =
    useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] =
    useState("");
  const [showImport, setShowImport] =
    useState(false);
  const [importDraft, setImportDraft] =
    useState<ImportDraft>({
      ...EMPTY_IMPORT_DRAFT,
    });
  const [preview, setPreview] =
    useState<ReferenceSourceImportPreview | null>(
      null,
    );
  const [previewLoading, setPreviewLoading] =
    useState(false);
  const [confirmLoading, setConfirmLoading] =
    useState(false);
  const [editingId, setEditingId] =
    useState<string | null>(null);
  const [editDraft, setEditDraft] =
    useState<EditDraft | null>(null);
  const [savingId, setSavingId] =
    useState<string | null>(null);

  useEffect(() => {
    const controller =
      new AbortController();

    listReferenceSourcesForManagement(
      {
        limit: 100,
        offset: 0,
      },
      controller.signal,
    )
      .then((response) => {
        if (!controller.signal.aborted) {
          setItems(response.items);
          setError("");
        }
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
            K.loadError,
          ),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  async function refreshSources() {
    setLoading(true);

    try {
      const response =
        await listReferenceSourcesForManagement(
          {
            limit: 100,
            offset: 0,
          },
        );

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

  function resetImport() {
    setImportDraft({
      ...EMPTY_IMPORT_DRAFT,
    });
    setPreview(null);
    setError("");
  }

  function updateImportDraft<
    TKey extends keyof ImportDraft,
  >(
    key: TKey,
    value: ImportDraft[TKey],
  ) {
    setImportDraft((current) => ({
      ...current,
      [key]: value,
    }));
    setPreview(null);
    setError("");
    setNotice("");
  }

  function createImportPayload(
    confirm: boolean,
  ): ReferenceSourceImportInput {
    return {
      name: importDraft.name.trim(),
      sourceGrade:
        importDraft.sourceGrade,
      domain: importDraft.domain.trim(),
      official: true,
      enabled: true,
      feedUrl:
        importDraft.feedUrl.trim(),
      providerType:
        importDraft.providerType.trim(),
      language:
        importDraft.language.trim(),
      requestIntervalSeconds:
        parseInteger(
          importDraft.requestIntervalSeconds,
        ),
      timeoutSeconds:
        parseInteger(
          importDraft.timeoutSeconds,
        ),
      maxItems:
        parseInteger(
          importDraft.maxItems,
        ),
      originalSourceName:
        importDraft.originalSourceName.trim() ||
        null,
      confirm,
    };
  }

  function validateImport(): string {
    if (!importDraft.name.trim()) {
      return K.nameRequired;
    }

    if (!importDraft.domain.trim()) {
      return K.domainRequired;
    }

    if (!importDraft.feedUrl.trim()) {
      return K.feedRequired;
    }

    if (!importDraft.providerType.trim()) {
      return K.providerRequired;
    }

    if (!importDraft.language.trim()) {
      return K.languageRequired;
    }

    return validateOperatingValues(
      parseInteger(
        importDraft.requestIntervalSeconds,
      ),
      parseInteger(
        importDraft.timeoutSeconds,
      ),
      parseInteger(
        importDraft.maxItems,
      ),
    );
  }

  async function previewImport(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const validationError =
      validateImport();

    if (validationError) {
      setError(validationError);
      return;
    }

    setPreviewLoading(true);
    setError("");
    setNotice("");

    try {
      const result =
        await importReferenceSource(
          createImportPayload(false),
        );

      if (result.confirmed) {
        throw new Error(
          "Unexpected confirmed response.",
        );
      }

      setPreview(result);
    } catch (reason: unknown) {
      setError(
        errorMessage(
          reason,
          K.previewError,
        ),
      );
    } finally {
      setPreviewLoading(false);
    }
  }

  async function confirmImport() {
    const validationError =
      validateImport();

    if (validationError) {
      setError(validationError);
      return;
    }

    setConfirmLoading(true);
    setError("");

    try {
      const result =
        await importReferenceSource(
          createImportPayload(true),
        );

      if (!result.confirmed) {
        throw new Error(
          "Unexpected preview response.",
        );
      }

      setNotice(
        `${result.source.name} ${K.created}`,
      );
      setShowImport(false);
      resetImport();
      await refreshSources();
    } catch (reason: unknown) {
      setError(
        errorMessage(
          reason,
          K.createError,
        ),
      );
    } finally {
      setConfirmLoading(false);
    }
  }

  function beginEdit(
    source: ReferenceSource,
  ) {
    setEditingId(source.id);
    setEditDraft({
      sourceGrade:
        source.sourceGrade,
      language: source.language,
      requestIntervalSeconds: String(
        source.requestIntervalSeconds,
      ),
      timeoutSeconds: String(
        source.timeoutSeconds,
      ),
      maxItems: String(
        source.maxItems,
      ),
    });
    setError("");
    setNotice("");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft(null);
    setError("");
  }

  async function saveEdit(
    source: ReferenceSource,
  ) {
    if (!editDraft) {
      return;
    }

    const requestIntervalSeconds =
      parseInteger(
        editDraft.requestIntervalSeconds,
      );
    const timeoutSeconds =
      parseInteger(
        editDraft.timeoutSeconds,
      );
    const maxItems =
      parseInteger(
        editDraft.maxItems,
      );

    const validationError =
      validateOperatingValues(
        requestIntervalSeconds,
        timeoutSeconds,
        maxItems,
      );

    if (validationError) {
      setError(validationError);
      return;
    }

    if (!editDraft.language.trim()) {
      setError(K.languageRequired);
      return;
    }

    const input:
      ReferenceSourceUpdateInput = {
      sourceGrade:
        editDraft.sourceGrade,
      language:
        editDraft.language.trim(),
      requestIntervalSeconds,
      timeoutSeconds,
      maxItems,
    };

    setSavingId(source.id);
    setError("");
    setNotice("");

    try {
      const updated =
        await updateReferenceSource(
          source.id,
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
      setEditDraft(null);
      setNotice(
        `${updated.name} ${K.saved}`,
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

  async function toggleSource(
    source: ReferenceSource,
  ) {
    if (
      source.enabled &&
      source.activeSubscriptionCount > 0
    ) {
      setError(K.activeGuard);
      setNotice("");
      return;
    }

    const nextEnabled =
      !source.enabled;

    setSavingId(source.id);
    setError("");
    setNotice("");

    try {
      const updated =
        await updateReferenceSource(
          source.id,
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

      setNotice(
        `${updated.name} ${
          nextEnabled
            ? K.restored
            : K.sourceStopped
        }`,
      );
    } catch (reason: unknown) {
      setError(
        errorMessage(
          reason,
          nextEnabled
            ? K.restoreError
            : K.stopError,
        ),
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-panel">
      <div className="flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-gold">
            공식 출처
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
            const next = !showImport;

            setShowImport(next);
            setError("");
            setNotice("");

            if (!next) {
              resetImport();
            }
          }}
          className="inline-flex min-h-10 items-center justify-center rounded-xl border border-[#f0b90b] bg-[#f0b90b] px-4 text-sm font-bold text-[#0b0e11] shadow-sm transition hover:bg-[#f8c934]"
        >
          {showImport
            ? K.closeRegister
            : K.register}
        </button>
      </div>

      {notice ? (
        <p className="mt-4 rounded-xl border border-green/40 bg-green/10 p-3 text-sm text-green">
          {notice}
        </p>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red"
        >
          {error}
        </p>
      ) : null}

      {showImport ? (
        <form
          onSubmit={previewImport}
          className="mt-5 rounded-2xl border border-gold/30 bg-card p-4"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="font-bold">
                {K.newTitle}
              </h3>
              <p className="mt-1 text-xs leading-5 text-muted">
                {K.newDescription}
              </p>
            </div>

            <span className="rounded-full border border-green/40 bg-green/10 px-3 py-1 text-xs font-bold text-green">
              {K.officialActive}
            </span>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-semibold">
              {K.name}
              <input
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.name}
                onChange={(event) =>
                  updateImportDraft(
                    "name",
                    event.target.value,
                  )
                }
                placeholder="Oaktree Howard Marks Memos"
              />
            </label>

            <label className="block text-sm font-semibold">
              {K.grade}
              <select
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.sourceGrade}
                onChange={(event) =>
                  updateImportDraft(
                    "sourceGrade",
                    event.target
                      .value as SourceGrade,
                  )
                }
              >
                {(
                  Object.entries(
                    gradeLabels,
                  ) as Array<
                    [SourceGrade, string]
                  >
                ).map(
                  ([value, label]) => (
                    <option
                      key={value}
                      value={value}
                    >
                      {label}
                    </option>
                  ),
                )}
              </select>
            </label>

            <label className="block text-sm font-semibold">
              {K.domain}
              <input
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.domain}
                onChange={(event) =>
                  updateImportDraft(
                    "domain",
                    event.target.value,
                  )
                }
                placeholder="example.com"
              />
            </label>

            <label className="block text-sm font-semibold">
              {K.provider}
              <select
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.providerType}
                onChange={(event) =>
                  updateImportDraft(
                    "providerType",
                    event.target.value,
                  )
                }
              >
                <option value="REFERENCE_INDEX">
                  공개자료 목록
                </option>
              </select>
            </label>

            <label className="block text-sm font-semibold sm:col-span-2">
              {K.feedUrl}
              <input
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.feedUrl}
                onChange={(event) =>
                  updateImportDraft(
                    "feedUrl",
                    event.target.value,
                  )
                }
                placeholder="https://example.com/insights"
              />
              <span className="mt-1 block text-xs leading-5 text-muted">
                {K.feedHint}
              </span>
            </label>

            <label className="block text-sm font-semibold">
              {K.language}
              <select
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.language}
                onChange={(event) =>
                  updateImportDraft(
                    "language",
                    event.target.value,
                  )
                }
              >
                <option value="ko">한국어</option>
                <option value="en">영어</option>
              </select>
            </label>

            <label className="block text-sm font-semibold">
              {K.originalName}
              <input
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.originalSourceName}
                onChange={(event) =>
                  updateImportDraft(
                    "originalSourceName",
                    event.target.value,
                  )
                }
                placeholder={K.optional}
              />
            </label>

            <label className="block text-sm font-semibold">
              {K.interval}
              <input
                type="number"
                min={60}
                max={604800}
                className={`${INPUT_CLASS} mt-1.5`}
                value={
                  importDraft.requestIntervalSeconds
                }
                onChange={(event) =>
                  updateImportDraft(
                    "requestIntervalSeconds",
                    event.target.value,
                  )
                }
              />
            </label>

            <label className="block text-sm font-semibold">
              {K.timeout}
              <input
                type="number"
                min={1}
                max={120}
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.timeoutSeconds}
                onChange={(event) =>
                  updateImportDraft(
                    "timeoutSeconds",
                    event.target.value,
                  )
                }
              />
            </label>

            <label className="block text-sm font-semibold">
              {K.maxItems}
              <input
                type="number"
                min={1}
                max={500}
                className={`${INPUT_CLASS} mt-1.5`}
                value={importDraft.maxItems}
                onChange={(event) =>
                  updateImportDraft(
                    "maxItems",
                    event.target.value,
                  )
                }
              />
            </label>
          </div>

          {preview ? (
            <div className="mt-5 rounded-2xl border border-cyan/30 bg-cyan/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="font-bold">
                  {K.previewTitle}
                </h4>

                <span
                  className={
                    preview.wouldCreate
                      ? "text-sm font-bold text-green"
                      : "text-sm font-bold text-red"
                  }
                >
                  {preview.wouldCreate
                    ? K.canCreate
                    : K.blocked}
                </span>
              </div>

              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-muted">
                    {K.normalizedName}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {preview.normalizedSource.name}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.domain}
                  </dt>
                  <dd className="mt-1 break-all font-semibold">
                    {preview.normalizedSource.domain}
                  </dd>
                </div>

                <div className="sm:col-span-2">
                  <dt className="text-xs text-muted">
                    {K.feedUrl}
                  </dt>
                  <dd className="mt-1 break-all font-semibold">
                    {preview.normalizedSource.feedUrl}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.sameSource}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {preview.duplicate.duplicate
                      ? K.exists
                      : K.none}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.duplicateFields}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {preview.duplicate.matchedFields.length
                      ? preview.duplicate.matchedFields.join(
                          ", ",
                        )
                      : K.none}
                  </dd>
                </div>
              </dl>

              {preview.validationWarnings.length ? (
                <ul className="mt-4 space-y-1 text-sm text-secondary">
                  {preview.validationWarnings.map(
                    (warning) => (
                      <li key={warning}>
                        {"\u00b7"}{" "}
                        {warningLabel(warning)}
                      </li>
                    ),
                  )}
                </ul>
              ) : (
                <p className="mt-4 text-sm text-green">
                  {K.noWarnings}
                </p>
              )}

              <p className="mt-4 text-xs leading-5 text-muted">
                {K.previewOnly}
              </p>
            </div>
          ) : null}

          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => {
                resetImport();
                setShowImport(false);
              }}
              disabled={
                previewLoading ||
                confirmLoading
              }
              className="min-h-10 rounded-xl border border-border px-4 text-sm font-semibold disabled:opacity-50"
            >
              {K.cancel}
            </button>

            <button
              type="submit"
              disabled={
                previewLoading ||
                confirmLoading
              }
              className="min-h-10 rounded-xl bg-cyan px-4 text-sm font-bold text-background disabled:opacity-50"
            >
              {previewLoading
                ? K.previewing
                : K.preview}
            </button>

            {preview?.wouldCreate ? (
              <button
                type="button"
                onClick={() => {
                  void confirmImport();
                }}
                disabled={
                  previewLoading ||
                  confirmLoading
                }
                className="min-h-10 rounded-xl border border-green px-4 text-sm font-bold text-green disabled:opacity-50"
              >
                {confirmLoading
                  ? K.confirming
                  : K.confirm}
              </button>
            ) : null}
          </div>
        </form>
      ) : null}

      <div className="mt-5 space-y-4">
        {loading ? (
          <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted">
            {K.loading}
          </p>
        ) : null}

        {!loading && items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-card p-5">
            <p className="font-semibold">
              {K.empty}
            </p>
            <p className="mt-2 text-xs leading-5 text-muted">
              {K.emptyDescription}
            </p>
          </div>
        ) : null}

        {items.map((source) => {
          const editing =
            editingId === source.id;
          const saving =
            savingId === source.id;

          return (
            <article
              key={source.id}
              className="rounded-2xl border border-border bg-card p-4"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-bold">
                      {source.name}
                    </h3>

                    <span
                      className={
                        source.enabled
                          ? "rounded-full border border-green/40 bg-green/10 px-2.5 py-1 text-xs font-bold text-green"
                          : "rounded-full border border-red/40 bg-red/10 px-2.5 py-1 text-xs font-bold text-red"
                      }
                    >
                      {source.enabled
                        ? K.active
                        : K.stopped}
                    </span>

                    <span className="rounded-full border border-gold/40 bg-gold/10 px-2.5 py-1 text-xs font-bold text-gold">
                      {K.grade}{" "}
                      {source.sourceGrade}
                    </span>
                  </div>

                  <p className="mt-2 break-all text-xs text-muted">
                    {source.domain}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (editing) {
                        cancelEdit();
                      } else {
                        beginEdit(source);
                      }
                    }}
                    disabled={
                      savingId !== null
                    }
                    className="inline-flex min-h-9 items-center justify-center rounded-lg border border-border px-3 text-xs font-bold text-secondary hover:border-cyan/50 hover:text-cyan disabled:opacity-50"
                  >
                    {editing
                      ? K.cancelEdit
                      : K.edit}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      void toggleSource(source);
                    }}
                    disabled={
                      savingId !== null
                    }
                    className={
                      source.enabled
                        ? "inline-flex min-h-9 items-center justify-center rounded-lg border border-red/40 px-3 text-xs font-bold text-red hover:bg-red/10 disabled:opacity-50"
                        : "inline-flex min-h-9 items-center justify-center rounded-lg border border-green/40 px-3 text-xs font-bold text-green hover:bg-green/10 disabled:opacity-50"
                    }
                  >
                    {saving
                      ? K.processing
                      : source.enabled
                        ? K.stopSource
                        : K.restoreSource}
                  </button>
                </div>
              </div>

              <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted">
                    {K.official}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {source.official
                      ? K.officialSource
                      : K.unverified}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    수집 방식
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {providerTypeLabel(source.providerType)}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.language}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {languageLabel(source.language)}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.requestInterval}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {source.requestIntervalSeconds}
                    {K.seconds}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.timeout}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {source.timeoutSeconds}
                    {K.seconds}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.maxCollect}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {source.maxItems}
                    {K.count}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.activeSubscriptions}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {source.activeSubscriptionCount}
                    {K.count}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-muted">
                    {K.totalSubscriptions}
                  </dt>
                  <dd className="mt-1 font-semibold">
                    {source.totalSubscriptionCount}
                    {K.count}
                  </dd>
                </div>

                <div className="sm:col-span-2 lg:col-span-3">
                  <dt className="text-xs text-muted">
                    {K.feedUrl}
                  </dt>
                  <dd className="mt-1 break-all font-semibold">
                    {source.feedUrl ?? K.none}
                  </dd>
                </div>
              </dl>

              {source.enabled &&
              source.activeSubscriptionCount > 0 ? (
                <p className="mt-4 rounded-xl border border-gold/30 bg-gold/5 p-3 text-xs leading-5 text-secondary">
                  {K.activeSubscriptions}{" "}
                  {source.activeSubscriptionCount}
                  {K.count}. {K.protection}
                </p>
              ) : null}

              {editing && editDraft ? (
                <div className="mt-5 rounded-2xl border border-cyan/30 bg-cyan/5 p-4">
                  <h4 className="font-bold">
                    {K.editTitle}
                  </h4>

                  <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <label className="block text-sm font-semibold">
                      {K.grade}
                      <select
                        className={`${INPUT_CLASS} mt-1.5`}
                        value={
                          editDraft.sourceGrade
                        }
                        onChange={(event) =>
                          setEditDraft({
                            ...editDraft,
                            sourceGrade:
                              event.target
                                .value as SourceGrade,
                          })
                        }
                        disabled={saving}
                      >
                        {(
                          Object.entries(
                            gradeLabels,
                          ) as Array<
                            [SourceGrade, string]
                          >
                        ).map(
                          ([value, label]) => (
                            <option
                              key={value}
                              value={value}
                            >
                              {label}
                            </option>
                          ),
                        )}
                      </select>
                    </label>

                    <label className="block text-sm font-semibold">
                      {K.language}
                      <input
                        className={`${INPUT_CLASS} mt-1.5`}
                        value={
                          editDraft.language
                        }
                        onChange={(event) =>
                          setEditDraft({
                            ...editDraft,
                            language:
                              event.target.value,
                          })
                        }
                        disabled={saving}
                      />
                    </label>

                    <label className="block text-sm font-semibold">
                      {K.interval}
                      <input
                        type="number"
                        min={60}
                        max={604800}
                        className={`${INPUT_CLASS} mt-1.5`}
                        value={
                          editDraft
                            .requestIntervalSeconds
                        }
                        onChange={(event) =>
                          setEditDraft({
                            ...editDraft,
                            requestIntervalSeconds:
                              event.target.value,
                          })
                        }
                        disabled={saving}
                      />
                    </label>

                    <label className="block text-sm font-semibold">
                      {K.timeout}
                      <input
                        type="number"
                        min={1}
                        max={120}
                        className={`${INPUT_CLASS} mt-1.5`}
                        value={
                          editDraft.timeoutSeconds
                        }
                        onChange={(event) =>
                          setEditDraft({
                            ...editDraft,
                            timeoutSeconds:
                              event.target.value,
                          })
                        }
                        disabled={saving}
                      />
                    </label>

                    <label className="block text-sm font-semibold">
                      {K.maxItems}
                      <input
                        type="number"
                        min={1}
                        max={500}
                        className={`${INPUT_CLASS} mt-1.5`}
                        value={
                          editDraft.maxItems
                        }
                        onChange={(event) =>
                          setEditDraft({
                            ...editDraft,
                            maxItems:
                              event.target.value,
                          })
                        }
                        disabled={saving}
                      />
                    </label>
                  </div>

                  <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                    <button
                      type="button"
                      onClick={cancelEdit}
                      disabled={saving}
                      className="min-h-10 rounded-xl border border-border px-4 text-sm font-semibold disabled:opacity-50"
                    >
                      {K.cancel}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        void saveEdit(source);
                      }}
                      disabled={saving}
                      className="min-h-10 rounded-xl bg-cyan px-4 text-sm font-bold text-background disabled:opacity-50"
                    >
                      {saving
                        ? K.saving
                        : K.save}
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
