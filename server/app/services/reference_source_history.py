from __future__ import annotations

from enum import Enum
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.reference_source_history import (
    ReferenceSourceChangeRecord,
)
from app.services.sqlite_backup import (
    sqlite_database_path,
)

MANAGED_REFERENCE_SOURCE_FIELDS = (
    "name",
    "source_grade",
    "domain",
    "official",
    "enabled",
    "feed_url",
    "provider_type",
    "language",
    "request_interval_seconds",
    "timeout_seconds",
    "max_items",
    "original_source_name",
)


def _json_value(
    value: object,
) -> object:
    if isinstance(value, Enum):
        return value.value

    return value


def reference_source_snapshot(
    source: object,
) -> dict[str, object]:
    return {
        field: _json_value(getattr(source, field))
        for field in (MANAGED_REFERENCE_SOURCE_FIELDS)
    }


def _backup_reference(
    session: Session,
    backup_path: Path | None,
) -> str | None:
    if backup_path is None:
        return None

    database_path = sqlite_database_path(session)

    if database_path is None:
        return backup_path.name

    reference_root = database_path.parent

    for candidate in (
        database_path.parent,
        *database_path.parents,
    ):
        if candidate.name == ".local":
            reference_root = candidate
            break

    try:
        return backup_path.resolve().relative_to(reference_root.resolve()).as_posix()
    except ValueError:
        return backup_path.name


def create_reference_source_change(
    session: Session,
    *,
    source_id: str,
    operation: str,
    changed_fields: list[str],
    before_values: (dict[str, object] | None),
    after_values: dict[str, object],
    backup_path: Path | None,
) -> ReferenceSourceChangeRecord:
    normalized_operation = operation.strip().upper()

    if normalized_operation not in {
        "CREATE",
        "UPDATE",
    }:
        raise ValueError("Unsupported source change operation.")

    normalized_fields = [
        field for field in (MANAGED_REFERENCE_SOURCE_FIELDS) if field in changed_fields
    ]

    if not normalized_fields:
        raise ValueError("Source change must include at least one changed field.")

    record = ReferenceSourceChangeRecord(
        source_id=source_id,
        operation=normalized_operation,
        changed_fields=normalized_fields,
        before_values=before_values,
        after_values=after_values,
        backup_path=_backup_reference(
            session,
            backup_path,
        ),
    )

    session.add(record)
    session.flush()

    return record
