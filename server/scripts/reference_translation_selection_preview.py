from __future__ import annotations

import sqlite3
import sys
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


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8",
        )

    database_path = Path(".local/data/" + EXPECTED_DATABASE_NAME).resolve()

    if not database_path.exists():
        raise RuntimeError(f"Validation database not found: {database_path}")

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
            ORDER BY
                published_at DESC,
                created_at DESC,
                id ASC
            """
        ).fetchall()

        stored_translation_count = connection.execute(
            """
                SELECT COUNT(*)
                FROM analyst_references
                WHERE
                    translated_title_ko
                    IS NOT NULL
                    OR translation_status
                    != 'NOT_REQUESTED'
                """
        ).fetchone()[0]

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()

    if revision != EXPECTED_REVISION:
        raise RuntimeError(f"Unexpected revision: {revision}")

    provider = LocalNllbTranslationProvider(
        cache_dir=Path(".local/models/huggingface").resolve(),
        local_files_only=True,
    )

    english_rows = []

    for row in rows:
        plan = plan_reference_translation(
            title=row[1],
            public_abstract=row[2],
        )

        if plan.source_language == "en":
            english_rows.append(row)

    print("=" * 78)
    print("REFERENCE TITLE AUTO SELECTION PREVIEW")
    print("READ ONLY / DATABASE WRITES: 0")
    print("=" * 78)
    print("Database:", database_path)
    print("Revision:", revision)
    print("English references:", len(english_rows))
    print("Stored translations:", stored_translation_count)
    print()

    selected_count = 0
    review_count = 0

    for index, row in enumerate(
        english_rows,
        start=1,
    ):
        (
            reference_id,
            title,
            public_abstract,
            ingest_mode,
            published_at,
        ) = row

        del public_abstract

        selection = select_title_translation(
            source_title=title,
            provider=provider,
        )

        print("=" * 78)
        print(f"{index}. {title}")
        print("=" * 78)
        print("ID:", reference_id)
        print("Ingest mode:", ingest_mode)
        print("Published:", published_at)
        print()

        for rank, evaluation in enumerate(
            selection.evaluations,
            start=1,
        ):
            print(
                f"Candidate {rank}:",
                evaluation.candidate_name,
            )
            print(
                "Input:",
                evaluation.candidate_input,
            )
            print(
                "Translation:",
                evaluation.translation,
            )
            print(
                "Score:",
                evaluation.score,
            )
            print(
                "Approved:",
                evaluation.approved,
            )
            print(
                "Reasons:",
                list(evaluation.reasons),
            )
            print("-" * 78)

        if selection.selected is None:
            review_count += 1
            print("SELECTED: NONE")
            print("STATUS: REVIEW_REQUIRED")
        else:
            selected_count += 1
            print(
                "SELECTED CANDIDATE:",
                selection.selected.candidate_name,
            )
            print(
                "SELECTED TRANSLATION:",
                selection.selected.translation,
            )
            print("STATUS: AUTO_APPROVED")

        print()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print("English references:", len(english_rows))
    print("Auto approved:", selected_count)
    print("Review required:", review_count)
    print(
        "Stored translations before:",
        stored_translation_count,
    )
    print("Database writes: 0")
    print("Integrity:", integrity)

    passed = (
        len(english_rows) == 3
        and selected_count == 3
        and review_count == 0
        and stored_translation_count == 0
        and integrity == "ok"
    )

    print(
        "Result:",
        (
            "TITLE AUTO SELECTION PREVIEW PASS"
            if passed
            else "TITLE AUTO SELECTION REVIEW REQUIRED"
        ),
    )

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
