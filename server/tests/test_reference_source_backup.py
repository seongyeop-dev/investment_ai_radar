from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.database import Database
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.schemas.reference_source_management import (
    ReferenceSourceImportRequest,
    ReferenceSourceUpdateRequest,
)
from app.services.reference_source_management import (
    ReferenceSourceImportBlockedError,
    ReferenceSourceManagementService,
    ReferenceSourceUpdateConflictError,
)


def _database(
    tmp_path: Path,
) -> Database:
    path = tmp_path / "investment_ai_radar.db"
    database = Database("sqlite+pysqlite:///" + path.as_posix())
    database.create_schema()
    return database


def _import_payload(
    *,
    confirm: bool,
) -> ReferenceSourceImportRequest:
    return ReferenceSourceImportRequest(
        name="Official Research Source",
        source_grade=SourceGrade.A,
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


def _backup_files(
    tmp_path: Path,
) -> list[Path]:
    directory = tmp_path / "backups" / "reference_source_management"

    if not directory.exists():
        return []

    return sorted(directory.rglob("*.db"))


def _source_count(
    database: Database,
) -> int:
    with database.session_scope() as session:
        value = session.scalar(select(func.count()).select_from(SourceRecord))

        return int(value or 0)


def test_preview_does_not_create_backup(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        preview = ReferenceSourceManagementService(session).preview(
            _import_payload(
                confirm=False,
            )
        )

        assert preview.would_create is True

    assert _source_count(database) == 0
    assert _backup_files(tmp_path) == []


def test_confirm_creates_prechange_backup(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        confirmed = ReferenceSourceManagementService(session).confirm(
            _import_payload(
                confirm=True,
            )
        )

        assert confirmed.confirmed is True

    backups = _backup_files(tmp_path)

    assert len(backups) == 1
    assert "source_create" in backups[0].name
    assert _source_count(database) == 1

    with sqlite3.connect(backups[0]) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()

        source_count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()

    assert integrity == ("ok",)
    assert source_count == (0,)


def test_duplicate_confirm_does_not_create_backup(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        ReferenceSourceManagementService(session).confirm(
            _import_payload(
                confirm=True,
            )
        )

    before = _backup_files(tmp_path)

    with pytest.raises(ReferenceSourceImportBlockedError), database.session_scope() as session:
        ReferenceSourceManagementService(session).confirm(
            _import_payload(
                confirm=True,
            )
        )

    assert _backup_files(tmp_path) == before
    assert _source_count(database) == 1


def test_blocked_disable_does_not_create_backup(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        confirmed = ReferenceSourceManagementService(session).confirm(
            _import_payload(
                confirm=True,
            )
        )
        source_id = str(confirmed.source.id)

    with database.session_scope() as session:
        session.add(
            ReferenceSubscriptionRecord(
                source_id=source_id,
                subject_type=(ReferenceSubjectType.EXPERT),
                display_name="Protected Expert",
                match_mode=(ReferenceMatchMode.AUTHOR),
                match_terms=[
                    "Protected Expert",
                ],
                enabled=True,
            )
        )

    before = _backup_files(tmp_path)

    with pytest.raises(ReferenceSourceUpdateConflictError), database.session_scope() as session:
        ReferenceSourceManagementService(session).update(
            source_id,
            ReferenceSourceUpdateRequest(
                enabled=False,
            ),
        )

    assert _backup_files(tmp_path) == before


def test_valid_update_creates_prechange_backup(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        confirmed = ReferenceSourceManagementService(session).confirm(
            _import_payload(
                confirm=True,
            )
        )
        source_id = str(confirmed.source.id)

    with database.session_scope() as session:
        updated = ReferenceSourceManagementService(session).update(
            source_id,
            ReferenceSourceUpdateRequest(
                request_interval_seconds=43200,
                timeout_seconds=25,
                max_items=75,
            ),
        )

        assert updated is not None
        assert updated.request_interval_seconds == 43200

    backups = _backup_files(tmp_path)
    update_backups = [path for path in backups if "source_update" in path.name]

    assert len(update_backups) == 1

    with sqlite3.connect(update_backups[0]) as connection:
        stored = connection.execute(
            """
            SELECT
                request_interval_seconds,
                timeout_seconds,
                max_items
            FROM sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()

    assert stored == (
        21600,
        20,
        50,
    )


def test_noop_update_does_not_create_backup(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    with database.session_scope() as session:
        confirmed = ReferenceSourceManagementService(session).confirm(
            _import_payload(
                confirm=True,
            )
        )
        source_id = str(confirmed.source.id)

    before = _backup_files(tmp_path)

    with database.session_scope() as session:
        ReferenceSourceManagementService(session).update(
            source_id,
            ReferenceSourceUpdateRequest(
                request_interval_seconds=21600,
                timeout_seconds=20,
                max_items=50,
            ),
        )

    assert _backup_files(tmp_path) == before
