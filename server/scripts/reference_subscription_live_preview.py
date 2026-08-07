from __future__ import annotations

import os
from collections.abc import Iterable

from sqlalchemy import select

from app.database import Database
from app.models.database import SourceRecord
from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)
from app.providers.reference_http import (
    ReferenceHttpProvider,
)
from app.providers.reference_index import (
    BerkshireLetterIndexAdapter,
    OaktreeMemoIndexAdapter,
    ReferenceIndexCandidate,
)
from app.services.reference_discovery import (
    ReferenceDiscoveryPreview,
    ReferenceDiscoveryState,
    preview_reference_candidates,
)


def _candidates_for_source(
    source: SourceRecord,
) -> tuple[ReferenceIndexCandidate, ...]:
    domain = source.domain.casefold()

    if "oaktreecapital.com" in domain:
        provider = ReferenceHttpProvider(
            allowed_hosts={
                "oaktreecapital.com",
                "www.oaktreecapital.com",
            },
            timeout_seconds=float(source.timeout_seconds),
        )

        response = provider.fetch_html(
            source.feed_url or ("https://www.oaktreecapital.com/insights")
        )

        return OaktreeMemoIndexAdapter.parse(
            response.html,
            base_url=response.final_url,
        )

    if "berkshirehathaway.com" in domain:
        provider = ReferenceHttpProvider(
            allowed_hosts={
                "berkshirehathaway.com",
                "www.berkshirehathaway.com",
            },
            timeout_seconds=float(source.timeout_seconds),
        )

        buffett_response = provider.fetch_html(
            "https://www.berkshirehathaway.com/letters/letters.html"
        )

        abel_response = provider.fetch_html(
            "https://www.berkshirehathaway.com/letters/gealetters.html"
        )

        buffett = BerkshireLetterIndexAdapter.parse(
            buffett_response.html,
            base_url=buffett_response.final_url,
            author_name="Warren Buffett",
        )

        abel = BerkshireLetterIndexAdapter.parse(
            abel_response.html,
            base_url=abel_response.final_url,
            author_name="Greg Abel",
        )

        unique = {
            candidate.provider_item_id: candidate
            for candidate in (
                *buffett,
                *abel,
            )
        }

        return tuple(unique.values())

    return ()


def _print_items(
    items: Iterable[ReferenceDiscoveryPreview],
    *,
    maximum: int = 10,
) -> None:
    values = list(items)

    for index, item in enumerate(
        values[:maximum],
        start=1,
    ):
        print()
        print(f"{index}. {item.title}")
        print("   State:", item.state.value)
        print("   Matched:", item.matched)
        print("   Ingest ready:", item.ingest_ready)
        print("   Author:", item.author_name)
        print("   Published:", item.published_at)
        print("   URL:", item.canonical_url)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is required for reference subscription live preview")

    database = Database(database_url)

    with database.session_scope() as session:
        subscriptions = list(
            session.scalars(
                select(ReferenceSubscriptionRecord)
                .where(ReferenceSubscriptionRecord.enabled.is_(True))
                .order_by(ReferenceSubscriptionRecord.display_name.asc())
            )
        )

        print("=" * 72)
        print("REFERENCE SUBSCRIPTION LIVE PREVIEW")
        print("=" * 72)
        print(
            "Enabled subscriptions:",
            len(subscriptions),
        )
        print("Database writes: 0")

        total_candidates = 0
        total_matched = 0
        total_ready = 0
        total_date_unverified = 0

        for subscription in subscriptions:
            source = session.get(
                SourceRecord,
                subscription.source_id,
            )

            if source is None:
                print()
                print(
                    "SOURCE MISSING:",
                    subscription.display_name,
                )
                continue

            candidates = _candidates_for_source(source)

            previews = preview_reference_candidates(
                subscription=subscription,
                candidates=candidates,
            )

            matched = [item for item in previews if item.matched]

            ready = [item for item in matched if item.state is ReferenceDiscoveryState.READY]

            date_unverified = [
                item
                for item in matched
                if item.state is ReferenceDiscoveryState.DATE_UNVERIFIED
            ]

            total_candidates += len(previews)
            total_matched += len(matched)
            total_ready += len(ready)
            total_date_unverified += len(date_unverified)

            print()
            print("=" * 72)
            print(subscription.display_name)
            print("=" * 72)
            print("Source:", source.name)
            print(
                "Match mode:",
                subscription.match_mode.value,
            )
            print("Candidates:", len(previews))
            print("Matched:", len(matched))
            print("Ingest ready:", len(ready))
            print(
                "Date unverified:",
                len(date_unverified),
            )

            _print_items(matched)

        print()
        print("=" * 72)
        print("LIVE PREVIEW SUMMARY")
        print("=" * 72)
        print(
            "Total subscriptions:",
            len(subscriptions),
        )
        print(
            "Total candidates:",
            total_candidates,
        )
        print("Total matched:", total_matched)
        print("Ingest ready:", total_ready)
        print(
            "Date unverified:",
            total_date_unverified,
        )
        print("Database writes: 0")
        print("Result: REFERENCE SUBSCRIPTION LIVE PREVIEW PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
