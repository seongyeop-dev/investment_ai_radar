from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.models.analyst_references import (
    AnalystReferenceRecord,
    AnalystTranslationStatus,
)

_HANGUL_PATTERN = re.compile(r"[\uac00-\ud7a3]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")


class ReferenceTranslationProvider(Protocol):
    name: str

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class ReferenceTranslationPlan:
    source_language: str
    translation_status: AnalystTranslationStatus
    title_requires_translation: bool
    abstract_requires_translation: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ReferenceTranslationResult:
    translated: bool
    source_language: str
    translation_status: AnalystTranslationStatus
    provider: str | None
    reason: str


def detect_reference_language(
    title: str | None,
    public_abstract: str | None = None,
) -> str:
    text = " ".join(
        value.strip()
        for value in (
            title,
            public_abstract,
        )
        if value and value.strip()
    )

    if not text:
        return "und"

    hangul_count = len(_HANGUL_PATTERN.findall(text))
    latin_count = len(_LATIN_PATTERN.findall(text))

    if hangul_count >= 2:
        return "ko"

    if latin_count >= 2 and hangul_count == 0:
        return "en"

    return "und"


def plan_reference_translation(
    *,
    title: str,
    public_abstract: str | None,
) -> ReferenceTranslationPlan:
    source_language = detect_reference_language(
        title,
        public_abstract,
    )

    if source_language == "ko":
        return ReferenceTranslationPlan(
            source_language="ko",
            translation_status=(AnalystTranslationStatus.NOT_NEEDED),
            title_requires_translation=False,
            abstract_requires_translation=False,
            reason="SOURCE_ALREADY_KOREAN",
        )

    if source_language == "en":
        return ReferenceTranslationPlan(
            source_language="en",
            translation_status=(AnalystTranslationStatus.PENDING),
            title_requires_translation=True,
            abstract_requires_translation=bool(public_abstract and public_abstract.strip()),
            reason="ENGLISH_TRANSLATION_REQUIRED",
        )

    return ReferenceTranslationPlan(
        source_language="und",
        translation_status=(AnalystTranslationStatus.NOT_REQUESTED),
        title_requires_translation=False,
        abstract_requires_translation=False,
        reason="SOURCE_LANGUAGE_UNDETERMINED",
    )


class AnalystReferenceTranslationService:
    def prepare(
        self,
        reference: AnalystReferenceRecord,
    ) -> ReferenceTranslationPlan:
        plan = plan_reference_translation(
            title=reference.title,
            public_abstract=reference.public_abstract,
        )

        reference.source_language = plan.source_language
        reference.translation_status = plan.translation_status

        if plan.translation_status is AnalystTranslationStatus.NOT_NEEDED:
            self._clear_translation_result(reference)

        return plan

    def translate(
        self,
        reference: AnalystReferenceRecord,
        *,
        provider: ReferenceTranslationProvider,
        now: datetime | None = None,
    ) -> ReferenceTranslationResult:
        plan = self.prepare(reference)

        if plan.translation_status is not AnalystTranslationStatus.PENDING:
            return ReferenceTranslationResult(
                translated=False,
                source_language=(plan.source_language),
                translation_status=(plan.translation_status),
                provider=None,
                reason=plan.reason,
            )

        provider_name = self._provider_name(provider)

        try:
            translated_title = self._translate_required(
                provider,
                reference.title,
                source_language=(plan.source_language),
            )

            translated_abstract = self._translate_optional(
                provider,
                reference.public_abstract,
                source_language=(plan.source_language),
            )
        except Exception as exc:
            reference.translation_status = AnalystTranslationStatus.FAILED
            reference.translation_provider = provider_name
            reference.translation_error = self._error_message(exc)
            reference.translated_title_ko = None
            reference.translated_abstract_ko = None
            reference.translated_at = None

            return ReferenceTranslationResult(
                translated=False,
                source_language=(plan.source_language),
                translation_status=(AnalystTranslationStatus.FAILED),
                provider=provider_name,
                reason="PROVIDER_FAILED",
            )

        reference.translated_title_ko = translated_title
        reference.translated_abstract_ko = translated_abstract
        reference.translation_status = AnalystTranslationStatus.COMPLETED
        reference.translation_provider = provider_name
        reference.translation_error = None
        reference.translated_at = self._utc(now or datetime.now(UTC))

        return ReferenceTranslationResult(
            translated=True,
            source_language=(plan.source_language),
            translation_status=(AnalystTranslationStatus.COMPLETED),
            provider=provider_name,
            reason="TRANSLATION_COMPLETED",
        )

    @staticmethod
    def _translate_required(
        provider: ReferenceTranslationProvider,
        text: str,
        *,
        source_language: str,
    ) -> str:
        translated = provider.translate(
            text,
            source_language=source_language,
            target_language="ko",
        ).strip()

        if not translated:
            raise ValueError("Translation provider returned an empty title.")

        if len(translated) > 500:
            raise ValueError("Translated title exceeds 500 characters.")

        return translated

    @staticmethod
    def _translate_optional(
        provider: ReferenceTranslationProvider,
        text: str | None,
        *,
        source_language: str,
    ) -> str | None:
        if text is None or not text.strip():
            return None

        translated = provider.translate(
            text,
            source_language=source_language,
            target_language="ko",
        ).strip()

        if not translated:
            return None

        if len(translated) > 300:
            raise ValueError("Translated abstract exceeds 300 characters.")

        return translated

    @staticmethod
    def _provider_name(
        provider: ReferenceTranslationProvider,
    ) -> str:
        normalized = provider.name.strip()

        if not normalized:
            raise ValueError("Translation provider name must not be empty.")

        if len(normalized) > 100:
            raise ValueError("Translation provider name exceeds 100 characters.")

        return normalized

    @staticmethod
    def _error_message(
        error: Exception,
    ) -> str:
        message = str(error).strip()

        if not message:
            message = error.__class__.__name__

        return message[:500]

    @staticmethod
    def _clear_translation_result(
        reference: AnalystReferenceRecord,
    ) -> None:
        reference.translated_title_ko = None
        reference.translated_abstract_ko = None
        reference.translation_provider = None
        reference.translation_error = None
        reference.translated_at = None

    @staticmethod
    def _utc(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)
