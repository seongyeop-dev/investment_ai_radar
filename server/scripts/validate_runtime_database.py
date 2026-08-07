from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

EXPECTED_RUNTIME_REVISION = "20260803_0017"


class RuntimeDatabaseValidationError(RuntimeError):
    def __init__(
        self,
        *,
        check: str,
        message: str,
    ) -> None:
        super().__init__(f"{check}: {message}")
        self.check = check
        self.message = message


@dataclass(frozen=True, slots=True)
class RuntimeDatabaseValidation:
    revision: str
    quick_check: str
    foreign_key_errors: int


def readonly_sqlite_uri(database_path: Path) -> str:
    return f"{database_path.resolve().as_uri()}?mode=ro"


def validate_runtime_database(
    database_path: Path,
    *,
    expected_revision: str = EXPECTED_RUNTIME_REVISION,
) -> RuntimeDatabaseValidation:
    path = database_path.resolve()

    if not path.is_file():
        raise RuntimeDatabaseValidationError(
            check="file_exists",
            message="database file was not found",
        )

    try:
        connection = sqlite3.connect(
            readonly_sqlite_uri(path),
            uri=True,
        )
    except sqlite3.Error as exc:
        raise RuntimeDatabaseValidationError(
            check="connection",
            message="read-only SQLite connection failed",
        ) from exc

    try:
        connection.execute("PRAGMA query_only = ON")

        version_table = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'alembic_version'
            """
        ).fetchone()

        if version_table is None:
            raise RuntimeDatabaseValidationError(
                check="alembic_version",
                message="alembic_version table was not found",
            )

        revision_rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()

        if len(revision_rows) != 1:
            raise RuntimeDatabaseValidationError(
                check="revision",
                message="exactly one Alembic revision is required",
            )

        revision = str(revision_rows[0][0])

        if revision != expected_revision:
            raise RuntimeDatabaseValidationError(
                check="revision",
                message=(f"expected {expected_revision}, found {revision}"),
            )

        quick_check_rows = connection.execute("PRAGMA quick_check").fetchall()
        quick_check_values = tuple(str(row[0]) for row in quick_check_rows)

        if quick_check_values != ("ok",):
            raise RuntimeDatabaseValidationError(
                check="quick_check",
                message="SQLite quick_check did not return ok",
            )

        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

        if foreign_key_errors:
            raise RuntimeDatabaseValidationError(
                check="foreign_key_check",
                message=(f"found {len(foreign_key_errors)} foreign key error(s)"),
            )

        return RuntimeDatabaseValidation(
            revision=revision,
            quick_check=quick_check_values[0],
            foreign_key_errors=0,
        )
    except sqlite3.Error as exc:
        raise RuntimeDatabaseValidationError(
            check="sqlite_read",
            message="SQLite validation query failed",
        ) from exc
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Validate a runtime SQLite database through a read-only connection.")
    )
    parser.add_argument(
        "--database-path",
        required=True,
    )
    parser.add_argument(
        "--expected-revision",
        default=EXPECTED_RUNTIME_REVISION,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        result = validate_runtime_database(
            Path(args.database_path),
            expected_revision=args.expected_revision,
        )
    except RuntimeDatabaseValidationError as exc:
        print(
            f"DATABASE_VALIDATION_FAILED check={exc.check} message={exc.message}",
            file=sys.stderr,
        )
        return 1

    print(
        "DATABASE_VALIDATION_OK "
        f"revision={result.revision} "
        f"quick_check={result.quick_check} "
        "foreign_key_errors=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
