"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/common/ui";
import { ApiClientError } from "@/lib/api/client";
import { getRiskProfile, saveRiskProfile } from "@/lib/api/risk-profile";
import { decimalCompare, decimalSum } from "@/lib/decimal-math";
import { isPercentage, isPositiveDecimal } from "@/lib/portfolio-form";
import type {
  AveragingDownPolicy,
  InvestmentHorizon,
  PrimaryGoal,
  RiskProfile,
  RiskProfileInput,
  RiskProfileRecommendation,
  RiskStyle,
} from "@/types/api";

const inputClass =
  "min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-foreground";

interface WizardValues {
  riskStyle: RiskStyle;
  primaryGoal: PrimaryGoal;
  defaultInvestmentHorizon: InvestmentHorizon;
  maxSinglePositionPercent: string;
  portfolioLossReviewPercent: string;
  defaultLossReviewPercent: string;
  defaultProfitReviewPercent: string;
  minimumCashPercent: string;
  maxSingleAdditionalBuyPercent: string;
  averagingDownPolicy: AveragingDownPolicy;
  maxAveragingDownCount: string;
  requireOfficialEvidenceForAveragingDown: boolean;
  highVolatilityAssetLimitPercent: string;
  cryptoAssetLimitPercent: string;
  notes: string;
}

const empty: WizardValues = {
  riskStyle: "CUSTOM",
  primaryGoal: "BALANCED_GROWTH",
  defaultInvestmentHorizon: "LONG",
  maxSinglePositionPercent: "",
  portfolioLossReviewPercent: "",
  defaultLossReviewPercent: "",
  defaultProfitReviewPercent: "",
  minimumCashPercent: "",
  maxSingleAdditionalBuyPercent: "",
  averagingDownPolicy: "DISABLED",
  maxAveragingDownCount: "0",
  requireOfficialEvidenceForAveragingDown: true,
  highVolatilityAssetLimitPercent: "",
  cryptoAssetLimitPercent: "",
  notes: "",
};

const steps = [
  "투자 목적",
  "투자 기간",
  "감당 가능한 손실",
  "종목 집중 한도",
  "현금 비중",
  "추가매수 정책",
  "최종 확인",
];

const styleSuggestions: Record<
  Exclude<RiskStyle, "CUSTOM">,
  Partial<WizardValues>
> = {
  CONSERVATIVE: {
    maxSinglePositionPercent: "10",
    portfolioLossReviewPercent: "8",
    minimumCashPercent: "30",
    cryptoAssetLimitPercent: "5",
    averagingDownPolicy: "DISABLED",
  },
  BALANCED: {
    maxSinglePositionPercent: "20",
    portfolioLossReviewPercent: "15",
    minimumCashPercent: "15",
    cryptoAssetLimitPercent: "10",
    averagingDownPolicy: "CONDITIONAL",
    maxAveragingDownCount: "2",
  },
  AGGRESSIVE: {
    maxSinglePositionPercent: "30",
    portfolioLossReviewPercent: "25",
    minimumCashPercent: "5",
    cryptoAssetLimitPercent: "20",
    averagingDownPolicy: "CONDITIONAL",
    maxAveragingDownCount: "3",
  },
};

function fromProfile(profile: RiskProfile): WizardValues {
  return {
    riskStyle: profile.riskStyle ?? "CUSTOM",
    primaryGoal: profile.primaryGoal ?? "BALANCED_GROWTH",
    defaultInvestmentHorizon:
      profile.defaultInvestmentHorizon ?? "UNSET",
    maxSinglePositionPercent:
      profile.maxSinglePositionPercent ?? profile.maxPositionPercent ?? "",
    portfolioLossReviewPercent:
      profile.portfolioLossReviewPercent ??
      profile.maxPortfolioLossPercent ??
      "",
    defaultLossReviewPercent:
      profile.defaultLossReviewPercent ??
      profile.defaultStopLossPercent ??
      "",
    defaultProfitReviewPercent:
      profile.defaultProfitReviewPercent ??
      profile.defaultTakeProfitPercent ??
      "",
    minimumCashPercent:
      profile.minimumCashPercent ?? profile.cashReservePercent ?? "",
    maxSingleAdditionalBuyPercent:
      profile.maxSingleAdditionalBuyPercent ?? "",
    averagingDownPolicy:
      profile.averagingDownPolicy ??
      (profile.allowAveragingDown ? "ALLOWED" : "DISABLED"),
    maxAveragingDownCount: String(profile.maxAveragingDownCount ?? 0),
    requireOfficialEvidenceForAveragingDown:
      profile.requireOfficialEvidenceForAveragingDown ?? true,
    highVolatilityAssetLimitPercent:
      profile.highVolatilityAssetLimitPercent ?? "",
    cryptoAssetLimitPercent: profile.cryptoAssetLimitPercent ?? "",
    notes: profile.notes ?? "",
  };
}

function fromRecommendation(
  recommendation: RiskProfileRecommendation,
): WizardValues {
  return {
    ...empty,
    riskStyle: recommendation.suggestedRiskStyle,
    maxSinglePositionPercent:
      recommendation.maxSinglePositionPercent,
    portfolioLossReviewPercent:
      recommendation.portfolioLossReviewPercent,
    defaultLossReviewPercent:
      recommendation.defaultLossReviewPercent,
    defaultProfitReviewPercent:
      recommendation.defaultProfitReviewPercent,
    minimumCashPercent: recommendation.minimumCashPercent ?? "",
    maxSingleAdditionalBuyPercent:
      recommendation.maxSingleAdditionalBuyPercent,
    averagingDownPolicy: recommendation.averagingDownPolicy,
    maxAveragingDownCount: String(
      recommendation.maxAveragingDownCount,
    ),
    requireOfficialEvidenceForAveragingDown:
      recommendation.requireOfficialEvidenceForAveragingDown,
    highVolatilityAssetLimitPercent:
      recommendation.highVolatilityAssetLimitPercent,
    cryptoAssetLimitPercent:
      recommendation.cryptoAssetLimitPercent,
  };
}

function display(value: string | null): string {
  return value === null || value === "" ? "미설정" : `${value}%`;
}

export function RiskProfileWizard({
  suggestion,
}: {
  suggestion?: RiskProfileRecommendation | null;
}) {
  const [configured, setConfigured] = useState(false);
  const [profile, setProfile] = useState<RiskProfile | null>(null);
  const [editing, setEditing] = useState(false);
  const [step, setStep] = useState(0);
  const [values, setValues] = useState<WizardValues>(empty);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getRiskProfile(controller.signal)
      .then((response) => {
        setConfigured(response.configured);
        setProfile(response.profile);
        if (response.profile) setValues(fromProfile(response.profile));
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") return;
        setMessage(
          reason instanceof ApiClientError
            ? reason.message
            : "위험 설정을 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  function setValue<K extends keyof WizardValues>(
    name: K,
    value: WizardValues[K],
  ) {
    setValues((current) => ({ ...current, [name]: value }));
    setMessage("");
  }

  function applyStyle(style: Exclude<RiskStyle, "CUSTOM">) {
    setValues((current) => ({
      ...current,
      ...styleSuggestions[style],
      riskStyle: style,
    }));
    setMessage(
      "제안값을 미리 적용했습니다. 최종 확인 전에는 저장되지 않습니다.",
    );
  }

  function loadSuggestion() {
    if (!suggestion) return;
    setValues(fromRecommendation(suggestion));
    setEditing(true);
    setStep(0);
    setMessage(
      "자동 제안값을 사용자 지정 초깃값으로 불러왔습니다. 최종 확인 전에는 저장되지 않습니다.",
    );
  }

  function validateCurrent(): string {
    const requiredPositive: Array<keyof WizardValues> = [
      "maxSinglePositionPercent",
      "portfolioLossReviewPercent",
      "defaultLossReviewPercent",
      "defaultProfitReviewPercent",
    ];
    for (const name of requiredPositive) {
      const value = values[name];
      if (
        typeof value === "string" &&
        value &&
        (!isPositiveDecimal(value) || !isPercentage(value))
      ) {
        return "손실·수익·집중 기준은 0 초과 100 이하로 입력해 주세요.";
      }
    }
    for (const name of [
      "minimumCashPercent",
      "maxSingleAdditionalBuyPercent",
      "highVolatilityAssetLimitPercent",
      "cryptoAssetLimitPercent",
    ] as const) {
      if (values[name] && !isPercentage(values[name])) {
        return "비중 값은 0에서 100 사이로 입력해 주세요.";
      }
    }
    if (
      values.averagingDownPolicy === "CONDITIONAL" &&
      Number(values.maxAveragingDownCount) < 1
    ) {
      return "조건부 추가매수는 최대 횟수를 1회 이상 입력해 주세요.";
    }
    return "";
  }

  function next() {
    const error = validateCurrent();
    if (error) {
      setMessage(error);
      return;
    }
    if (
      step === 4 &&
      values.maxSinglePositionPercent &&
      values.minimumCashPercent
    ) {
      try {
        if (
          decimalCompare(
            decimalSum([
              values.maxSinglePositionPercent,
              values.minimumCashPercent,
            ]),
            "100",
          ) > 0
        ) {
          setMessage(
            "종목 최대 비중과 최소 현금 비중의 합이 100%를 넘습니다. 저장은 가능하지만 계획을 다시 확인하세요.",
          );
        }
      } catch {
        setMessage("비중 값을 확인해 주세요.");
        return;
      }
    }
    setStep((current) => Math.min(6, current + 1));
  }

  async function save() {
    const error = validateCurrent();
    if (error) {
      setMessage(error);
      return;
    }
    setSaving(true);
    setMessage("");
    const optional = (value: string) => value.trim() || null;
    const input: RiskProfileInput = {
      riskStyle: values.riskStyle,
      primaryGoal: values.primaryGoal,
      defaultInvestmentHorizon: values.defaultInvestmentHorizon,
      maxSinglePositionPercent: optional(values.maxSinglePositionPercent),
      portfolioLossReviewPercent: optional(
        values.portfolioLossReviewPercent,
      ),
      defaultLossReviewPercent: optional(values.defaultLossReviewPercent),
      defaultProfitReviewPercent: optional(
        values.defaultProfitReviewPercent,
      ),
      minimumCashPercent: optional(values.minimumCashPercent),
      maxSingleAdditionalBuyPercent: optional(
        values.maxSingleAdditionalBuyPercent,
      ),
      averagingDownPolicy: values.averagingDownPolicy,
      maxAveragingDownCount: Number(values.maxAveragingDownCount),
      requireOfficialEvidenceForAveragingDown:
        values.requireOfficialEvidenceForAveragingDown,
      highVolatilityAssetLimitPercent: optional(
        values.highVolatilityAssetLimitPercent,
      ),
      cryptoAssetLimitPercent: optional(values.cryptoAssetLimitPercent),
      notes: values.notes.trim() || null,
      acknowledgedAt: new Date().toISOString(),
      maxPositionPercent: optional(values.maxSinglePositionPercent),
      maxPortfolioLossPercent: optional(
        values.portfolioLossReviewPercent,
      ),
      defaultStopLossPercent: optional(values.defaultLossReviewPercent),
      defaultTakeProfitPercent: optional(
        values.defaultProfitReviewPercent,
      ),
      cashReservePercent: optional(values.minimumCashPercent),
      allowAveragingDown: values.averagingDownPolicy !== "DISABLED",
      recommendationMode: "UNSET",
      maxSingleTradeAmount: profile?.maxSingleTradeAmount ?? null,
    };
    try {
      const response = await saveRiskProfile(input);
      setProfile(response.profile);
      setConfigured(true);
      setEditing(false);
      setStep(0);
      setMessage("투자 위험 검토 기준을 저장했습니다.");
    } catch (reason) {
      setMessage(
        reason instanceof ApiClientError
          ? reason.message
          : "위험 설정을 저장하지 못했습니다.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Card><p className="py-12 text-center">위험 설정 확인 중…</p></Card>;

  if (configured && profile && !editing) {
    return (
      <Card title="투자 위험 설정 요약">
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["투자 성향", profile.riskStyle ?? "사용자 지정"],
            ["종목당 최대 비중", display(profile.maxSinglePositionPercent)],
            ["전체 손실 검토", display(profile.portfolioLossReviewPercent)],
            ["기본 손실 검토", display(profile.defaultLossReviewPercent)],
            ["기본 수익 검토", display(profile.defaultProfitReviewPercent)],
            ["최소 현금 비중", display(profile.minimumCashPercent)],
            ["추가매수 정책", profile.averagingDownPolicy ?? "DISABLED"],
            ["암호자산 한도", display(profile.cryptoAssetLimitPercent)],
            [
              "마지막 확인",
              profile.acknowledgedAt
                ? new Date(profile.acknowledgedAt).toLocaleString("ko-KR")
                : "미확인",
            ],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-border bg-surface p-3">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="mt-1 font-bold">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm">
          이 값은 경고와 재검토 기준이며 자동 주문에는 사용되지 않습니다.
        </p>
        {message ? <p className="mt-3 text-sm text-green">{message}</p> : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {suggestion ? (
            <button
              type="button"
              onClick={loadSuggestion}
              className="min-h-11 rounded-xl border border-cyan/50 px-4 font-semibold text-cyan"
            >
              자동 제안값으로 수정
            </button>
          ) : null}
          <button type="button" onClick={() => setEditing(true)} className="min-h-11 rounded-xl bg-cyan px-4 font-bold text-background">설정 수정</button>
          <button type="button" onClick={() => { setEditing(true); setStep(0); }} className="min-h-11 rounded-xl border border-border px-4 font-semibold">설정 다시 검토</button>
        </div>
      </Card>
    );
  }

  if (!editing) {
    return (
      <Card title="투자 위험 설정">
        <div className="rounded-xl border border-dashed border-border p-6 text-center">
          <p className="font-bold">아직 저장된 위험 기준이 없습니다.</p>
          <p className="mt-2 text-sm text-secondary">특정 성향은 자동 선택되지 않으며 최종 확인 전에는 저장하지 않습니다.</p>
          <div className="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
            {suggestion ? (
              <button
                type="button"
                onClick={loadSuggestion}
                className="min-h-11 rounded-xl border border-cyan/50 px-5 font-bold text-cyan"
              >
                자동 제안값을 초깃값으로 사용
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => {
                setValues(empty);
                setEditing(true);
              }}
              className="min-h-11 rounded-xl bg-cyan px-5 font-bold text-background"
            >
              직접 처음부터 설정
            </button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card title="투자 위험 설정 마법사">
      <div className="mb-5 overflow-x-auto">
        <ol className="flex min-w-max gap-2">
          {steps.map((label, index) => (
            <li key={label} className={`rounded-full px-3 py-2 text-xs font-bold ${index === step ? "bg-cyan text-background" : "bg-surface text-muted"}`}>
              {index + 1}. {label}
            </li>
          ))}
        </ol>
      </div>

      <div className="min-h-72">
        {step === 0 ? (
          <section>
            <h3 className="font-bold">투자 목적과 성향</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {(["CONSERVATIVE", "BALANCED", "AGGRESSIVE"] as const).map((style) => (
                <button key={style} type="button" onClick={() => applyStyle(style)} className="min-h-14 rounded-xl border border-border px-3 font-bold">
                  {style === "CONSERVATIVE" ? "보수 제안" : style === "BALANCED" ? "균형 제안" : "적극 제안"}
                </button>
              ))}
            </div>
            <label className="mt-5 block text-sm font-semibold">주요 목적
              <select className={`${inputClass} mt-2`} value={values.primaryGoal} onChange={(event) => setValue("primaryGoal", event.target.value as PrimaryGoal)}>
                <option value="CAPITAL_PRESERVATION">자산 보전</option>
                <option value="INCOME">현금흐름</option>
                <option value="BALANCED_GROWTH">균형 성장</option>
                <option value="GROWTH">장기 성장</option>
                <option value="CUSTOM">사용자 지정</option>
              </select>
            </label>
          </section>
        ) : null}
        {step === 1 ? (
          <section><h3 className="font-bold">기본 투자 기간</h3>
            <select className={`${inputClass} mt-4`} value={values.defaultInvestmentHorizon} onChange={(event) => setValue("defaultInvestmentHorizon", event.target.value as InvestmentHorizon)}>
              <option value="UNSET">미정</option><option value="SHORT">단기</option><option value="MEDIUM">중기</option><option value="LONG">장기</option>
            </select>
          </section>
        ) : null}
        {step === 2 ? (
          <section className="grid gap-4 sm:grid-cols-3"><h3 className="sm:col-span-3 font-bold">감당 가능한 손실과 수익 검토 기준</h3>
            {[
              ["portfolioLossReviewPercent", "전체 손실 검토 기준", "전체 자산 손실이 이 비율에 도달하면 투자 계획을 다시 확인합니다."],
              ["defaultLossReviewPercent", "기본 손실 검토율", "자동 손절이 아니라 종목을 다시 검토할 기준입니다."],
              ["defaultProfitReviewPercent", "기본 수익 검토율", "자동 매도가 아니라 수익 실현 여부를 다시 확인할 기준입니다."],
            ].map(([name, label, hint]) => (
              <label key={name} className="text-sm font-semibold">{label}<input className={`${inputClass} mt-2`} inputMode="decimal" value={values[name as keyof WizardValues] as string} onChange={(event) => setValue(name as keyof WizardValues, event.target.value as never)} /><span className="mt-1 block text-xs font-normal text-muted">{hint}</span></label>
            ))}
          </section>
        ) : null}
        {step === 3 ? (
          <section className="grid gap-4 sm:grid-cols-3"><h3 className="sm:col-span-3 font-bold">종목 집중 한도</h3>
            {[
              ["maxSinglePositionPercent", "종목당 최대 비중", "전체 투자금 중 한 종목에 허용할 최대 비율입니다."],
              ["highVolatilityAssetLimitPercent", "고변동 자산 한도", "변동성이 높은 자산의 검토 한도입니다."],
              ["cryptoAssetLimitPercent", "암호자산 한도", "암호자산 전체의 검토 한도입니다."],
            ].map(([name, label, hint]) => (
              <label key={name} className="text-sm font-semibold">{label}<input className={`${inputClass} mt-2`} inputMode="decimal" value={values[name as keyof WizardValues] as string} onChange={(event) => setValue(name as keyof WizardValues, event.target.value as never)} /><span className="mt-1 block text-xs font-normal text-muted">{hint}</span></label>
            ))}
          </section>
        ) : null}
        {step === 4 ? (
          <section><h3 className="font-bold">최소 현금 비중</h3>
            <label className="mt-4 block text-sm font-semibold">최소 현금 비중 (%)<input className={`${inputClass} mt-2`} inputMode="decimal" value={values.minimumCashPercent} onChange={(event) => setValue("minimumCashPercent", event.target.value)} /><span className="mt-1 block text-xs font-normal text-muted">추가 기회와 위험 대응을 위해 남길 현금 비율입니다.</span></label>
          </section>
        ) : null}
        {step === 5 ? (
          <section className="grid gap-4 sm:grid-cols-2"><h3 className="sm:col-span-2 font-bold">추가매수 정책</h3>
            <label className="text-sm font-semibold">정책<select className={`${inputClass} mt-2`} value={values.averagingDownPolicy} onChange={(event) => setValue("averagingDownPolicy", event.target.value as AveragingDownPolicy)}><option value="DISABLED">사용 안 함</option><option value="CONDITIONAL">조건부</option><option value="ALLOWED">허용</option></select></label>
            <label className="text-sm font-semibold">최대 횟수<input className={`${inputClass} mt-2`} type="number" min={0} value={values.maxAveragingDownCount} onChange={(event) => setValue("maxAveragingDownCount", event.target.value)} /></label>
            <label className="text-sm font-semibold">1회 최대 추가매수 비중 (%)<input className={`${inputClass} mt-2`} inputMode="decimal" value={values.maxSingleAdditionalBuyPercent} onChange={(event) => setValue("maxSingleAdditionalBuyPercent", event.target.value)} /></label>
            <label className="flex min-h-11 items-center gap-3 rounded-xl border border-border p-3 text-sm font-semibold"><input type="checkbox" checked={values.requireOfficialEvidenceForAveragingDown} onChange={(event) => setValue("requireOfficialEvidenceForAveragingDown", event.target.checked)} />공식 근거 확인 필수</label>
            <p className="sm:col-span-2 text-sm text-secondary">가격 하락만으로 자동 매수하지 않으며 사용자 확인 없이 주문하지 않습니다.</p>
          </section>
        ) : null}
        {step === 6 ? (
          <section><h3 className="font-bold">최종 확인</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-2"><p>성향: <strong>{values.riskStyle}</strong></p><p>종목 한도: <strong>{display(values.maxSinglePositionPercent || null)}</strong></p><p>전체 손실 검토: <strong>{display(values.portfolioLossReviewPercent || null)}</strong></p><p>최소 현금: <strong>{display(values.minimumCashPercent || null)}</strong></p><p>추가매수: <strong>{values.averagingDownPolicy}</strong></p><p>암호자산 한도: <strong>{display(values.cryptoAssetLimitPercent || null)}</strong></p></div>
            <label className="mt-4 block text-sm font-semibold">메모<textarea className={`${inputClass} mt-2 min-h-24 py-3`} value={values.notes} onChange={(event) => setValue("notes", event.target.value)} /></label>
            <p className="mt-4 rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm">위험 설정은 경고·검토 기준입니다. 추천 엔진은 비활성이며 매수·매도·목표가·자동 주문을 생성하지 않습니다.</p>
          </section>
        ) : null}
      </div>

      {message ? <p className="mt-4 rounded-xl border border-border p-3 text-sm" role="status">{message}</p> : null}
      <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <button type="button" onClick={() => step === 0 ? setEditing(false) : setStep((current) => current - 1)} className="min-h-11 rounded-xl border border-border px-4 font-semibold">{step === 0 ? "취소" : "이전 단계"}</button>
        {step < 6 ? (
          <button type="button" onClick={next} className="min-h-11 rounded-xl bg-cyan px-5 font-bold text-background">다음 단계</button>
        ) : (
          <button type="button" onClick={save} disabled={saving} className="min-h-11 rounded-xl bg-cyan px-5 font-bold text-background disabled:opacity-50">{saving ? "저장 중…" : "최종 확인 및 저장"}</button>
        )}
      </div>
    </Card>
  );
}
