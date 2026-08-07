#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the portfolio validation database without inserting seed records."
        )
    )
    parser.add_argument("--database")
    parser.add_argument("--database-url")
    parser.add_argument("--expected-demo-root")
    parser.add_argument("--confirm", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.confirm:
        raise SystemExit("Portfolio validation confirmation is required.")

    project_root = Path(__file__).resolve().parents[2]
    default_validation_root = (project_root / ".local" / "portfolio_validation").resolve()
    expected_database = (default_validation_root / "portfolio_validation.db").resolve()

    if args.expected_demo_root:
        requested_root = Path(args.expected_demo_root).resolve()
        if requested_root != default_validation_root:
            raise SystemExit(f"Unexpected validation root: {requested_root}")

    if args.database and args.database_url:
        raise SystemExit("Use either --database or --database-url, not both.")

    if args.database:
        database_path = Path(args.database).resolve()
    elif args.database_url:
        prefix = "sqlite:///"
        if not args.database_url.startswith(prefix):
            raise SystemExit("Only sqlite:/// database URLs are supported.")
        database_path = Path(args.database_url[len(prefix) :]).resolve()
    else:
        database_path = expected_database

    if database_path != expected_database:
        raise SystemExit(f"Unexpected validation database path: {database_path}")
    expected_suffix = Path(".local") / "portfolio_validation" / "portfolio_validation.db"

    if database_path.parts[-3:] != expected_suffix.parts:
        raise SystemExit(f"Unexpected validation database path: {database_path}")

    if not database_path.is_file():
        raise SystemExit(f"Validation database was not created by Alembic: {database_path}")

    connection = sqlite3.connect(database_path)

    try:
        revision_row = connection.execute("SELECT version_num FROM alembic_version").fetchone()

        if revision_row is None:
            raise SystemExit("Alembic revision was not found.")

        table_names = [
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_schema
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                  AND name <> 'alembic_version'
                ORDER BY name
                """
            ).fetchall()
        ]

        nonempty_tables: dict[str, int] = {}

        for table_name in table_names:
            quoted_name = table_name.replace('"', '""')
            count = int(
                connection.execute(f'SELECT COUNT(*) FROM "{quoted_name}"').fetchone()[0]
            )

            if count > 0:
                nonempty_tables[table_name] = count
    finally:
        connection.close()

    status = (
        "empty_validation_ready"
        if not nonempty_tables
        else "existing_validation_data_preserved"
    )

    print(
        json.dumps(
            {
                "status": status,
                "database": str(database_path),
                "revision": revision_row[0],
                "nonempty_tables": nonempty_tables,
                "seed_records_inserted": 0,
                "personal_investment_data_imported": 0,
                "live_provider_requests": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
