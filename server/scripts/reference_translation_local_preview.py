from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from app.providers.reference_translation_local import (
    DEFAULT_MODEL_NAME,
    LocalMarianTranslationProvider,
)
from app.services.reference_translation import (
    plan_reference_translation,
)

EXPECTED_DATABASE_NAME = "investment_ai_radar_0014_validation.db"
EXPECTED_REVISION = "20260730_0014"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview English-to-Korean reference title translations without database writes."
        )
    )
    parser.add_argument(
        "--database-path",
        default=(".local/data/" + EXPECTED_DATABASE_NAME),
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
    )

    return parser.parse_args()


def contains_hangul(
    value: str,
) -> bool:
    return any("\uac00" <= character <= "\ud7a3" for character in value)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    database_path = Path(args.database_path).resolve()

    if not database_path.exists():
        raise RuntimeError(f"Validation database was not found: {database_path}")

    if database_path.name != EXPECTED_DATABASE_NAME:
        raise RuntimeError("Only the 0014 validation database may be used")

    connection = sqlite3.connect(
        (f"file:{database_path.as_posix()}?mode=ro"),
        uri=True,
    )

    try:
        revision = connection.execute(
            """
            SELECT version_num
            FROM alembic_version
            """
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT
                id,
                title,
                public_abstract,
                ingest_mode,
                published_at
            FROM analyst_references
            WHERE ingest_mode = 'AUTOMATIC'
            ORDER BY
                published_at DESC,
                created_at DESC,
                id ASC
            """
        ).fetchall()

        reference_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM analyst_references
            """
        ).fetchone()[0]

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()

    if revision != EXPECTED_REVISION:
        raise RuntimeError(f"Unexpected database revision: {revision}")

    planned_rows = []

    for row in rows:
        plan = plan_reference_translation(
            title=row[1],
            public_abstract=row[2],
        )

        if plan.source_language == "en" and plan.title_requires_translation:
            planned_rows.append(row)

    cache_dir = Path(".local/models/huggingface").resolve()

    provider = LocalMarianTranslationProvider(
        model_name=args.model_name,
        cache_dir=cache_dir,
        local_files_only=(args.local_files_only),
    )

    print("=" * 72)
    print("LOCAL REFERENCE TRANSLATION PREVIEW")
    print("READ ONLY / DATABASE WRITES: 0")
    print("=" * 72)
    print("Database:", database_path)
    print("Revision:", revision)
    print("Reference count:", reference_count)
    print("English titles:", len(planned_rows))
    print("Model:", provider.model_name)
    print("Model cache:", cache_dir)
    print(
        "Local files only:",
        provider.local_files_only,
    )
    print()

    successful = 0

    for index, row in enumerate(
        planned_rows,
        start=1,
    ):
        (
            reference_id,
            title,
            public_abstract,
            ingest_mode,
            published_at,
        ) = row

        translated_title = provider.translate(
            title,
            source_language="en",
            target_language="ko",
        )

        translated_abstract = None

        if public_abstract and public_abstract.strip():
            translated_abstract = provider.translate(
                public_abstract,
                source_language="en",
                target_language="ko",
            )

        valid_title = bool(translated_title) and contains_hangul(translated_title)

        if valid_title:
            successful += 1

        print(f"{index}. ID: {reference_id}")
        print("   Ingest mode:", ingest_mode)
        print("   Published:", published_at)
        print("   Original title:", title)
        print(
            "   Korean preview:",
            translated_title,
        )

        if translated_abstract is not None:
            print(
                "   Korean abstract preview:",
                translated_abstract,
            )

        print(
            "   Hangul result:",
            valid_title,
        )
        print()

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print("Planned:", len(planned_rows))
    print("Translated:", successful)
    print("Database writes: 0")
    print("Reference documents downloaded: 0")
    print("Integrity:", integrity)

    passed = (
        len(planned_rows) == 3
        and successful == 3
        and reference_count == 4
        and integrity == "ok"
    )

    print(
        "Result:",
        ("LOCAL TRANSLATION PREVIEW PASS" if passed else "LOCAL TRANSLATION REVIEW REQUIRED"),
    )

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
