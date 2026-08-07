from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.reference_scheduler import (
    ReferenceSchedulerLock,
)
from app.services.reference_scheduler_runner import (
    ReferenceScheduledRunConfig,
    build_reference_batch_command,
    run_reference_scheduled_batch,
)

NOW = datetime(
    2026,
    8,
    1,
    2,
    0,
    tzinfo=UTC,
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
            VALUES ('scheduled-reference')
            """
        )
        connection.commit()
    finally:
        connection.close()


def _config(
    tmp_path: Path,
    database_path: Path,
    **overrides: object,
) -> ReferenceScheduledRunConfig:
    values: dict[str, object] = {
        "project_root": tmp_path,
        "database_path": database_path,
        "subscription_name": "Howard Marks",
        "creation_limit": 3,
        "timeout_seconds": 5,
        "lock_stale_seconds": 3600,
        "log_retention_days": 7,
        "console_logging": False,
    }

    values.update(overrides)

    return ReferenceScheduledRunConfig(**values)


def test_build_reference_batch_command(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investment_ai_radar.db"

    config = _config(
        tmp_path,
        database_path,
        expect_created=0,
    )

    command = build_reference_batch_command(config)

    assert command[0] == sys.executable
    assert "--database-path" in command
    assert str(database_path) in command
    assert "--confirm-validation-write" in command
    assert "--allow-real-database" in command
    assert "--expect-created" in command
    assert "0" in command


def test_scheduled_runner_success(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investment_ai_radar.db"

    _create_database(database_path)

    outcome = run_reference_scheduled_batch(
        _config(
            tmp_path,
            database_path,
        ),
        now=NOW,
        command_override=(
            sys.executable,
            "-c",
            "print('scheduled-success')",
        ),
    )

    assert outcome.status == "SUCCESS"
    assert outcome.returncode == 0
    assert outcome.child_returncode == 0
    assert outcome.backup_path is not None
    assert outcome.backup_path.is_file()

    assert not (tmp_path / ".local" / "run" / "reference_scheduler.lock").exists()

    log_text = (
        tmp_path / ".local" / "logs" / "reference_scheduler" / "reference_scheduler.log"
    ).read_text(encoding="utf-8")

    assert "REFERENCE_SCHEDULED_RUN_SUCCESS" in log_text
    assert "scheduled-success" in log_text


def test_scheduled_runner_preserves_child_failure(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investment_ai_radar.db"

    _create_database(database_path)

    outcome = run_reference_scheduled_batch(
        _config(
            tmp_path,
            database_path,
        ),
        now=NOW,
        command_override=(
            sys.executable,
            "-c",
            "raise SystemExit(7)",
        ),
    )

    assert outcome.status == "FAILED"
    assert outcome.returncode == 7
    assert outcome.child_returncode == 7
    assert outcome.backup_path is not None
    assert outcome.backup_path.is_file()


def test_scheduled_runner_timeout(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investment_ai_radar.db"

    _create_database(database_path)

    outcome = run_reference_scheduled_batch(
        _config(
            tmp_path,
            database_path,
            timeout_seconds=1,
        ),
        now=NOW,
        command_override=(
            sys.executable,
            "-c",
            ("import time; time.sleep(3)"),
        ),
    )

    assert outcome.status == "TIMEOUT"
    assert outcome.returncode == 124
    assert outcome.backup_path is not None
    assert outcome.backup_path.is_file()


def test_scheduled_runner_skips_existing_lock(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investment_ai_radar.db"

    _create_database(database_path)

    lock_path = tmp_path / ".local" / "run" / "reference_scheduler.lock"

    first_lock = ReferenceSchedulerLock(
        lock_path,
        stale_after_seconds=3600,
        command=("existing-run",),
    )

    first_lock.acquire(now=NOW)

    try:
        outcome = run_reference_scheduled_batch(
            _config(
                tmp_path,
                database_path,
            ),
            now=(NOW + timedelta(minutes=5)),
            command_override=(
                sys.executable,
                "-c",
                "print('must-not-run')",
            ),
        )
    finally:
        first_lock.release()

    assert outcome.status == "SKIPPED_ALREADY_RUNNING"
    assert outcome.returncode == 0
    assert outcome.backup_path is None


def _add_reference_subscription(
    database_path: Path,
    *,
    display_name: str,
    enabled: bool,
) -> None:
    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE reference_subscriptions (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                enabled BOOLEAN NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO reference_subscriptions (
                id,
                display_name,
                enabled
            )
            VALUES (?, ?, ?)
            """,
            (
                "scheduler-disabled-test",
                display_name,
                int(enabled),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_scheduled_runner_skips_disabled_subscription(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investment_ai_radar.db"
    child_marker = tmp_path / "child-command-ran.txt"

    _create_database(database_path)
    _add_reference_subscription(
        database_path,
        display_name="Howard Marks",
        enabled=False,
    )

    child_script = (
        "from pathlib import Path; "
        f"Path({str(child_marker)!r}).write_text("
        "'unexpected child execution', "
        "encoding='utf-8'"
        ")"
    )

    outcome = run_reference_scheduled_batch(
        _config(
            tmp_path,
            database_path,
        ),
        now=NOW,
        command_override=(
            sys.executable,
            "-c",
            child_script,
        ),
    )

    assert outcome.status == "SKIPPED_DISABLED"
    assert outcome.returncode == 0
    assert outcome.backup_path is None
    assert outcome.child_returncode is None
    assert outcome.elapsed_seconds is None

    assert not child_marker.exists()

    lock_path = tmp_path / ".local" / "run" / "reference_scheduler.lock"

    assert not lock_path.exists()

    backup_databases = [
        path for path in tmp_path.rglob("*.db") if path.resolve() != database_path.resolve()
    ]

    assert backup_databases == []

    log_path = tmp_path / ".local" / "logs" / "reference_scheduler" / "reference_scheduler.log"

    assert log_path.is_file()

    log_text = log_path.read_text(
        encoding="utf-8",
    )

    assert "REFERENCE_SCHEDULED_RUN_SKIPPED" in log_text
    assert "reason=subscription_disabled" in log_text
    assert "REFERENCE_DATABASE_BACKUP_CREATED" not in log_text
    assert "REFERENCE_BATCH_STDOUT" not in log_text
