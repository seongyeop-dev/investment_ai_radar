from __future__ import annotations

import sqlite3
from pathlib import Path

from app.services.reference_translation import (
    plan_reference_translation,
)


def main() -> int:
    path = Path(".local/data/investment_ai_radar_0014_validation.db").resolve()

    if not path.exists():
        raise SystemExit(f"Validation database was not found: {path}")

    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro",
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
                ingest_mode,
                title,
                public_abstract,
                source_language,
                translation_status
            FROM analyst_references
            ORDER BY
                published_at DESC,
                created_at DESC,
                id ASC
            """
        ).fetchall()

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()

    print("=" * 72)
    print("REFERENCE TRANSLATION PLAN PREVIEW")
    print("READ ONLY / DATABASE WRITES: 0")
    print("=" * 72)
    print("Database:", path)
    print("Revision:", revision)
    print("Reference count:", len(rows))
    print()

    counts: dict[str, int] = {
        "en": 0,
        "ko": 0,
        "und": 0,
    }

    for index, row in enumerate(
        rows,
        start=1,
    ):
        (
            reference_id,
            ingest_mode,
            title,
            public_abstract,
            stored_language,
            stored_status,
        ) = row

        plan = plan_reference_translation(
            title=title,
            public_abstract=public_abstract,
        )

        counts[plan.source_language] += 1

        print(f"{index}. {title}")
        print("   ID:", reference_id)
        print("   Ingest mode:", ingest_mode)
        print(
            "   Stored:",
            stored_language,
            "/",
            stored_status,
        )
        print(
            "   Planned:",
            plan.source_language,
            "/",
            plan.translation_status.value,
        )
        print(
            "   Title translation:",
            plan.title_requires_translation,
        )
        print(
            "   Abstract translation:",
            plan.abstract_requires_translation,
        )
        print("   Reason:", plan.reason)
        print()

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print("English:", counts["en"])
    print("Korean:", counts["ko"])
    print("Undetermined:", counts["und"])
    print("Database writes: 0")
    print("Integrity:", integrity)

    expected = (
        revision == "20260730_0014"
        and len(rows) == 4
        and counts["en"] == 3
        and counts["ko"] == 1
        and counts["und"] == 0
        and integrity == "ok"
    )

    print(
        "Result:",
        ("TRANSLATION PLAN PREVIEW PASS" if expected else "TRANSLATION PLAN REVIEW REQUIRED"),
    )

    return 0 if expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
