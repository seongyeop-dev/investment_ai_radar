from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session


def sqlite_database_path(
    session: Session,
) -> Path | None:
    bind = session.get_bind()

    if bind.dialect.name != "sqlite":
        return None

    engine = getattr(
        bind,
        "engine",
        bind,
    )
    url = getattr(
        engine,
        "url",
        None,
    )
    database = getattr(
        url,
        "database",
        None,
    )

    if not database or database == ":memory:":
        return None

    path = Path(database).expanduser()

    if not path.is_absolute():
        path = path.resolve()

    return path


def _backup_root(
    database_path: Path,
) -> Path:
    candidates = (
        database_path.parent,
        *database_path.parents,
    )

    for candidate in candidates:
        if candidate.name == ".local":
            return candidate / "backups" / "reference_source_management"

    return database_path.parent / "backups" / "reference_source_management"


def create_sqlite_backup(
    session: Session,
    *,
    operation: str,
    now: datetime | None = None,
) -> Path | None:
    database_path = sqlite_database_path(session)

    if database_path is None:
        return None

    if not database_path.is_file():
        raise RuntimeError(f"SQLite database file was not found: {database_path}")

    current = now or datetime.now(UTC)

    if current.tzinfo is None:
        raise ValueError("Backup timestamp must be timezone-aware.")

    safe_operation = re.sub(
        r"[^a-z0-9_-]+",
        "_",
        operation.strip().casefold(),
    ).strip("_")

    if not safe_operation:
        raise ValueError("Backup operation must not be empty.")

    backup_directory = _backup_root(database_path) / current.strftime("%Y%m%d")
    backup_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = current.strftime("%Y%m%dT%H%M%S_%fZ")
    backup_path = backup_directory / (
        f"{database_path.stem}_{safe_operation}_{timestamp}_{uuid4().hex[:8]}.db"
    )

    source_uri = "file:" + database_path.resolve().as_posix() + "?mode=ro"

    try:
        with (
            sqlite3.connect(
                source_uri,
                uri=True,
            ) as source_connection,
            sqlite3.connect(
                backup_path,
            ) as destination_connection,
        ):
            source_connection.backup(destination_connection)

        with sqlite3.connect(
            backup_path,
        ) as verification_connection:
            integrity = verification_connection.execute("PRAGMA integrity_check").fetchone()

            foreign_key_errors = list(
                verification_connection.execute("PRAGMA foreign_key_check")
            )

        if integrity is None or integrity[0] != "ok":
            raise RuntimeError("SQLite backup integrity check failed.")

        if foreign_key_errors:
            raise RuntimeError("SQLite backup foreign-key check failed.")

        return backup_path

    except BaseException:
        backup_path.unlink(
            missing_ok=True,
        )
        raise
