from __future__ import annotations

from app.models.analyst_references import (
    AnalystIngestMode,
    AnalystReferenceRecord,
    AnalystUserState,
)
from app.schemas.analyst_references import (
    AnalystReferenceRead,
)


def test_analyst_reference_read_exposes_automation_fields() -> None:
    fields = AnalystReferenceRead.model_fields

    assert "source_id" in fields
    assert "subscription_id" in fields
    assert "provider_item_id" in fields
    assert "ingest_mode" in fields
    assert "user_state" in fields
    assert "discovered_at" in fields


def test_manual_origin_column_defaults_are_registered() -> None:
    table = AnalystReferenceRecord.__table__

    assert table.c.ingest_mode.default.arg is AnalystIngestMode.MANUAL
    assert table.c.user_state.default.arg is AnalystUserState.NEW
    assert table.c.discovered_at.default is not None


def test_manual_origin_columns_are_optional() -> None:
    table = AnalystReferenceRecord.__table__

    assert table.c.source_id.nullable is True
    assert table.c.subscription_id.nullable is True
    assert table.c.provider_item_id.nullable is True
