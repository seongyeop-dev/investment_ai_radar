"use client";

import { type FormEvent, useEffect, useState } from "react";
import { Card } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import {
  getMarketBriefingPreview,
  getNextMarketBriefings,
  getNotificationPreference,
  saveNotificationPreference,
} from "@/lib/api/operations";
import { maskEmail } from "@/lib/operations";
import type {
  MarketBriefingPreview,
  MarketBriefingType,
  NextMarketBriefing,
  NotificationPreference,
  NotificationPreferenceInput,
} from "@/types/api";

const inputClass =
  "min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-foreground";

const empty: NotificationPreferenceInput = {
  enabled: false,
  hourlyChangeBriefingEnabled: false,
  dailyDigestEnabled: false,
  krxPreOpenEnabled: false,
  krxPostCloseEnabled: false,
  nasdaqPreOpenEnabled: false,
  nasdaqPostCloseEnabled: false,
  immediateMaterialChangeEnabled: false,
  correctionNoticeEnabled: true,
  providerFailureNoticeEnabled: false,
  timezone: "Asia/Seoul",
  dailyDigestHour: 8,
  minimumPriority: 50,
  includeWatchlist: true,
  includeReentryWatch: false,
  includeSold: false,
  sendNoMaterialChangeBriefing: false,
  krxPreOpenOffsetMinutes: 40,
  krxPostCloseOffsetMinutes: 20,
  nasdaqPreOpenOffsetMinutes: 60,
  nasdaqPostCloseOffsetMinutes: 20,
  recipientEmail: "",
};

const marketOptions: Array<{
  type: MarketBriefingType;
  label: string;
  enabled: keyof NotificationPreferenceInput;
  offset: keyof NotificationPreferenceInput;
  timing: string;
}> = [
  {
    type: "KRX_PRE_OPEN",
    label: "국내장 개장 전",
    enabled: "krxPreOpenEnabled",
    offset: "krxPreOpenOffsetMinutes",
    timing: "개장 전",
  },
  {
    type: "KRX_POST_CLOSE",
    label: "국내장 마감 후",
    enabled: "krxPostCloseEnabled",
    offset: "krxPostCloseOffsetMinutes",
    timing: "마감 후",
  },
  {
    type: "NASDAQ_PRE_OPEN",
    label: "나스닥 개장 전",
    enabled: "nasdaqPreOpenEnabled",
    offset: "nasdaqPreOpenOffsetMinutes",
    timing: "개장 전",
  },
  {
    type: "NASDAQ_POST_CLOSE",
    label: "나스닥 마감 후",
    enabled: "nasdaqPostCloseEnabled",
    offset: "nasdaqPostCloseOffsetMinutes",
    timing: "마감 후",
  },
];

function scheduleText(schedule?: NextMarketBriefing): string {
  if (!schedule || schedule.scheduleStatus === "NOT_CONFIGURED") {
    return "시장 일정 미설정";
  }
  if (schedule.scheduleStatus === "CLOSED") return "휴장 · 발송 안 함";
  if (!schedule.scheduledAtKst) return "다음 일정 확인 불가";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(schedule.scheduledAtKst));
}

export function NotificationSettings() {
  const [values, setValues] = useState(empty);
  const [current, setCurrent] = useState<NotificationPreference | null>(null);
  const [schedules, setSchedules] = useState<NextMarketBriefing[]>([]);
  const [preview, setPreview] = useState<MarketBriefingPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getNotificationPreference(controller.signal),
      getNextMarketBriefings(controller.signal),
    ])
      .then(([value, next]) => {
        setCurrent(value);
        setSchedules(next.items);
        setValues({
          enabled: value.enabled,
          hourlyChangeBriefingEnabled: value.hourlyChangeBriefingEnabled,
          dailyDigestEnabled: value.dailyDigestEnabled,
          krxPreOpenEnabled: value.krxPreOpenEnabled,
          krxPostCloseEnabled: value.krxPostCloseEnabled,
          nasdaqPreOpenEnabled: value.nasdaqPreOpenEnabled,
          nasdaqPostCloseEnabled: value.nasdaqPostCloseEnabled,
          immediateMaterialChangeEnabled:
            value.immediateMaterialChangeEnabled,
          correctionNoticeEnabled: value.correctionNoticeEnabled,
          providerFailureNoticeEnabled: value.providerFailureNoticeEnabled,
          timezone: value.timezone,
          dailyDigestHour: value.dailyDigestHour,
          minimumPriority: value.minimumPriority,
          includeWatchlist: value.includeWatchlist,
          includeReentryWatch: value.includeReentryWatch,
          includeSold: value.includeSold,
          sendNoMaterialChangeBriefing:
            value.sendNoMaterialChangeBriefing,
          krxPreOpenOffsetMinutes: value.krxPreOpenOffsetMinutes,
          krxPostCloseOffsetMinutes: value.krxPostCloseOffsetMinutes,
          nasdaqPreOpenOffsetMinutes: value.nasdaqPreOpenOffsetMinutes,
          nasdaqPostCloseOffsetMinutes: value.nasdaqPostCloseOffsetMinutes,
          recipientEmail: "",
        });
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setMessage(
          reason instanceof ApiClientError
            ? reason.message
            : "브리핑 설정을 불러오지 못했습니다.",
        );
      });
    return () => controller.abort();
  }, []);

  function toggle(name: keyof NotificationPreferenceInput) {
    setValues((value) => ({ ...value, [name]: !value[name] }));
  }

  async function showPreview(type: MarketBriefingType) {
    if (previewLoading) return;
    setPreviewLoading(true);
    setMessage("");
    try {
      setPreview(await getMarketBriefingPreview(type));
    } catch (reason) {
      setMessage(
        reason instanceof ApiClientError
          ? reason.message
          : "Preview를 불러오지 못했습니다.",
      );
    } finally {
      setPreviewLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const saved = await saveNotificationPreference({
        ...values,
        recipientEmail: values.recipientEmail?.trim() || undefined,
      });
      setCurrent(saved);
      setValues((value) => ({ ...value, recipientEmail: "" }));
      setMessage("브리핑 설정을 저장했습니다.");
    } catch (reason) {
      setMessage(
        reason instanceof ApiClientError
          ? reason.message
          : "설정을 저장하지 못했습니다.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="시장 브리핑 및 이메일">
      <form className="space-y-6" onSubmit={submit}>
        {current?.emailProviderStatus === "NOT_CONFIGURED" ? (
          <p className="rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm leading-6">
            브리핑 설정은 저장할 수 있지만 실제 이메일은 이메일 제공자 연결 후
            발송됩니다.
          </p>
        ) : null}

        <section>
          <h3 className="font-bold">시장 브리핑</h3>
          <p className="mt-1 text-sm text-secondary">
            절대 시각 대신 실제 시장 개장·마감 기준 offset을 저장합니다.
            휴장에는 만들지 않고 조기 폐장은 실제 폐장 시각을 사용합니다.
          </p>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {marketOptions.map((option) => {
              const schedule = schedules.find(
                (item) => item.briefingType === option.type,
              );
              return (
                <div
                  key={option.type}
                  className="rounded-2xl border border-border bg-surface p-4"
                >
                  <label className="flex min-h-11 items-center gap-3 font-bold">
                    <input
                      type="checkbox"
                      checked={Boolean(values[option.enabled])}
                      onChange={() => toggle(option.enabled)}
                    />
                    {option.label}
                  </label>
                  <label className="mt-3 block text-sm font-semibold">
                    {option.timing} 알림 시점(분)
                    <input
                      className={`${inputClass} mt-2`}
                      type="number"
                      min={0}
                      max={240}
                      value={String(values[option.offset])}
                      onChange={(event) =>
                        setValues((value) => ({
                          ...value,
                          [option.offset]: Number(event.target.value),
                        }))
                      }
                    />
                  </label>
                  <p className="mt-3 text-xs text-muted">
                    다음 예정: {scheduleText(schedule)}
                    {schedule?.earlyClose ? " · 조기 폐장 반영" : ""}
                  </p>
                  <button
                    type="button"
                    onClick={() => showPreview(option.type)}
                    disabled={previewLoading}
                    className="mt-3 min-h-10 rounded-lg border border-cyan/40 px-3 text-sm font-bold text-cyan disabled:opacity-50"
                  >미리보기</button>
                </div>
              );
            })}
          </div>
        </section>

        <section className="grid gap-3 border-t border-border pt-5 sm:grid-cols-2">
          <h3 className="sm:col-span-2 font-bold">즉시 알림·종합본</h3>
          {[
            ["dailyDigestEnabled", "하루 최종 종합본"],
            ["immediateMaterialChangeEnabled", "새로운 중요 변경"],
            ["correctionNoticeEnabled", "정정·공식 부인"],
            ["providerFailureNoticeEnabled", "데이터 제공자 장애"],
            ["sendNoMaterialChangeBriefing", "중요 변경 없음 브리핑"],
          ].map(([name, label]) => (
            <label
              key={name}
              className="flex min-h-11 items-center gap-3 rounded-xl border border-border p-3 text-sm font-semibold"
            >
              <input
                type="checkbox"
                checked={Boolean(
                  values[name as keyof NotificationPreferenceInput],
                )}
                onChange={() =>
                  toggle(name as keyof NotificationPreferenceInput)
                }
              />
              {label}
            </label>
          ))}
        </section>

        <section className="grid gap-3 border-t border-border pt-5 sm:grid-cols-2">
          <h3 className="sm:col-span-2 font-bold">포함 대상</h3>
          <p className="rounded-xl border border-green/30 bg-green/10 p-3 text-sm font-semibold">
            보유 종목 · 항상 포함
          </p>
          {[
            ["includeWatchlist", "관심 종목 포함"],
            ["includeReentryWatch", "재진입 관심 포함"],
            ["includeSold", "매도 완료 종목 포함"],
          ].map(([name, label]) => (
            <label
              key={name}
              className="flex min-h-11 items-center gap-3 rounded-xl border border-border p-3 text-sm font-semibold"
            >
              <input
                type="checkbox"
                checked={Boolean(
                  values[name as keyof NotificationPreferenceInput],
                )}
                onChange={() =>
                  toggle(name as keyof NotificationPreferenceInput)
                }
              />
              {label}
            </label>
          ))}
        </section>

        <section className="grid gap-4 border-t border-border pt-5 sm:grid-cols-3">
          <label className="text-sm font-semibold">
            이메일 알림 사용
            <input
              className="ml-3"
              type="checkbox"
              checked={values.enabled}
              onChange={() => toggle("enabled")}
            />
          </label>
          <label className="text-sm font-semibold">
            최소 중요도
            <input
              className={`${inputClass} mt-2`}
              type="number"
              min={0}
              max={100}
              value={values.minimumPriority}
              onChange={(event) =>
                setValues((value) => ({
                  ...value,
                  minimumPriority: Number(event.target.value),
                }))
              }
            />
          </label>
          <label className="text-sm font-semibold">
            시간대
            <input
              className={`${inputClass} mt-2`}
              value={values.timezone}
              readOnly
            />
          </label>
          <label className="text-sm font-semibold sm:col-span-3">
            수신 이메일
            <input
              className={`${inputClass} mt-2`}
              type="email"
              autoComplete="email"
              value={values.recipientEmail ?? ""}
              placeholder={current?.recipientEmailMasked ?? "name@example.com"}
              onChange={(event) =>
                setValues((value) => ({
                  ...value,
                  recipientEmail: event.target.value,
                }))
              }
            />
            {values.recipientEmail ? (
              <span className="mt-1 block text-xs text-muted">
                저장 시 표시: {maskEmail(values.recipientEmail)}
              </span>
            ) : null}
          </label>
        </section>

        {preview ? (
          <section className="rounded-2xl border border-cyan/40 bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-bold">{preview.emailSubject}</h3>
                <p className="mt-1 text-xs text-muted">
                  {preview.market} · 기준일 {preview.sessionDate} · 발송 기록 생성 안 함
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPreview(null)}
                aria-label="Preview 닫기"
                className="text-xl"
              >
                ×
              </button>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div><dt className="text-muted">관련 종목</dt><dd className="font-bold">{preview.relatedInstrumentCount}</dd></div>
              <div><dt className="text-muted">공식 공시</dt><dd className="font-bold">{preview.officialDisclosureCount}</dd></div>
              <div><dt className="text-muted">뉴스 참조</dt><dd className="font-bold">{preview.newsReferenceCount}</dd></div>
              <div><dt className="text-muted">중요 변경</dt><dd className="font-bold">{preview.materialChangeCount}</dd></div>
            </dl>
            <p className={`mt-4 rounded-xl p-3 text-sm ${preview.dataMissing ? "bg-yellow/10 text-yellow" : "bg-green/10 text-green"}`}>
              {preview.dataStatusMessage}
            </p>
            <div className="mt-4 space-y-3 text-sm">
              {preview.bodySections.map((section) => (
                <div key={section.title}>
                  <h4 className="font-bold">{section.title}</h4>
                  <p className="mt-1 text-secondary">{section.content}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <p className="rounded-xl border border-border bg-surface p-4 text-sm leading-6 text-secondary">
          SMTP 비밀번호와 API 키는 서버 환경변수에서만 설정합니다. 실제 기사
          전문·추천·자동 주문은 만들지 않습니다.
        </p>
        {message ? (
          <p role="status" className="text-sm font-semibold text-cyan">
            {message}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={saving}
          className="min-h-11 rounded-xl bg-cyan px-5 font-bold text-background disabled:opacity-60"
        >
          {saving ? "저장 중…" : "브리핑 설정 저장"}
        </button>
      </form>
    </Card>
  );
}
