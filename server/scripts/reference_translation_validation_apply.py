from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.providers.reference_translation_nllb import (
    LocalNllbTranslationProvider,
)
from app.services.reference_translation import (
    plan_reference_translation,
)
from app.services.reference_translation_title_selection import (
    select_title_translation,
)

EXPECTED_DATABASE_NAME = "investment_ai_radar_0014_validation.db"
EXPECTED_REVISION = "20260730_0014"
EXPECTED_REFERENCE_COUNT = 4
EXPECTED_ENGLISH_COUNT = 3
EXPECTED_KOREAN_COUNT = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Apply approved Korean titles to the 0014 validation database only.")
    )
    parser.add_argument(
        "--database-path",
        default=(".local/data/" + EXPECTED_DATABASE_NAME),
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
    )
    return parser.parse_args()


def timestamp_value() -> str:
    return (
        datetime.now(UTC)
        .replace(tzinfo=None)
        .isoformat(
            sep=" ",
            timespec="microseconds",
        )
    )


def read_state(
    database_path: Path,
) -> tuple[
    str,
    list[dict[str, object]],
    int,
    str,
]:
    connection = sqlite3.connect(
        (f"file:{database_path.as_posix()}?mode=ro"),
        uri=True,
    )
    connection.row_factory = sqlite3.Row

    try:
        revision = connection.execute(
            """
            SELECT version_num
            FROM alembic_version
            """
        ).fetchone()[0]

        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    title,
                    public_abstract,
                    ingest_mode,
                    source_language,
                    translated_title_ko,
                    translation_status
                FROM analyst_references
                ORDER BY
                    published_at DESC,
                    created_at DESC,
                    id ASC
                """
            ).fetchall()
        ]

        translation_state_count = connection.execute(
            """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE
                    source_language != 'und'
                    OR translated_title_ko IS NOT NULL
                    OR translated_abstract_ko IS NOT NULL
                    OR translation_status != 'NOT_REQUESTED'
                    OR translation_provider IS NOT NULL
                    OR translated_at IS NOT NULL
                """
        ).fetchone()[0]

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()

    return (
        revision,
        rows,
        translation_state_count,
        integrity,
    )


def create_actions(
    rows: list[dict[str, object]],
) -> list[dict[str, str | None]]:
    provider = LocalNllbTranslationProvider(
        cache_dir=Path(".local/models/huggingface").resolve(),
        local_files_only=True,
    )

    actions: list[dict[str, str | None]] = []

    for row in rows:
        reference_id = str(row["id"])
        title = str(row["title"])

        abstract_value = row["public_abstract"]
        public_abstract = str(abstract_value) if abstract_value is not None else None

        plan = plan_reference_translation(
            title=title,
            public_abstract=public_abstract,
        )

        if plan.source_language == "ko":
            actions.append(
                {
                    "id": reference_id,
                    "original_title": title,
                    "source_language": "ko",
                    "translated_title_ko": None,
                    "translation_status": "NOT_NEEDED",
                    "translation_provider": None,
                }
            )
            continue

        if plan.source_language != "en":
            raise RuntimeError(
                f"Unsupported source language for {reference_id}: {plan.source_language}"
            )

        selection = select_title_translation(
            source_title=title,
            provider=provider,
        )

        if selection.selected is None:
            raise RuntimeError(f"No approved translation selected for title: {title}")

        actions.append(
            {
                "id": reference_id,
                "original_title": title,
                "source_language": "en",
                "translated_title_ko": (selection.selected.translation),
                "translation_status": "COMPLETED",
                "translation_provider": provider.name,
            }
        )

    return actions


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
        database_path.stem + "_before_translation_" + timestamp + database_path.suffix
    )

    with sqlite3.connect(database_path) as source, sqlite3.connect(backup_path) as destination:
        source.backup(destination)

    return backup_path


def apply_actions(
    database_path: Path,
    actions: list[dict[str, str | None]],
    expected_titles: tuple[
        tuple[str, str],
        ...,
    ],
) -> dict[str, object]:
    connection = sqlite3.connect(database_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        revision = connection.execute(
            """
            SELECT version_num
            FROM alembic_version
            """
        ).fetchone()[0]

        if revision != EXPECTED_REVISION:
            raise RuntimeError(f"Database revision changed: {revision}")

        current_titles = tuple(
            connection.execute(
                """
                SELECT id, title
                FROM analyst_references
                ORDER BY id
                """
            ).fetchall()
        )

        if current_titles != expected_titles:
            raise RuntimeError("Original reference titles changed before the write.")

        existing_state = connection.execute(
            """
            SELECT COUNT(*)
            FROM analyst_references
            WHERE
                source_language != 'und'
                OR translated_title_ko IS NOT NULL
                OR translated_abstract_ko IS NOT NULL
                OR translation_status != 'NOT_REQUESTED'
                OR translation_provider IS NOT NULL
                OR translated_at IS NOT NULL
            """
        ).fetchone()[0]

        if existing_state != 0:
            raise RuntimeError("Translation state is not empty.")

        now_value = timestamp_value()

        for action in actions:
            translated_at = now_value if action["translation_status"] == "COMPLETED" else None

            cursor = connection.execute(
                """
                UPDATE analyst_references
                SET
                    source_language = ?,
                    translated_title_ko = ?,
                    translated_abstract_ko = NULL,
                    translation_status = ?,
                    translation_provider = ?,
                    translation_error = NULL,
                    translated_at = ?,
                    updated_at = ?
                WHERE
                    id = ?
                    AND title = ?
                    AND source_language = 'und'
                    AND translation_status
                        = 'NOT_REQUESTED'
                    AND translated_title_ko IS NULL
                """,
                (
                    action["source_language"],
                    action["translated_title_ko"],
                    action["translation_status"],
                    action["translation_provider"],
                    translated_at,
                    now_value,
                    action["id"],
                    action["original_title"],
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Expected exactly one updated row "
                    f"for {action['id']}; "
                    f"updated {cursor.rowcount}."
                )

        counts = {
            "references": connection.execute(
                """
                SELECT COUNT(*)
                FROM analyst_references
                """
            ).fetchone()[0],
            "completed": connection.execute(
                """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE translation_status = 'COMPLETED'
                """
            ).fetchone()[0],
            "not_needed": connection.execute(
                """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE translation_status = 'NOT_NEEDED'
                """
            ).fetchone()[0],
            "korean_titles": connection.execute(
                """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE translated_title_ko IS NOT NULL
                """
            ).fetchone()[0],
            "english": connection.execute(
                """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE source_language = 'en'
                """
            ).fetchone()[0],
            "korean": connection.execute(
                """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE source_language = 'ko'
                """
            ).fetchone()[0],
            "remaining": connection.execute(
                """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE translation_status
                    = 'NOT_REQUESTED'
                """
            ).fetchone()[0],
        }

        titles_after = tuple(
            connection.execute(
                """
                SELECT id, title
                FROM analyst_references
                ORDER BY id
                """
            ).fetchall()
        )

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]

        passed = (
            counts["references"] == EXPECTED_REFERENCE_COUNT
            and counts["completed"] == EXPECTED_ENGLISH_COUNT
            and counts["not_needed"] == EXPECTED_KOREAN_COUNT
            and counts["korean_titles"] == EXPECTED_ENGLISH_COUNT
            and counts["english"] == EXPECTED_ENGLISH_COUNT
            and counts["korean"] == EXPECTED_KOREAN_COUNT
            and counts["remaining"] == 0
            and titles_after == expected_titles
            and integrity == "ok"
        )

        if not passed:
            raise RuntimeError(
                "Post-write validation failed. The transaction will be rolled back."
            )

        connection.commit()

        return {
            **counts,
            "integrity": integrity,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    database_path = Path(args.database_path).resolve()

    if not database_path.exists():
        raise RuntimeError(f"Validation database not found: {database_path}")

    if database_path.name != EXPECTED_DATABASE_NAME:
        raise RuntimeError("Only the 0014 validation database may be modified.")

    (
        revision,
        rows,
        existing_state,
        integrity,
    ) = read_state(database_path)

    if revision != EXPECTED_REVISION:
        raise RuntimeError(f"Unexpected revision: {revision}")

    if len(rows) != EXPECTED_REFERENCE_COUNT:
        raise RuntimeError(f"Unexpected reference count: {len(rows)}")

    if existing_state != 0:
        raise RuntimeError("Translation state already exists. No changes were written.")

    if integrity != "ok":
        raise RuntimeError("Database integrity check failed.")

    actions = create_actions(rows)

    english_count = sum(action["source_language"] == "en" for action in actions)
    korean_count = sum(action["source_language"] == "ko" for action in actions)

    if english_count != EXPECTED_ENGLISH_COUNT or korean_count != EXPECTED_KOREAN_COUNT:
        raise RuntimeError("Unexpected translation action counts.")

    print("=" * 78)
    print("REFERENCE VALIDATION TRANSLATION APPLY")
    print("=" * 78)
    print("Database:", database_path)
    print("Revision:", revision)
    print("References:", len(rows))
    print("Confirm:", args.confirm)
    print()

    for index, action in enumerate(
        actions,
        start=1,
    ):
        print(f"{index}.")
        print(
            "   Original:",
            action["original_title"],
        )
        print(
            "   Language:",
            action["source_language"],
        )
        print(
            "   Status:",
            action["translation_status"],
        )
        print(
            "   Korean title:",
            (action["translated_title_ko"] or "<ORIGINAL KOREAN>"),
        )
        print()

    if not args.confirm:
        print("Database writes: 0")
        print("Result: CONFIRMATION REQUIRED")
        return 0

    expected_titles = tuple(
        sorted(
            (
                str(row["id"]),
                str(row["title"]),
            )
            for row in rows
        )
    )

    backup_path = create_backup(database_path)

    result = apply_actions(
        database_path,
        actions,
        expected_titles,
    )

    print("=" * 78)
    print("APPLY RESULT")
    print("=" * 78)
    print("Backup:", backup_path)
    print("References:", result["references"])
    print("Completed:", result["completed"])
    print("Not needed:", result["not_needed"])
    print(
        "Korean titles:",
        result["korean_titles"],
    )
    print("English source:", result["english"])
    print("Korean source:", result["korean"])
    print(
        "Not requested remaining:",
        result["remaining"],
    )
    print("Original titles unchanged: True")
    print("Integrity:", result["integrity"])
    print("Database writes: 4")
    print("Result: VALIDATION TRANSLATION APPLY PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
