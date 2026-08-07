from __future__ import annotations

from datetime import UTC, datetime

from app.models.analyst_references import (
    AnalystReferenceRecord,
    AnalystTranslationStatus,
)
from app.services.reference_translation import (
    AnalystReferenceTranslationService,
    detect_reference_language,
    plan_reference_translation,
)


class StubTranslationProvider:
    name = "stub-local-provider"

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
                "\uc7a5\uc560\ubb3c\uc744 \ub118\uc5b4 "
                "\uc804\uc9c4\ud55c\ub2e4"
            ),
            "Public abstract": ("\uacf5\uac1c \uc694\uc57d"),
        }

        return translations[text]


class FailingTranslationProvider:
    name = "failing-provider"

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
        raise RuntimeError("provider unavailable")


def test_detects_english_and_korean() -> None:
    assert detect_reference_language("AI Hurtles Ahead") == "en"
    assert (
        detect_reference_language(
            "\uc2e0\uc131\uc7a5 \uc0ac\uc5c5\uc758 \uc99d\uba85\ub9cc \ub0a8\uc558\ub2e4"
        )
        == "ko"
    )
    assert detect_reference_language("") == "und"


def test_english_reference_is_planned() -> None:
    plan = plan_reference_translation(
        title="AI Hurtles Ahead",
        public_abstract=None,
    )

    assert plan.source_language == "en"
    assert plan.translation_status is AnalystTranslationStatus.PENDING
    assert plan.title_requires_translation
    assert not plan.abstract_requires_translation


def test_korean_reference_does_not_require_translation() -> None:
    plan = plan_reference_translation(
        title=("\uc2e0\uc131\uc7a5 \uc0ac\uc5c5\uc758 \uc99d\uba85\ub9cc \ub0a8\uc558\ub2e4"),
        public_abstract=None,
    )

    assert plan.source_language == "ko"
    assert plan.translation_status is AnalystTranslationStatus.NOT_NEEDED
    assert not plan.title_requires_translation


def test_translation_preserves_original_text() -> None:
    reference = AnalystReferenceRecord(
        title="AI Hurtles Ahead",
        public_abstract="Public abstract",
    )
    service = AnalystReferenceTranslationService()
    now = datetime(
        2026,
        7,
        30,
        9,
        30,
        tzinfo=UTC,
    )

    result = service.translate(
        reference,
        provider=StubTranslationProvider(),
        now=now,
    )

    assert result.translated
    assert reference.title == "AI Hurtles Ahead"
    assert reference.public_abstract == "Public abstract"
    assert reference.source_language == "en"
    assert reference.translation_status is AnalystTranslationStatus.COMPLETED
    assert reference.translated_title_ko == (
        "\uc778\uacf5\uc9c0\ub2a5\uc740 "
        "\uc7a5\uc560\ubb3c\uc744 \ub118\uc5b4 "
        "\uc804\uc9c4\ud55c\ub2e4"
    )
    assert reference.translated_abstract_ko == "\uacf5\uac1c \uc694\uc57d"
    assert reference.translation_provider == "stub-local-provider"
    assert reference.translation_error is None
    assert reference.translated_at == now


def test_provider_failure_is_recorded() -> None:
    reference = AnalystReferenceRecord(
        title="AI Hurtles Ahead",
        public_abstract=None,
    )
    service = AnalystReferenceTranslationService()

    result = service.translate(
        reference,
        provider=FailingTranslationProvider(),
    )

    assert not result.translated
    assert reference.title == "AI Hurtles Ahead"
    assert reference.translation_status is AnalystTranslationStatus.FAILED
    assert reference.translation_provider == "failing-provider"
    assert reference.translation_error == "provider unavailable"
    assert reference.translated_title_ko is None
    assert reference.translated_at is None
