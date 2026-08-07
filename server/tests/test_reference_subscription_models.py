from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)


def test_reference_subscription_normalizes_values() -> None:
    record = ReferenceSubscriptionRecord(
        source_id=str(uuid4()),
        subject_type=ReferenceSubjectType.EXPERT,
        display_name="  Howard   Marks  ",
        match_mode=ReferenceMatchMode.AUTHOR,
        match_terms=[
            " Howard Marks ",
            "howard marks",
            "",
        ],
    )

    assert record.display_name == "Howard Marks"
    assert record.match_terms == ["Howard Marks"]
    assert record.subject_type is ReferenceSubjectType.EXPERT
    assert record.match_mode is ReferenceMatchMode.AUTHOR


def test_reference_subscription_allows_source_wide_mode() -> None:
    record = ReferenceSubscriptionRecord(
        source_id=str(uuid4()),
        subject_type=ReferenceSubjectType.INSTITUTION,
        display_name="Berkshire Hathaway",
        match_mode=ReferenceMatchMode.ALL_SOURCE,
        match_terms=[],
    )

    assert record.display_name == "Berkshire Hathaway"
    assert record.match_terms == []


def test_reference_subscription_rejects_empty_name() -> None:
    with pytest.raises(
        ValueError,
        match="display_name must not be empty",
    ):
        ReferenceSubscriptionRecord(
            source_id=str(uuid4()),
            subject_type=ReferenceSubjectType.EXPERT,
            display_name="   ",
            match_mode=ReferenceMatchMode.AUTHOR,
            match_terms=["Warren Buffett"],
        )


def test_reference_subscription_rejects_non_string_term() -> None:
    with pytest.raises(
        ValueError,
        match="match_terms must contain strings",
    ):
        ReferenceSubscriptionRecord(
            source_id=str(uuid4()),
            subject_type=ReferenceSubjectType.EXPERT,
            display_name="Warren Buffett",
            match_mode=ReferenceMatchMode.AUTHOR,
            match_terms=["Warren Buffett", 123],
        )
