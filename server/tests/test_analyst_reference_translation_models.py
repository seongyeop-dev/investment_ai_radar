from __future__ import annotations

import pytest

from app.models.analyst_references import (
    AnalystReferenceRecord,
    AnalystTranslationStatus,
)
from app.schemas.analyst_references import (
    AnalystReferenceRead,
)


def test_translation_status_values_are_stable() -> None:
    assert {status.value for status in AnalystTranslationStatus} == {
        "NOT_REQUESTED",
        "PENDING",
        "COMPLETED",
        "FAILED",
        "NOT_NEEDED",
    }


def test_translation_columns_are_registered() -> None:
    columns = AnalystReferenceRecord.__table__.c

    assert columns.source_language.nullable is False
    assert columns.translated_title_ko.nullable is True
    assert columns.translated_abstract_ko.nullable is True
    assert columns.translation_status.nullable is False
    assert columns.translation_provider.nullable is True
    assert columns.translation_error.nullable is True
    assert columns.translated_at.nullable is True

    assert columns.source_language.default.arg == "und"
    assert columns.translation_status.default.arg is AnalystTranslationStatus.NOT_REQUESTED


def test_translation_schema_fields_are_exposed() -> None:
    expected = {
        "source_language",
        "translated_title_ko",
        "translated_abstract_ko",
        "translation_status",
        "translation_provider",
        "translation_error",
        "translated_at",
    }

    assert expected.issubset(AnalystReferenceRead.model_fields)


def test_translation_text_is_normalized() -> None:
    record = AnalystReferenceRecord()

    record.source_language = " EN-us "
    record.translated_title_ko = " translated title "
    record.translated_abstract_ko = " translated abstract "
    record.translation_provider = " local-provider "
    record.translation_error = " temporary failure "

    assert record.source_language == "en-us"
    assert record.translated_title_ko == "translated title"
    assert record.translated_abstract_ko == "translated abstract"
    assert record.translation_provider == "local-provider"
    assert record.translation_error == "temporary failure"


def test_translation_length_limits_are_enforced() -> None:
    record = AnalystReferenceRecord()

    with pytest.raises(
        ValueError,
        match="source_language",
    ):
        record.source_language = "x" * 13

    with pytest.raises(
        ValueError,
        match="translated_title_ko",
    ):
        record.translated_title_ko = "x" * 501

    with pytest.raises(
        ValueError,
        match="translated_abstract_ko",
    ):
        record.translated_abstract_ko = "x" * 301

    with pytest.raises(
        ValueError,
        match="translation_provider",
    ):
        record.translation_provider = "x" * 101

    with pytest.raises(
        ValueError,
        match="translation_error",
    ):
        record.translation_error = "x" * 501
