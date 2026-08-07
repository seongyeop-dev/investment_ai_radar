from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import or_, select

from app.database import Database
from app.models.database import SourceGrade, SourceRecord

EXPECTED_DATABASE_NAME = "investment_ai_radar.db"
EXPECTED_REVISION = "20260803_0017"

SOURCE_SPEC = {
    "name": "Oaktree Howard Marks Memos",
    "source_type": "EXPERT_REFERENCE",
    "source_grade": "A",
    "domain": "oaktreecapital.com",
    "official": True,
    "enabled": True,
    "feed_url": "https://www.oaktreecapital.com/insights",
    "provider_type": "REFERENCE_INDEX",
    "language": "en",
    "request_interval_seconds": 21600,
    "timeout_seconds": 20,
    "max_items": 50,
    "original_source_name": None,
}

PRESERVED_TABLES = (
    "portfolio_items",
    "information_events",
    "analyst_references",
    "analyst_reference_coverages",
    "reference_subscriptions",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or create the official Oaktree reference "
            "source in the migrated real database."
        )
    )

    parser.add_argument(
        "--database-path",
        required=True,
    )

    parser.add_argument(
        "--confirm",
        action="store_true",
    )

    return parser.parse_args()


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def count_rows(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    if not table_exists(
        connection,
        table_name,
    ):
        return 0

    row = connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()

    return int(row[0])


def database_snapshot(
    database_path: Path,
) -> dict[str, object]:
    connection = sqlite3.connect(database_path)

    try:
        revision_row = connection.execute("SELECT version_num FROM alembic_version").fetchone()

        revision = str(revision_row[0]) if revision_row is not None else ""

        integrity_row = connection.execute("PRAGMA integrity_check").fetchone()

        integrity = str(integrity_row[0]) if integrity_row is not None else ""

        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

        counts = {
            table_name: count_rows(
                connection,
                table_name,
            )
            for table_name in (
                "sources",
                *PRESERVED_TABLES,
            )
        }

        return {
            "revision": revision,
            "integrity": integrity,
            "foreign_key_errors": len(foreign_key_errors),
            "counts": counts,
        }
    finally:
        connection.close()


def verify_database(
    database_path: Path,
) -> dict[str, object]:
    if not database_path.is_file():
        raise RuntimeError(f"Database was not found: {database_path}")

    if database_path.name != EXPECTED_DATABASE_NAME:
        raise RuntimeError("Only investment_ai_radar.db is supported.")

    snapshot = database_snapshot(database_path)

    if snapshot["revision"] != EXPECTED_REVISION:
        raise RuntimeError(
            "Unexpected database revision. "
            f"Expected {EXPECTED_REVISION}, "
            f"found {snapshot['revision']}."
        )

    if snapshot["integrity"] != "ok":
        raise RuntimeError("Database integrity check failed.")

    if snapshot["foreign_key_errors"] != 0:
        raise RuntimeError("Foreign key errors were detected.")

    return snapshot


def normalized_source(
    source: SourceRecord,
) -> dict[str, object]:
    grade = source.source_grade

    if hasattr(
        grade,
        "value",
    ):
        grade = grade.value

    return {
        "name": source.name,
        "source_type": source.source_type,
        "source_grade": grade,
        "domain": source.domain,
        "official": source.official,
        "enabled": source.enabled,
        "feed_url": source.feed_url,
        "provider_type": source.provider_type,
        "language": source.language,
        "request_interval_seconds": (source.request_interval_seconds),
        "timeout_seconds": source.timeout_seconds,
        "max_items": source.max_items,
        "original_source_name": (source.original_source_name),
    }


def create_backup(
    database_path: Path,
) -> Path:
    backup_directory = database_path.parent / "backups"

    backup_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    backup_path = backup_directory / (
        f"investment_ai_radar_before_oaktree_source_{timestamp}.db"
    )

    source_connection = sqlite3.connect(database_path)

    destination_connection = sqlite3.connect(backup_path)

    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()

    backup_snapshot = verify_backup(backup_path)

    if backup_snapshot["revision"] != EXPECTED_REVISION:
        raise RuntimeError("Backup revision verification failed.")

    return backup_path


def verify_backup(
    backup_path: Path,
) -> dict[str, object]:
    snapshot = database_snapshot(backup_path)

    if snapshot["integrity"] != "ok":
        raise RuntimeError("Backup integrity check failed.")

    if snapshot["foreign_key_errors"] != 0:
        raise RuntimeError("Backup foreign key verification failed.")

    if backup_path.stat().st_size < 1:
        raise RuntimeError("Backup file is empty.")

    return snapshot


def find_existing_sources(
    database: Database,
) -> list[SourceRecord]:
    with database.session_scope() as session:
        rows = session.scalars(
            select(SourceRecord).where(
                or_(
                    SourceRecord.name == SOURCE_SPEC["name"],
                    SourceRecord.domain == SOURCE_SPEC["domain"],
                )
            )
        )

        return list(rows)


def print_plan(
    database_path: Path,
    snapshot: dict[str, object],
    existing: list[SourceRecord],
) -> None:
    print("=" * 76)
    print("REAL REFERENCE SOURCE BOOTSTRAP")
    print("=" * 76)
    print("Database:", database_path)
    print("Revision:", snapshot["revision"])
    print("Integrity:", snapshot["integrity"])
    print(
        "Foreign key errors:",
        snapshot["foreign_key_errors"],
    )
    print()

    print("PLANNED SOURCE")

    for key, value in SOURCE_SPEC.items():
        print(f"- {key}: {value}")

    print()
    print("EXISTING MATCHES:", len(existing))

    for source in existing:
        print(
            "-",
            source.id,
            source.name,
            source.domain,
            source.provider_type,
        )

    print()
    print("CURRENT TABLE COUNTS")

    counts = snapshot["counts"]

    for table_name, count in counts.items():
        print(f"- {table_name}: {count}")


def main() -> int:
    args = parse_args()

    database_path = Path(args.database_path).resolve()

    before = verify_database(database_path)

    database_url = "sqlite+pysqlite:///" + database_path.as_posix()

    database = Database(database_url)

    existing = find_existing_sources(database)

    print_plan(
        database_path,
        before,
        existing,
    )

    exact_matches = [source for source in existing if normalized_source(source) == SOURCE_SPEC]

    conflicts = [source for source in existing if normalized_source(source) != SOURCE_SPEC]

    if conflicts:
        raise RuntimeError("A conflicting source with the same name or domain already exists.")

    if exact_matches:
        print()
        print("Would create: False")
        print("Reason: EXACT_SOURCE_ALREADY_PRESENT")
        print("Database writes: 0")
        print("Result: SOURCE ALREADY PRESENT")
        return 0

    print()
    print("Would create: True")

    if not args.confirm:
        print("Confirm: False")
        print("Database writes: 0")
        print("Result: CONFIRMATION REQUIRED")
        return 0

    backup_path = create_backup(database_path)

    before_counts = dict(before["counts"])

    with database.session_scope() as session:
        source = SourceRecord(
            name=str(SOURCE_SPEC["name"]),
            source_type=str(SOURCE_SPEC["source_type"]),
            source_grade=SourceGrade.A,
            domain=str(SOURCE_SPEC["domain"]),
            official=bool(SOURCE_SPEC["official"]),
            enabled=bool(SOURCE_SPEC["enabled"]),
            feed_url=str(SOURCE_SPEC["feed_url"]),
            provider_type=str(SOURCE_SPEC["provider_type"]),
            language=str(SOURCE_SPEC["language"]),
            request_interval_seconds=int(SOURCE_SPEC["request_interval_seconds"]),
            timeout_seconds=int(SOURCE_SPEC["timeout_seconds"]),
            max_items=int(SOURCE_SPEC["max_items"]),
            original_source_name=None,
        )

        session.add(source)
        session.flush()

        source_id = source.id

    after = verify_database(database_path)
    after_counts = dict(after["counts"])

    if after_counts["sources"] != before_counts["sources"] + 1:
        raise RuntimeError("Unexpected sources count after write.")

    for table_name in PRESERVED_TABLES:
        if after_counts[table_name] != before_counts[table_name]:
            raise RuntimeError(f"{table_name} changed unexpectedly.")

    verified = find_existing_sources(database)

    if len(verified) != 1 or normalized_source(verified[0]) != SOURCE_SPEC:
        raise RuntimeError("Created source verification failed.")

    print()
    print("=" * 76)
    print("SOURCE CREATION RESULT")
    print("=" * 76)
    print("Backup:", backup_path)
    print("Created source ID:", source_id)
    print(
        "Sources:",
        before_counts["sources"],
        "->",
        after_counts["sources"],
    )

    for table_name in PRESERVED_TABLES:
        print(
            f"{table_name}:",
            before_counts[table_name],
            "->",
            after_counts[table_name],
        )

    print("Integrity:", after["integrity"])
    print(
        "Foreign key errors:",
        after["foreign_key_errors"],
    )
    print("External documents downloaded: 0")
    print("Database writes: 1")
    print("Result: REAL SOURCE BOOTSTRAP PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
