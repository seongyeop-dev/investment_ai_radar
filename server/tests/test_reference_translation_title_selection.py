from __future__ import annotations

from app.services.reference_translation_title_selection import (
    generate_title_candidates,
    select_title_translation,
)


class StubProvider:
    name = "stub-title-provider"

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> str:
        assert source_language == "en"
        assert target_language == "ko"

        translations = {
            "AI Hurtles Ahead": (
                "\uc778\uacf5\uc9c0\ub2a5\uc740 "
                "\uc55e\uc73c\ub85c "
                "\uace0\ud1b5\uc744 "
                "\ub2f9\ud55c\ub2e4"
            ),
            ("Artificial intelligence Hurtles Ahead"): (
                "\uc778\uacf5\uc9c0\ub2a5\uc774 \uc55e\uc7a5\uc11c\uace0 \uc788\ub2e4"
            ),
            "AI advances rapidly": ("AI\ub294 \ube60\ub974\uac8c \ubc1c\uc804\ud55c\ub2e4"),
            ("Artificial intelligence advances rapidly"): (
                "\uc778\uacf5\uc9c0\ub2a5\uc740 "
                "\ube60\ub974\uac8c "
                "\ubc1c\uc804\ud558\uace0 "
                "\uc788\uc2b5\ub2c8\ub2e4"
            ),
            "Is It a Bubble?": ("\uac70\ud488\uc778\uac00\uc694?"),
        }

        return translations[text]


class BadProvider:
    name = "bad-title-provider"

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> str:
        del text
        del source_language
        del target_language

        return "Your wave \u4e2d\u56fd"


def test_generates_combined_normalized_candidate() -> None:
    candidates = generate_title_candidates("AI Hurtles Ahead")

    values = {candidate.name: candidate.input_text for candidate in candidates}

    assert values[("EXPAND_AI_AND_NORMALIZE_HURTLES_AHEAD")] == (
        "Artificial intelligence advances rapidly"
    )


def test_selects_combined_candidate_on_tie() -> None:
    selection = select_title_translation(
        source_title="AI Hurtles Ahead",
        provider=StubProvider(),
    )

    assert selection.selected is not None

    assert selection.selected.candidate_name == ("EXPAND_AI_AND_NORMALIZE_HURTLES_AHEAD")

    assert selection.selected.translation == (
        "\uc778\uacf5\uc9c0\ub2a5\uc740 "
        "\ube60\ub974\uac8c "
        "\ubc1c\uc804\ud558\uace0 "
        "\uc788\uc2b5\ub2c8\ub2e4"
    )

    assert selection.selected.approved
    assert selection.selected.score == 100


def test_general_title_uses_original_translation() -> None:
    selection = select_title_translation(
        source_title="Is It a Bubble?",
        provider=StubProvider(),
    )

    assert selection.selected is not None
    assert selection.selected.candidate_name == "ORIGINAL"
    assert selection.selected.translation == "\uac70\ud488\uc778\uac00\uc694?"
    assert selection.selected.score == 70


def test_bad_mixed_result_requires_review() -> None:
    selection = select_title_translation(
        source_title="Is It a Bubble?",
        provider=BadProvider(),
    )

    assert selection.selected is None
    assert selection.evaluations

    best = selection.evaluations[0]

    assert not best.approved
    assert "CJK_DETECTED" in best.reasons
    assert "REVIEW_REQUIRED" in best.reasons
