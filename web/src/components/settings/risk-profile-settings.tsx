"use client";

import { useEffect, useMemo, useState } from "react";
import { Dialog } from "@/components/common/dialog";
import { Card } from "@/components/common/ui";
import { RiskProfileWizard } from "@/components/settings/risk-profile-wizard";
import { ApiClientError } from "@/lib/api/client";
import {
  applyRiskRecommendation,
  getRiskProfile,
  getRiskRecommendation,
  getRiskRecommendationQuestions,
  refreshRiskRecommendation,
} from "@/lib/api/risk-profile";
import type {
  RiskProfile,
  RiskProfileRecommendation,
  RiskRecommendationAnswers,
  RiskRecommendationQuestions,
} from "@/types/api";

type Tab = "AUTO" | "CUSTOM";

const missingLabels: Record<string, string> = {
  FUNDS_NEEDED_WITHIN_ONE_YEAR: "1년 안에 사용할 투자금",
  ACCEPTABLE_TOTAL_LOSS: "감당 가능한 전체 손실 범위",
  EMERGENCY_FUND: "별도 비상자금 보유 여부",
  AVERAGING_DOWN_POLICY: "추가매수 정책",
  MARKET_PRICE_PROVIDER: "현재가 데이터 제공자",
  MARKET_VOLATILITY_PROVIDER: "시장 변동성 데이터 제공자",
  FX_RATES_FOR_CROSS_CURRENCY_WEIGHT: "통화 간 환율",
  CURRENT_CASH_BALANCE: "현재 현금 잔액",
  POSITIVE_POSITION_COST_BASIS: "보유 종목의 매수 원가",
};

const confidenceLabels = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
} as const;

const riskStyleLabels = {
  CONSERVATIVE: "보수형",
  BALANCED: "균형형",
  AGGRESSIVE: "적극형",
} as const;

const recommendationFields: Array<{
  key: keyof RiskProfileRecommendation;
  profileKey: keyof RiskProfile;
  label: string;
}> = [
  {
    key: "suggestedRiskStyle",
    profileKey: "riskStyle",
    label: "위험 성향",
  },
  {
    key: "maxSinglePositionPercent",
    profileKey: "maxSinglePositionPercent",
    label: "종목당 최대 비중",
  },
  {
    key: "portfolioLossReviewPercent",
    profileKey: "portfolioLossReviewPercent",
    label: "전체 손실 검토선",
  },
  {
    key: "defaultLossReviewPercent",
    profileKey: "defaultLossReviewPercent",
    label: "기본 손실 검토선",
  },
  {
    key: "defaultProfitReviewPercent",
    profileKey: "defaultProfitReviewPercent",
    label: "기본 수익 검토선",
  },
  {
    key: "minimumCashPercent",
    profileKey: "minimumCashPercent",
    label: "최소 현금 비중",
  },
  {
    key: "maxSingleAdditionalBuyPercent",
    profileKey: "maxSingleAdditionalBuyPercent",
    label: "1회 최대 추가매수 비중",
  },
  {
    key: "averagingDownPolicy",
    profileKey: "averagingDownPolicy",
    label: "추가매수 정책",
  },
  {
    key: "maxAveragingDownCount",
    profileKey: "maxAveragingDownCount",
    label: "최대 추가매수 횟수",
  },
  {
    key: "requireOfficialEvidenceForAveragingDown",
    profileKey: "requireOfficialEvidenceForAveragingDown",
    label: "추가매수 공식 근거",
  },
  {
    key: "highVolatilityAssetLimitPercent",
    profileKey: "highVolatilityAssetLimitPercent",
    label: "고변동 자산 한도",
  },
  {
    key: "cryptoAssetLimitPercent",
    profileKey: "cryptoAssetLimitPercent",
    label: "암호자산 한도",
  },
];

const settingValueLabels: Record<string, string> = {
  CONSERVATIVE: "보수형",
  BALANCED: "균형형",
  AGGRESSIVE: "적극형",
  CUSTOM: "사용자 지정",
  DISABLED: "사용 안 함",
  CONDITIONAL: "조건부",
  ALLOWED: "허용",
};

function valueText(value: unknown, percent = false): string {
  if (value === null || value === undefined || value === "") return "미확정";

  if (typeof value === "boolean") {
    return value ? "공식 근거 필요" : "공식 근거 불필요";
  }

  const raw = String(value);
  return `${settingValueLabels[raw] ?? raw}${percent ? "%" : ""}`;
}

export function RiskProfileSettings() {
  const [tab, setTab] = useState<Tab>("AUTO");
  const [recommendation, setRecommendation] =
    useState<RiskProfileRecommendation | null>(null);
  const [questions, setQuestions] =
    useState<RiskRecommendationQuestions | null>(null);
  const [profile, setProfile] = useState<RiskProfile | null>(null);
  const [answers, setAnswers] = useState<RiskRecommendationAnswers>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyOpen, setApplyOpen] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getRiskRecommendation(controller.signal),
      getRiskRecommendationQuestions(controller.signal),
      getRiskProfile(controller.signal),
    ])
      .then(([nextRecommendation, nextQuestions, nextProfile]) => {
        setRecommendation(nextRecommendation);
        setQuestions(nextQuestions);
        setProfile(nextProfile.profile);
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiClientError && reason.kind === "cancelled") {
          return;
        }
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "위험 설정 제안을 불러오지 못했습니다.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  const comparisons = useMemo(
    () =>
      recommendationFields.map((field) => ({
        ...field,
        current: profile?.[field.profileKey] ?? null,
        suggested: recommendation?.[field.key] ?? null,
      })),
    [profile, recommendation],
  );

  function updateAnswer(
    key: keyof RiskRecommendationAnswers,
    value: string,
  ) {
    setAnswers((current) => ({
      ...current,
      [key]: value || null,
    }));
    setNotice("답변을 반영하려면 다시 분석을 눌러 주세요.");
  }

  async function refresh() {
    setRefreshing(true);
    setError("");
    setNotice("");
    try {
      const next = await refreshRiskRecommendation(answers);
      setRecommendation(next);
      setNotice(
        "현재 답변과 등록 종목을 기준으로 다시 분석했습니다. 아직 저장되지 않았습니다.",
      );
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "위험 설정 제안을 다시 분석하지 못했습니다.",
      );
    } finally {
      setRefreshing(false);
    }
  }

  async function apply(mode: "ALL" | "CHANGED_ONLY") {
    if (!recommendation) return;
    setApplying(true);
    setError("");
    try {
      const result = await applyRiskRecommendation({
        answers,
        expectedPortfolioFingerprint:
          recommendation.portfolioFingerprint,
        recommendationVersion: recommendation.recommendationVersion,
        mode,
      });
      setRecommendation(result.recommendation);
      setProfile(result.profile);
      setApplyOpen(false);
      setNotice(
        mode === "ALL"
          ? "자동 제안을 전체 적용했습니다."
          : "기존 값과 다른 제안 항목만 적용했습니다.",
      );
    } catch (reason) {
      setApplyOpen(false);
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "위험 설정 제안을 적용하지 못했습니다.",
      );
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label="투자 위험 설정 방식"
        className="grid grid-cols-2 gap-2 rounded-2xl border border-border bg-card p-2"
      >
        {[
          ["AUTO", "자동 제안"],
          ["CUSTOM", "사용자 지정"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value as Tab)}
            className={`min-h-11 rounded-xl px-3 text-sm font-bold ${
              tab === value
                ? "bg-cyan text-background"
                : "text-secondary hover:bg-surface"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "CUSTOM" ? (
        <>
          <p className="rounded-xl border border-border bg-surface p-4 text-sm text-secondary">
            기존 7단계 마법사입니다. 자동 제안은 이 화면을 열거나
            저장하는 것만으로 적용되지 않습니다.
          </p>
          <RiskProfileWizard suggestion={recommendation} />
        </>
      ) : (
        <Card title="등록 종목 기반 위험 설정 자동 제안">
          {loading ? (
            <p className="py-12 text-center text-sm text-secondary">
              등록 종목과 거래 기록을 분석하는 중...
            </p>
          ) : error && !recommendation ? (
            <div
              role="alert"
              className="rounded-xl border border-red/40 bg-red/10 p-4"
            >
              <p className="text-sm font-semibold text-red">{error}</p>
              <button
                type="button"
                onClick={() => setReloadKey((current) => current + 1)}
                className="mt-3 min-h-10 rounded-lg border border-red/40 px-4 text-sm font-bold text-red"
              >
                다시 시도
              </button>
            </div>
          ) : recommendation ? (
            <div className="space-y-6">
              {recommendation.portfolioChanged ? (
                <p
                  role="status"
                  className="rounded-xl border border-yellow/50 bg-yellow/10 p-4 text-sm font-semibold"
                >
                  등록 종목이 변경되어 새로운 위험 설정 제안이
                  있습니다. 기존 설정은 유지됩니다.
                </p>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-border bg-surface p-4">
                  <p className="text-xs text-muted">제안 성향</p>
                  <p className="mt-1 text-lg font-bold text-cyan">
                    {riskStyleLabels[recommendation.suggestedRiskStyle]}
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-surface p-4">
                  <p className="text-xs text-muted">분석 신뢰도</p>
                  <p className="mt-1 text-lg font-bold">
                    {confidenceLabels[recommendation.confidence]}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    시장 데이터 제공자가 미설정이면 높음이 될 수 없습니다.
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-surface p-4">
                  <p className="text-xs text-muted">데이터 기준</p>
                  <p className="mt-1 font-bold">통화별 매수 원가</p>
                  <p className="mt-1 text-xs text-muted">
                    시가평가 비중·가짜 환율 미사용
                  </p>
                </div>
              </div>

              <section>
                <h3 className="font-bold">최소 확인 질문</h3>
                <p className="mt-1 text-sm text-secondary">
                  답하지 않아도 제안은 볼 수 있으며 미확인 항목으로
                  표시됩니다.
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  {questions?.items.map((question) => (
                    <label
                      key={question.id}
                      className="text-sm font-semibold"
                    >
                      {question.prompt}
                      <select
                        value={answers[question.id] ?? ""}
                        onChange={(event) =>
                          updateAnswer(question.id, event.target.value)
                        }
                        className="mt-2 min-h-11 w-full rounded-xl border border-border bg-surface px-3"
                      >
                        <option value="">답하지 않음</option>
                        {question.options.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
              </section>

              <section>
                <h3 className="font-bold">제안 항목</h3>
                <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {comparisons.map((item) => {
                    const percent = item.label.includes("비중") ||
                      item.label.includes("검토선") ||
                      item.label.includes("한도");
                    return (
                      <div
                        key={item.key}
                        className="rounded-xl border border-border bg-surface p-3"
                      >
                        <dt className="text-xs text-muted">{item.label}</dt>
                        <dd className="mt-1 font-bold">
                          {valueText(item.suggested, percent)}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </section>

              <section className="grid gap-4 lg:grid-cols-2">
                <div>
                  <h3 className="font-bold">제안 이유</h3>
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-secondary">
                    {recommendation.reasons.map((reason) => (
                      <li key={reason} className="rounded-xl bg-surface p-3">
                        {reason}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="font-bold">부족한 정보</h3>
                  <ul className="mt-3 flex flex-wrap gap-2">
                    {recommendation.missingInputs.map((item) => (
                      <li
                        key={item}
                        className="rounded-full border border-yellow/40 bg-yellow/10 px-3 py-2 text-xs font-semibold"
                      >
                        {missingLabels[item] ?? item}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-4 rounded-xl border border-border bg-surface p-4 text-sm text-secondary">
                    <p>
                      보유 {recommendation.dataCoverage.holdingCount}종목 ·
                      거래 {recommendation.dataCoverage.transactionCount}건 ·
                      추가매수{" "}
                      {recommendation.dataCoverage.additionalBuyCount}회
                    </p>
                    <p className="mt-1">
                      마지막 분석{" "}
                      {new Date(recommendation.generatedAt).toLocaleString(
                        "ko-KR",
                      )}
                    </p>
                  </div>
                </div>
              </section>

              {error ? (
                <p
                  role="alert"
                  className="rounded-xl border border-red/40 bg-red/10 p-3 text-sm text-red"
                >
                  {error}
                </p>
              ) : null}
              {notice ? (
                <p
                  role="status"
                  className="rounded-xl border border-cyan/40 bg-cyan/10 p-3 text-sm"
                >
                  {notice}
                </p>
              ) : null}

              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={refreshing}
                  className="min-h-11 rounded-xl border border-border px-4 font-bold disabled:opacity-50"
                >
                  {refreshing ? "분석 중..." : "다시 분석"}
                </button>
                <button
                  type="button"
                  onClick={() => setApplyOpen(true)}
                  className="min-h-11 rounded-xl bg-cyan px-4 font-bold text-background"
                >
                  이 제안 적용
                </button>
                <button
                  type="button"
                  onClick={() => setTab("CUSTOM")}
                  className="min-h-11 rounded-xl border border-border px-4 font-bold"
                >
                  사용자 지정으로 수정
                </button>
              </div>
            </div>
          ) : null}
        </Card>
      )}

      {applyOpen && recommendation ? (
        <Dialog
          title="위험 설정 제안 적용 확인"
          description="사용자가 선택하기 전에는 기존 위험 설정을 변경하지 않습니다."
          onRequestClose={() => {
            if (!applying) setApplyOpen(false);
          }}
        >
          <div className="overflow-auto p-4 sm:p-6">
            <div className="min-w-[32rem] overflow-hidden rounded-xl border border-border">
              <div className="grid grid-cols-3 bg-surface px-3 py-2 text-xs font-bold text-muted">
                <span>항목</span>
                <span>기존 값</span>
                <span>제안 값</span>
              </div>
              {comparisons.map((item) => (
                <div
                  key={item.key}
                  className="grid grid-cols-3 border-t border-border px-3 py-3 text-sm"
                >
                  <span className="font-semibold">{item.label}</span>
                  <span>{valueText(item.current)}</span>
                  <span className="font-bold text-cyan">
                    {valueText(item.suggested)}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-4 rounded-xl bg-surface p-4 text-sm leading-6 text-secondary">
              변경 이유: 현재 등록 종목의 통화별 매수 원가 집중도,
              자산 종류와 거래 기록, 사용자가 답한 확인 질문을
              반영합니다. 현재가·시장 변동성·현금 잔액은 추정하지
              않습니다.
            </p>
          </div>
          <footer className="flex flex-col-reverse gap-2 border-t border-border p-4 sm:flex-row sm:justify-end sm:px-6">
            <button
              type="button"
              onClick={() => setApplyOpen(false)}
              disabled={applying}
              className="min-h-11 rounded-xl border border-border px-4 font-bold"
            >
              취소
            </button>
            <button
              type="button"
              onClick={() => apply("CHANGED_ONLY")}
              disabled={applying}
              className="min-h-11 rounded-xl border border-cyan/50 px-4 font-bold text-cyan disabled:opacity-50"
            >
              변경된 값만 적용
            </button>
            <button
              type="button"
              data-autofocus="true"
              onClick={() => apply("ALL")}
              disabled={applying}
              className="min-h-11 rounded-xl bg-cyan px-4 font-bold text-background disabled:opacity-50"
            >
              {applying ? "적용 중..." : "전체 적용"}
            </button>
          </footer>
        </Dialog>
      ) : null}
    </div>
  );
}
