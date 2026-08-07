from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from app.models.database import (  # noqa: E402
    SourceGrade,
    SourceRecord,
)
from app.providers.reference_http import (  # noqa: E402
    ReferenceHttpError,
)
from app.services.reference_index_dispatch import (  # noqa: E402
    ReferenceIndexDispatchError,
    ReferenceIndexDispatchResult,
    fetch_reference_index_candidates,
)


@dataclass(
    frozen=True,
    slots=True,
)
class LiveReferenceSource:
    label: str
    source: SourceRecord


def _source(
    *,
    name: str,
    domain: str,
    feed_url: str,
) -> SourceRecord:
    return SourceRecord(
        name=name,
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain=domain,
        official=True,
        enabled=True,
        feed_url=feed_url,
        provider_type="REFERENCE_INDEX",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=20,
        max_items=50,
        original_source_name=None,
    )


LIVE_SOURCES = (
    LiveReferenceSource(
        label=("Berkshire Warren Buffett letter candidates"),
        source=_source(
            name=("Berkshire Hathaway Warren Buffett Letters"),
            domain="berkshirehathaway.com",
            feed_url=("https://www.berkshirehathaway.com/letters/letters.html"),
        ),
    ),
    LiveReferenceSource(
        label=("Berkshire Greg Abel letter candidates"),
        source=_source(
            name=("Berkshire Hathaway Greg Abel Letters"),
            domain="berkshirehathaway.com",
            feed_url=("https://www.berkshirehathaway.com/letters/gealetters.html"),
        ),
    ),
    LiveReferenceSource(
        label="Oaktree memo candidates",
        source=_source(
            name="Oaktree Howard Marks Memos",
            domain="oaktreecapital.com",
            feed_url=("https://www.oaktreecapital.com/insights"),
        ),
    ),
)


def _run_source(
    item: LiveReferenceSource,
) -> ReferenceIndexDispatchResult:
    print()
    print("=" * 72)
    print(item.label)
    print("=" * 72)

    result = fetch_reference_index_candidates(item.source)

    print(
        "Requested URL:",
        result.requested_urls[0],
    )
    print(
        "Final URL:",
        result.final_urls[0],
    )
    print(
        "HTTP status:",
        result.status_codes[0],
    )
    print(
        "Index requests:",
        result.request_count,
    )
    print(
        "External documents downloaded:",
        result.external_documents_downloaded,
    )
    print(
        "Candidate count:",
        len(result.candidates),
    )

    for candidate in result.candidates:
        published = (
            candidate.published_at.isoformat()
            if candidate.published_at is not None
            else "UNVERIFIED"
        )

        print("-" * 72)
        print(
            "Provider item ID:",
            candidate.provider_item_id,
        )
        print("Title:", candidate.title)
        print(
            "Author:",
            candidate.author_name,
        )
        print("Published:", published)
        print(
            "Canonical URL:",
            candidate.canonical_url,
        )

    return result


def main() -> int:
    results: list[
        tuple[
            LiveReferenceSource,
            ReferenceIndexDispatchResult,
        ]
    ] = []

    try:
        for item in LIVE_SOURCES:
            results.append(
                (
                    item,
                    _run_source(item),
                )
            )

    except (
        ReferenceHttpError,
        ReferenceIndexDispatchError,
    ) as exc:
        print()
        print("LIVE DRY-RUN FAILED:", exc)
        print("Database writes: 0")
        print("External documents downloaded: 0")
        return 1

    print()
    print("=" * 72)
    print("LIVE DRY-RUN SUMMARY")
    print("=" * 72)

    total_requests = 0
    total_documents = 0
    missing_candidates = False

    for item, result in results:
        candidate_count = len(result.candidates)

        print(
            f"{item.label}:",
            candidate_count,
        )

        total_requests += result.request_count
        total_documents += result.external_documents_downloaded

        if candidate_count == 0:
            missing_candidates = True

    print("Index requests:", total_requests)
    print("Database writes: 0")
    print(
        "External documents downloaded:",
        total_documents,
    )

    if total_documents != 0:
        print("Result: EXTERNAL DOCUMENT DOWNLOAD DETECTED")
        return 3

    if missing_candidates:
        print("Result: ADAPTER REVIEW REQUIRED")
        return 2

    print("Result: LIVE REFERENCE DISCOVERY PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
