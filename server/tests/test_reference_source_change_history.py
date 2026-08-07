from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.database import Database
from app.models.database import SourceRecord
from app.models.reference_source_history import (
    ReferenceSourceChangeRecord,
)
from app.schemas.reference_source_management import (
    ReferenceSourceImportRequest,
    ReferenceSourceUpdateRequest,
)
from app.services.reference_source_management import (
    ReferenceSourceManagementService,
)


def _database(
    tmp_path: Path,
) -> Database:
    database = Database(
        "sqlite+pysqlite:///" + (tmp_path / "investment_ai_radar.db").as_posix()
    )
    database.create_schema()
    return database


def _payload(
    *,
    confirm: bool,
) -> ReferenceSourceImportRequest:
    return ReferenceSourceImportRequest(
        name="Official Research Source",
        source_grade="A",
        domain="research.example.com",
        official=True,
        enabled=True,
        feed_url=("https://research.example.com/feed"),
        provider_type="REFERENCE_INDEX",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=20,
        max_items=50,
        original_source_name=None,
        confirm=confirm,
    )


def _history(
    database: Database,
) -> list[ReferenceSourceChangeRecord]:
    with database.session_scope() as session:
        return list(
            session.scalars(
                select(ReferenceSourceChangeRecord).order_by(
                    ReferenceSourceChangeRecord.created_at.asc(),
                    ReferenceSourceChangeRecord.id.asc(),
                )
            )
        )


def test_create_records_source_history(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        result = ReferenceSourceManagementService(session).confirm(_payload(confirm=True))
        source_id = str(result.source.id)

    rows = _history(database)

    assert len(rows) == 1

    row = rows[0]

    assert row.source_id == source_id
    assert row.operation == "CREATE"
    assert row.before_values is None
    assert row.after_values["name"] == ("Official Research Source")
    assert row.after_values["source_grade"] == "A"
    assert "request_interval_seconds" in row.changed_fields
    assert row.backup_path is not None
    assert not Path(row.backup_path).is_absolute()

    backup = tmp_path / row.backup_path

    assert backup.is_file()


def test_update_records_only_changed_fields(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        created = ReferenceSourceManagementService(session).confirm(_payload(confirm=True))
        source_id = str(created.source.id)

    with database.session_scope() as session:
        ReferenceSourceManagementService(session).update(
            source_id,
            ReferenceSourceUpdateRequest(
                request_interval_seconds=43200,
                timeout_seconds=25,
                max_items=75,
            ),
        )

    rows = _history(database)

    assert len(rows) == 2

    update = rows[1]

    assert update.operation == "UPDATE"
    assert update.changed_fields == [
        "request_interval_seconds",
        "timeout_seconds",
        "max_items",
    ]
    assert update.before_values == {
        "request_interval_seconds": 21600,
        "timeout_seconds": 20,
        "max_items": 50,
    }
    assert update.after_values == {
        "request_interval_seconds": 43200,
        "timeout_seconds": 25,
        "max_items": 75,
    }
    assert update.backup_path is not None
    assert (tmp_path / update.backup_path).is_file()


def test_noop_update_does_not_record_history(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        created = ReferenceSourceManagementService(session).confirm(_payload(confirm=True))
        source_id = str(created.source.id)

    before = len(_history(database))

    with database.session_scope() as session:
        ReferenceSourceManagementService(session).update(
            source_id,
            ReferenceSourceUpdateRequest(
                request_interval_seconds=21600,
                timeout_seconds=20,
                max_items=50,
            ),
        )

    assert len(_history(database)) == before


def test_source_and_history_share_transaction(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with pytest.raises(RuntimeError), database.session_scope() as session:
        ReferenceSourceManagementService(session).confirm(_payload(confirm=True))

        raise RuntimeError("force transaction rollback")

    with database.session_scope() as session:
        source_count = int(session.scalar(select(func.count()).select_from(SourceRecord)) or 0)
        history_count = int(
            session.scalar(select(func.count()).select_from(ReferenceSourceChangeRecord)) or 0
        )

    assert source_count == 0
    assert history_count == 0
