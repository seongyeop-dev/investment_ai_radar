from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.providers.reference_index import (
    BerkshireLetterIndexAdapter,
    OaktreeMemoIndexAdapter,
)

BERKSHIRE_FIXTURE = """
<html>
  <body>
    <a href="/letters/2024ltr.pdf">2024</a>
    <a href="/letters/2023ltr.pdf">
      2023 Shareholder Letter
    </a>
    <a href="/letters/2024ltr.pdf">2024</a>
    <a href="/annual-reports/2024ar.pdf">
      Annual Report
    </a>
    <a href="https://example.test/news">
      External news
    </a>
  </body>
</html>
"""


OAKTREE_FIXTURE = """
<html>
  <body>
    <article class="insight-card">
      <time datetime="2026-04-09">
        Apr 9, 2026
      </time>
      <a href="/insights/memo/private-credit">
        What's Going on in Private Credit?
      </a>
      <p class="summary">
        A public memo about private credit markets.
      </p>
    </article>

    <article class="insight-card">
      <time>Feb 26, 2026</time>
      <a href="/insights/memo/ai-hurtles-ahead">
        AI Hurtles Ahead
      </a>
    </article>

    <article class="insight-card">
      <time datetime="2026-04-09">
        Apr 9, 2026
      </time>
      <a href="/insights/memo-podcast/private-credit">
        What's Going on in Private Credit? Audio
      </a>
    </article>

    <article class="insight-card">
      <time datetime="2026-07-21">
        Jul 21, 2026
      </time>
      <a href="/insights/press/external-interview">
        External Interview
      </a>
    </article>
  </body>
</html>
"""


def test_berkshire_adapter_discovers_letter_pdfs_without_guessing_date() -> None:
    candidates = BerkshireLetterIndexAdapter.parse(
        BERKSHIRE_FIXTURE,
        base_url=("https://www.berkshirehathaway.com/letters/letters.html"),
        author_name="Warren Buffett",
    )

    assert len(candidates) == 2

    newest = candidates[0]

    assert newest.provider_item_id == ("2024ltr.pdf")
    assert newest.title == ("Berkshire Hathaway 2024 Shareholder Letter")
    assert newest.canonical_url == ("https://www.berkshirehathaway.com/letters/2024ltr.pdf")
    assert newest.author_name == ("Warren Buffett")
    assert newest.published_at is None

    with pytest.raises(
        ValueError,
        match="published_at must be verified",
    ):
        newest.to_feed_item()


def test_berkshire_adapter_can_represent_current_author_index() -> None:
    fixture = """
    <html>
      <body>
        <a href="/letters/2025ltr.pdf">
          2025
        </a>
      </body>
    </html>
    """

    candidates = BerkshireLetterIndexAdapter.parse(
        fixture,
        base_url=("https://www.berkshirehathaway.com/letters/gealetters.html"),
        author_name="Greg Abel",
    )

    assert len(candidates) == 1
    assert candidates[0].provider_item_id == ("2025ltr.pdf")
    assert candidates[0].author_name == ("Greg Abel")
    assert candidates[0].published_at is None


def test_oaktree_adapter_discovers_memos_with_verified_dates() -> None:
    candidates = OaktreeMemoIndexAdapter.parse(
        OAKTREE_FIXTURE,
        base_url=("https://www.oaktreecapital.com/insights"),
    )

    assert len(candidates) == 2

    newest = candidates[0]

    assert newest.provider_item_id == ("oaktree:private-credit")
    assert newest.title == ("What's Going on in Private Credit?")
    assert newest.canonical_url == (
        "https://www.oaktreecapital.com/insights/memo/private-credit"
    )
    assert newest.author_name == ("Howard Marks")
    assert newest.published_at == datetime(
        2026,
        4,
        9,
        tzinfo=UTC,
    )
    assert newest.public_abstract == ("A public memo about private credit markets.")

    feed_item = newest.to_feed_item()

    assert feed_item.provider_item_id == (newest.provider_item_id)
    assert feed_item.published_at == (newest.published_at)


def test_oaktree_adapter_excludes_audio_and_press_links() -> None:
    candidates = OaktreeMemoIndexAdapter.parse(
        OAKTREE_FIXTURE,
        base_url=("https://www.oaktreecapital.com/insights"),
    )

    urls = {candidate.canonical_url for candidate in candidates}

    assert all("/insights/memo/" in url for url in urls)
    assert all("/memo-podcast/" not in url for url in urls)
    assert all("/press/" not in url for url in urls)


OAKTREE_EMBEDDED_JSON_FIXTURE = """
<html>
  <body>
    <div
      data-items="[
        {&quot;InsightId&quot;:&quot;1&quot;,
         &quot;Title&quot;:&quot;AI Hurtles Ahead&quot;,
         &quot;IsoDate&quot;:&quot;2026-02-26T08:00:00.0000000Z&quot;,
         &quot;FormattedDate&quot;:&quot;Feb 26, 2026&quot;,
         &quot;MoreLink&quot;:&quot;/insights/memo/ai-hurtles-ahead&quot;,
         &quot;CategoryText&quot;:&quot;memos&quot;,
         &quot;ReadMoreText&quot;:&quot;Read&quot;,
         &quot;CssClassType&quot;:&quot;article&quot;},
        {&quot;InsightId&quot;:&quot;2&quot;,
         &quot;Title&quot;:&quot;AI Hurtles Ahead (Audio)&quot;,
         &quot;IsoDate&quot;:&quot;2026-02-26T08:00:00.0000000Z&quot;,
         &quot;MoreLink&quot;:&quot;/insights/memo-podcast/ai-hurtles-ahead&quot;,
         &quot;CategoryText&quot;:&quot;memos&quot;,
         &quot;ReadMoreText&quot;:&quot;Listen&quot;,
         &quot;CssClassType&quot;:&quot;audio&quot;}
      ]"
    ></div>
  </body>
</html>
"""


def test_oaktree_adapter_parses_entity_encoded_json() -> None:
    candidates = OaktreeMemoIndexAdapter.parse(
        OAKTREE_EMBEDDED_JSON_FIXTURE,
        base_url=("https://www.oaktreecapital.com/insights"),
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.provider_item_id == ("oaktree:ai-hurtles-ahead")
    assert candidate.title == ("AI Hurtles Ahead")
    assert candidate.author_name == ("Howard Marks")
    assert candidate.canonical_url == (
        "https://www.oaktreecapital.com/insights/memo/ai-hurtles-ahead"
    )
    assert candidate.published_at == datetime(
        2026,
        2,
        26,
        8,
        0,
        tzinfo=UTC,
    )
