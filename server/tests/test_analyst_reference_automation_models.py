from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.database import Base
from app.models.analyst_references import (
    AnalystIngestMode,
    AnalystReferenceRecord,
    AnalystUserState,
)


def test_analyst_automation_enums() -> None:
    assert AnalystIngestMode.MANUAL.value == "MANUAL"
    assert AnalystIngestMode.AUTOMATIC.value == "AUTOMATIC"

    assert AnalystUserState.NEW.value == "NEW"
    assert AnalystUserState.READ.value == "READ"
    assert AnalystUserState.ARCHIVED.value == "ARCHIVED"
    assert AnalystUserState.HIDDEN.value == "HIDDEN"


def test_analyst_automation_columns_are_registered() -> None:
    table = Base.metadata.tables["analyst_references"]

    assert table.c.source_id.nullable is True
    assert table.c.subscription_id.nullable is True
    assert table.c.provider_item_id.nullable is True

    assert table.c.ingest_mode.nullable is False
    assert table.c.user_state.nullable is False
    assert table.c.discovered_at.nullable is False

    source_foreign_key = next(iter(table.c.source_id.foreign_keys))
    subscription_foreign_key = next(iter(table.c.subscription_id.foreign_keys))

    assert source_foreign_key.target_fullname == "sources.id"
    assert subscription_foreign_key.target_fullname == "reference_subscriptions.id"


def test_analyst_automation_constraints_are_registered() -> None:
    table = Base.metadata.tables["analyst_references"]

    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "uq_analyst_reference_source_provider_item" in unique_names
    assert "ck_analyst_reference_ingest_origin" in check_names


def test_provider_item_id_is_normalized() -> None:
    record = AnalystReferenceRecord(
        provider_item_id="  memo   2026-07-30  ",
    )

    assert record.provider_item_id == "memo 2026-07-30"


def test_empty_provider_item_id_becomes_none() -> None:
    record = AnalystReferenceRecord(
        provider_item_id="   ",
    )

    assert record.provider_item_id is None
