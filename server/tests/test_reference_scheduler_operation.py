from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from app.services.reference_scheduler import (
    ReferenceSchedulerCommandTimeout,
    create_verified_sqlite_backup,
    run_reference_scheduler_command,
    verify_sqlite_database,
)

REVISION = "20260730_0014"


def _create_database(
    path: Path,
) -> None:
    connection = sqlite3.connect(path)

    try:
        connection.execute(
            """
            CREATE TABLE alembic_version (
                version_num TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO alembic_version (
                version_num
            )
            VALUES (?)
            """,
            (REVISION,),
        )
        connection.execute(
            """
            CREATE TABLE sample_items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO sample_items (
                name
            )
            VALUES ('reference-test')
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_verify_sqlite_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "source.db"

    _create_database(database_path)

    verification = verify_sqlite_database(database_path)

    assert verification.revision == REVISION
    assert verification.integrity == "ok"
    assert verification.foreign_key_errors == ()


def test_create_verified_sqlite_backup(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.db"
    backup_path = tmp_path / "backups" / "backup.db"

    _create_database(source_path)

    verification = create_verified_sqlite_backup(
        source_path,
        backup_path,
    )

    assert backup_path.is_file()
    assert verification.revision == REVISION
    assert verification.integrity == "ok"
    assert verification.foreign_key_errors == ()

    connection = sqlite3.connect(backup_path)

    try:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM sample_items
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 1


def test_scheduler_command_success(
    tmp_path: Path,
) -> None:
    result = run_reference_scheduler_command(
        (
            sys.executable,
            "-c",
            ("print('scheduler-success')"),
        ),
        working_directory=tmp_path,
        timeout_seconds=5,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "scheduler-success"
    assert result.stderr == ""
    assert result.elapsed_seconds >= 0


def test_scheduler_command_preserves_failure(
    tmp_path: Path,
) -> None:
    result = run_reference_scheduler_command(
        (
            sys.executable,
            "-c",
            ("import sys; print('scheduler-error', file=sys.stderr); raise SystemExit(7)"),
        ),
        working_directory=tmp_path,
        timeout_seconds=5,
    )

    assert result.returncode == 7
    assert result.stdout == ""
    assert result.stderr.strip() == "scheduler-error"


def test_scheduler_command_timeout(
    tmp_path: Path,
) -> None:
    with pytest.raises(ReferenceSchedulerCommandTimeout) as captured:
        run_reference_scheduler_command(
            (
                sys.executable,
                "-c",
                ("import time; time.sleep(3)"),
            ),
            working_directory=tmp_path,
            timeout_seconds=1,
        )

    assert captured.value.timeout_seconds == 1
