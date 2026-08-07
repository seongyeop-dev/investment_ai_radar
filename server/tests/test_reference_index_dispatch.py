from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.services import (
    reference_index_dispatch,
)
from app.services.reference_index_dispatch import (
    ReferenceIndexDispatchError,
    fetch_reference_index_candidates,
)


@dataclass(
    frozen=True,
    slots=True,
)
class StubResponse:
    html: str
    final_url: str
    status_code: int = 200


class StubFetcher:
    def __init__(
        self,
        html: str,
    ) -> None:
        self.html = html
        self.requests: list[str] = []

    def fetch_html(
        self,
        url: str,
    ) -> StubResponse:
        self.requests.append(url)

        return StubResponse(
            html=self.html,
            final_url=url,
        )


def _source(
    *,
    domain: str,
    feed_url: str,
    official: bool = True,
    enabled: bool = True,
    provider_type: str = "REFERENCE_INDEX",
) -> SourceRecord:
    return SourceRecord(
        name=f"Fixture {domain}",
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain=domain,
        official=official,
        enabled=enabled,
        feed_url=feed_url,
        provider_type=provider_type,
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=20,
        max_items=50,
        original_source_name=None,
    )


def test_berkshire_buffett_dispatch_fetches_only_index_html() -> None:
    fetcher = StubFetcher(
        """
        <html>
          <body>
            <a href="/letters/2024ltr.pdf">
              2024
            </a>
            <a href="/annual-reports/2024ar.pdf">
              Annual Report
            </a>
          </body>
        </html>
        """
    )

    index_url = "https://www.berkshirehathaway.com/letters/letters.html"

    result = fetch_reference_index_candidates(
        _source(
            domain="berkshirehathaway.com",
            feed_url=index_url,
        ),
        fetcher=fetcher,
    )

    assert fetcher.requests == [index_url]
    assert result.request_count == 1
    assert result.external_documents_downloaded == 0
    assert len(result.candidates) == 1

    candidate = result.candidates[0]

    assert candidate.provider_item_id == ("2024ltr.pdf")
    assert candidate.author_name == ("Warren Buffett")
    assert candidate.published_at is None
    assert candidate.canonical_url.endswith("/letters/2024ltr.pdf")

    assert candidate.canonical_url not in (fetcher.requests)


def test_berkshire_abel_index_assigns_greg_abel() -> None:
    fetcher = StubFetcher(
        """
        <a href="/letters/2025ltr.pdf">
          2025
        </a>
        """
    )

    index_url = "https://www.berkshirehathaway.com/letters/gealetters.html"

    result = fetch_reference_index_candidates(
        _source(
            domain=("www.berkshirehathaway.com"),
            feed_url=index_url,
        ),
        fetcher=fetcher,
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].author_name == "Greg Abel"
    assert result.candidates[0].published_at is None


def test_oaktree_dispatch_preserves_existing_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetcher = StubFetcher("<html>fixture</html>")

    index_url = "https://www.oaktreecapital.com/insights"

    expected = ReferenceIndexCandidate(
        provider_item_id="oaktree:fixture",
        title="Fixture memo",
        canonical_url=("https://www.oaktreecapital.com/insights/memo/fixture"),
        published_at=datetime(
            2026,
            8,
            1,
            tzinfo=UTC,
        ),
        author_name="Howard Marks",
    )

    def fake_parse(
        content: str | bytes,
        *,
        base_url: str,
    ) -> tuple[
        ReferenceIndexCandidate,
        ...,
    ]:
        assert content == "<html>fixture</html>"
        assert base_url == index_url
        return (expected,)

    monkeypatch.setattr(
        reference_index_dispatch.OaktreeMemoIndexAdapter,
        "parse",
        staticmethod(fake_parse),
    )

    result = fetch_reference_index_candidates(
        _source(
            domain="oaktreecapital.com",
            feed_url=index_url,
        ),
        fetcher=fetcher,
    )

    assert result.candidates == (expected,)
    assert fetcher.requests == [index_url]


@pytest.mark.parametrize(
    ("official", "enabled", "provider_type"),
    [
        (False, True, "REFERENCE_INDEX"),
        (True, False, "REFERENCE_INDEX"),
        (True, True, "RSS"),
    ],
)
def test_dispatch_blocks_invalid_source_before_request(
    official: bool,
    enabled: bool,
    provider_type: str,
) -> None:
    fetcher = StubFetcher("<html></html>")

    with pytest.raises(ReferenceIndexDispatchError):
        fetch_reference_index_candidates(
            _source(
                domain="berkshirehathaway.com",
                feed_url=("https://www.berkshirehathaway.com/letters/letters.html"),
                official=official,
                enabled=enabled,
                provider_type=provider_type,
            ),
            fetcher=fetcher,
        )

    assert fetcher.requests == []


def test_dispatch_rejects_unsupported_domain() -> None:
    fetcher = StubFetcher("<html></html>")

    with pytest.raises(
        ReferenceIndexDispatchError,
        match="Unsupported official",
    ):
        fetch_reference_index_candidates(
            _source(
                domain="example.com",
                feed_url=("https://example.com/index"),
            ),
            fetcher=fetcher,
        )

    assert fetcher.requests == []


def test_dispatch_rejects_berkshire_pdf_as_index() -> None:
    fetcher = StubFetcher("<html></html>")

    with pytest.raises(
        ReferenceIndexDispatchError,
        match="Unsupported Berkshire",
    ):
        fetch_reference_index_candidates(
            _source(
                domain="berkshirehathaway.com",
                feed_url=("https://www.berkshirehathaway.com/letters/2024ltr.pdf"),
            ),
            fetcher=fetcher,
        )

    assert fetcher.requests == []
