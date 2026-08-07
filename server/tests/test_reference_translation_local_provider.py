from __future__ import annotations

from pathlib import Path

import pytest

from app.providers.reference_translation_local import (
    DEFAULT_MODEL_NAME,
    LocalMarianTranslationProvider,
)


def test_provider_configuration_is_stable(
    tmp_path: Path,
) -> None:
    provider = LocalMarianTranslationProvider(
        cache_dir=tmp_path,
        local_files_only=True,
    )

    assert provider.model_name == DEFAULT_MODEL_NAME
    assert provider.cache_dir == tmp_path
    assert provider.local_files_only
    assert provider.name == (f"local-marian:{DEFAULT_MODEL_NAME}")


def test_empty_text_does_not_load_model() -> None:
    provider = LocalMarianTranslationProvider(
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
    provider = LocalMarianTranslationProvider(
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
        LocalMarianTranslationProvider(
            max_source_tokens=0,
        )

    with pytest.raises(
        ValueError,
        match="max_new_tokens",
    ):
        LocalMarianTranslationProvider(
            max_new_tokens=0,
        )
