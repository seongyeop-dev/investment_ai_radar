from __future__ import annotations

import re
from dataclasses import dataclass

from app.providers.reference_translation_nllb import (
    evaluate_korean_translation,
)
from app.services.reference_translation import (
    ReferenceTranslationProvider,
)

_AI_PATTERN = re.compile(
    r"\bAI\b",
    flags=re.IGNORECASE,
)

_HURTLES_AHEAD_PATTERN = re.compile(
    r"\bhurtles\s+ahead\b",
    flags=re.IGNORECASE,
)

_CJK_PATTERN = re.compile(
    r"[\u4e00-\u9fff]",
)

_PROGRESS_TERMS = (
    "\uc804\uc9c4",
    "\ub098\uc544",
    "\uc55e\uc11c",
    "\uc55e\uc7a5",
    "\ubc1c\uc804",
    "\uc9c4\ubcf4",
    "\uac00\uc18d",
    "\ube60\ub974\uac8c",
)

_BAD_PROGRESS_TERMS = (
    "\uace0\ud1b5",
    "\uace0\ud1b5\ubc1b",
    "\ub2f9\ud55c\ub2e4",
    "\uad34\ub85c\uc6c0",
)


@dataclass(frozen=True, slots=True)
class TitleTranslationCandidate:
    name: str
    input_text: str
    priority: int


@dataclass(frozen=True, slots=True)
class TitleTranslationEvaluation:
    candidate_name: str
    candidate_input: str
    translation: str
    priority: int
    score: int
    approved: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TitleTranslationSelection:
    source_title: str
    selected: TitleTranslationEvaluation | None
    evaluations: tuple[
        TitleTranslationEvaluation,
        ...,
    ]


def generate_title_candidates(
    title: str,
) -> tuple[TitleTranslationCandidate, ...]:
    normalized_title = title.strip()

    if not normalized_title:
        return ()

    candidates: list[TitleTranslationCandidate] = []

    seen: set[str] = set()

    def add(
        name: str,
        input_text: str,
        priority: int,
    ) -> None:
        normalized = " ".join(input_text.split())

        key = normalized.casefold()

        if not normalized or key in seen:
            return

        seen.add(key)

        candidates.append(
            TitleTranslationCandidate(
                name=name,
                input_text=normalized,
                priority=priority,
            )
        )

    add(
        "ORIGINAL",
        normalized_title,
        10,
    )

    expanded_ai = _AI_PATTERN.sub(
        "Artificial intelligence",
        normalized_title,
    )

    if expanded_ai != normalized_title:
        add(
            "EXPAND_AI",
            expanded_ai,
            20,
        )

    normalized_hurtles = _HURTLES_AHEAD_PATTERN.sub(
        "advances rapidly",
        normalized_title,
    )

    if normalized_hurtles != normalized_title:
        add(
            "NORMALIZE_HURTLES_AHEAD",
            normalized_hurtles,
            30,
        )

    combined = _AI_PATTERN.sub(
        "Artificial intelligence",
        normalized_hurtles,
    )

    if combined != normalized_title:
        add(
            ("EXPAND_AI_AND_NORMALIZE_HURTLES_AHEAD"),
            combined,
            40,
        )

    return tuple(candidates)


def evaluate_title_translation(
    *,
    source_title: str,
    candidate: TitleTranslationCandidate,
    translated_text: str,
) -> TitleTranslationEvaluation:
    translated = translated_text.strip()

    quality = evaluate_korean_translation(
        source_title,
        translated,
    )

    compact = re.sub(
        r"\s+",
        "",
        translated,
    )

    requires_ai = bool(_AI_PATTERN.search(source_title))

    requires_progress = bool(_HURTLES_AHEAD_PATTERN.search(source_title))

    reasons: list[str] = []
    blocking_reasons: list[str] = []
    score = 0

    if quality.passed:
        score += 50
        reasons.append("STRUCTURE_OK")
    else:
        reasons.extend(quality.reasons)
        blocking_reasons.extend(quality.reasons)

    if _CJK_PATTERN.search(translated):
        score -= 100
        reasons.append("CJK_DETECTED")
        blocking_reasons.append("CJK_DETECTED")

    if requires_ai:
        has_ai_term = "\uc778\uacf5\uc9c0\ub2a5" in compact or "AI" in translated

        if has_ai_term:
            score += 20
            reasons.append("AI_TERM_OK")
        else:
            score -= 40
            reasons.append("AI_TERM_MISSING")
            blocking_reasons.append("AI_TERM_MISSING")

    if requires_progress:
        has_progress_meaning = any(term in compact for term in _PROGRESS_TERMS)

        has_bad_progress_meaning = any(term in compact for term in _BAD_PROGRESS_TERMS)

        if has_progress_meaning:
            score += 30
            reasons.append("PROGRESS_MEANING_OK")
        else:
            score -= 40
            reasons.append("PROGRESS_MEANING_MISSING")
            blocking_reasons.append("PROGRESS_MEANING_MISSING")

        if has_bad_progress_meaning:
            score -= 100
            reasons.append("BAD_PROGRESS_MEANING")
            blocking_reasons.append("BAD_PROGRESS_MEANING")
    else:
        score += 20
        reasons.append("GENERAL_TITLE_ACCEPTED")

    approved = quality.passed and not blocking_reasons and score >= 70

    if approved:
        reasons.append("AUTO_APPROVED")
    else:
        reasons.append("REVIEW_REQUIRED")

    return TitleTranslationEvaluation(
        candidate_name=candidate.name,
        candidate_input=(candidate.input_text),
        translation=translated,
        priority=candidate.priority,
        score=score,
        approved=approved,
        reasons=tuple(reasons),
    )


def select_title_translation(
    *,
    source_title: str,
    provider: ReferenceTranslationProvider,
) -> TitleTranslationSelection:
    candidates = generate_title_candidates(source_title)

    evaluations: list[TitleTranslationEvaluation] = []

    for candidate in candidates:
        try:
            translated = provider.translate(
                candidate.input_text,
                source_language="en",
                target_language="ko",
            )
        except Exception as exc:
            evaluations.append(
                TitleTranslationEvaluation(
                    candidate_name=(candidate.name),
                    candidate_input=(candidate.input_text),
                    translation="",
                    priority=candidate.priority,
                    score=-1000,
                    approved=False,
                    reasons=(
                        "PROVIDER_ERROR",
                        exc.__class__.__name__,
                        "REVIEW_REQUIRED",
                    ),
                )
            )
            continue

        evaluations.append(
            evaluate_title_translation(
                source_title=source_title,
                candidate=candidate,
                translated_text=translated,
            )
        )

    ranked = sorted(
        evaluations,
        key=lambda evaluation: (
            evaluation.approved,
            evaluation.score,
            evaluation.priority,
        ),
        reverse=True,
    )

    selected = ranked[0] if ranked and ranked[0].approved else None

    return TitleTranslationSelection(
        source_title=source_title,
        selected=selected,
        evaluations=tuple(ranked),
    )
