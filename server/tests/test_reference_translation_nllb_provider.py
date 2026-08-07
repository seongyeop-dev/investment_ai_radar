from __future__ import annotations

from pathlib import Path

import pytest

from app.providers.reference_translation_nllb import (
    DEFAULT_MODEL_NAME,
    LocalNllbTranslationProvider,
    evaluate_korean_translation,
)


def test_provider_configuration_is_stable(
    tmp_path: Path,
) -> None:
    provider = LocalNllbTranslationProvider(
        cache_dir=tmp_path,
        local_files_only=True,
    )

    assert provider.model_name == DEFAULT_MODEL_NAME
    assert provider.cache_dir == tmp_path
    assert provider.local_files_only
    assert provider.name == (f"local-nllb:{DEFAULT_MODEL_NAME}")


def test_empty_text_does_not_load_model() -> None:
    provider = LocalNllbTranslationProvider(
        local_files_only=True,
    )

    result = provider.translate(
        "   ",
        source_language="en",
        target_language="ko",
    )

    assert result == ""
    assert provider._model is None


def test_unsupported_language_pair_is_rejected() -> None:
    provider = LocalNllbTranslationProvider(
        local_files_only=True,
    )

    with pytest.raises(
        ValueError,
        match="English source",
    ):
        provider.translate(
            "test",
            source_language="ja",
            target_language="ko",
        )

    with pytest.raises(
        ValueError,
        match="Korean target",
    ):
        provider.translate(
            "test",
            source_language="en",
            target_language="fr",
        )

    assert provider._model is None


def test_invalid_limits_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="max_source_tokens",
    ):
        LocalNllbTranslationProvider(
            max_source_tokens=0,
        )

    with pytest.raises(
        ValueError,
        match="must not exceed 512",
    ):
        LocalNllbTranslationProvider(
            max_source_tokens=513,
        )

    with pytest.raises(
        ValueError,
        match="max_new_tokens",
    ):
        LocalNllbTranslationProvider(
            max_new_tokens=0,
        )

    with pytest.raises(
        ValueError,
        match="num_beams",
    ):
        LocalNllbTranslationProvider(
            num_beams=0,
        )


def test_quality_gate_accepts_korean_result() -> None:
    quality = evaluate_korean_translation(
        "Is It a Bubble?",
        "\uac70\ud488\uc778\uac00?",
    )

    assert quality.passed
    assert quality.hangul_count >= 2
    assert not quality.reasons


def test_quality_gate_allows_embedded_english_term() -> None:
    quality = evaluate_korean_translation(
        "AI Hurtles Ahead",
        "AI\ub294 \uacc4\uc18d \uc55e\uc73c\ub85c \ub098\uc544\uac04\ub2e4",
    )

    assert quality.passed
    assert quality.hangul_ratio >= 0.35


def test_quality_gate_rejects_bad_results() -> None:
    unchanged = evaluate_korean_translation(
        "AI Hurtles Ahead",
        "AI Hurtles Ahead",
    )

    mixed = evaluate_korean_translation(
        "Is It a Bubble?",
        "Your wave \uc911\uad6d\uc740",
    )

    empty = evaluate_korean_translation(
        "Test",
        "   ",
    )

    assert not unchanged.passed
    assert "UNCHANGED_SOURCE" in (unchanged.reasons)

    assert not mixed.passed
    assert "LOW_HANGUL_RATIO" in (mixed.reasons)

    assert not empty.passed
    assert "EMPTY_RESULT" in (empty.reasons)
