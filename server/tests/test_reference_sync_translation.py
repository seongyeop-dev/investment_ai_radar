from __future__ import annotations

from datetime import UTC, datetime

from app.models.analyst_references import (
    AnalystTranslationStatus,
)
from app.services.reference_sync import (
    build_reference_translation_fields,
)

NOW = datetime(
    2026,
    7,
    31,
    1,
    30,
    tzinfo=UTC,
)


class StaticProvider:
    name = "test-static-provider"

    def __init__(
        self,
        translation: str,
    ) -> None:
        self.translation = translation
        self.calls = 0

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> str:
        del text

        assert source_language == "en"
        assert target_language == "ko"

        self.calls += 1
        return self.translation


class FailingProvider:
    name = "test-failing-provider"

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

        raise RuntimeError("translation unavailable")


def test_korean_title_does_not_need_translation() -> None:
    result = build_reference_translation_fields(
        title=("\uc2e0\uc131\uc7a5 \uc0ac\uc5c5\uc758 \uc99d\uba85\ub9cc \ub0a8\uc558\ub2e4"),
        public_abstract=None,
        provider=None,
        now=NOW,
    )

    assert result.source_language == "ko"
    assert result.translated_title_ko is None
    assert result.translation_status is AnalystTranslationStatus.NOT_NEEDED
    assert result.translation_provider is None
    assert result.translation_error is None
    assert result.translated_at is None


def test_english_title_without_provider_is_pending() -> None:
    result = build_reference_translation_fields(
        title="Is It a Bubble?",
        public_abstract=None,
        provider=None,
        now=NOW,
    )

    assert result.source_language == "en"
    assert result.translated_title_ko is None
    assert result.translation_status is AnalystTranslationStatus.PENDING
    assert result.translation_provider is None
    assert result.translation_error == "TRANSLATION_PROVIDER_NOT_CONFIGURED"
    assert result.translated_at is None


def test_approved_english_title_is_completed() -> None:
    provider = StaticProvider("\uac70\ud488\uc778\uac00\uc694?")

    result = build_reference_translation_fields(
        title="Is It a Bubble?",
        public_abstract=None,
        provider=provider,
        now=NOW,
    )

    assert result.source_language == "en"
    assert result.translated_title_ko == "\uac70\ud488\uc778\uac00\uc694?"
    assert result.translation_status is AnalystTranslationStatus.COMPLETED
    assert result.translation_provider == provider.name
    assert result.translation_error is None
    assert result.translated_at == NOW
    assert provider.calls >= 1


def test_failed_provider_is_not_saved_as_completed() -> None:
    provider = FailingProvider()

    result = build_reference_translation_fields(
        title="Is It a Bubble?",
        public_abstract=None,
        provider=provider,
        now=NOW,
    )

    assert result.source_language == "en"
    assert result.translated_title_ko is None
    assert result.translation_status is AnalystTranslationStatus.PENDING
    assert result.translation_provider == provider.name
    assert result.translation_error in {
        "TITLE_REVIEW_REQUIRED",
        "TRANSLATION_PROVIDER_ERROR:RuntimeError",
    }
    assert result.translated_at is None
