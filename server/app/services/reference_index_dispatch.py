from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from app.models.database import SourceRecord
from app.providers.reference_http import (
    ReferenceHttpProvider,
)
from app.providers.reference_index import (
    BerkshireLetterIndexAdapter,
    OaktreeMemoIndexAdapter,
    ReferenceIndexCandidate,
)

OAKTREE_HOSTS = frozenset(
    {
        "oaktreecapital.com",
        "www.oaktreecapital.com",
    }
)

BERKSHIRE_HOSTS = frozenset(
    {
        "berkshirehathaway.com",
        "www.berkshirehathaway.com",
    }
)

OAKTREE_DEFAULT_INDEX_URL = "https://www.oaktreecapital.com/insights"

BERKSHIRE_BUFFETT_INDEX_URL = "https://www.berkshirehathaway.com/letters/letters.html"

BERKSHIRE_ABEL_INDEX_URL = "https://www.berkshirehathaway.com/letters/gealetters.html"


class ReferenceIndexDispatchError(RuntimeError):
    pass


class ReferenceHtmlResponse(Protocol):
    html: str | bytes
    final_url: str
    status_code: int


class ReferenceHtmlFetcher(Protocol):
    def fetch_html(
        self,
        url: str,
    ) -> ReferenceHtmlResponse: ...


@dataclass(
    frozen=True,
    slots=True,
)
class ReferenceIndexDispatchResult:
    candidates: tuple[
        ReferenceIndexCandidate,
        ...,
    ]
    requested_urls: tuple[str, ...]
    final_urls: tuple[str, ...]
    status_codes: tuple[int, ...]
    request_count: int
    external_documents_downloaded: int = 0


def _normalized_host(
    value: str | None,
) -> str:
    return (value or "").strip().casefold().rstrip(".")


def _validated_index_url(
    value: str,
    *,
    allowed_hosts: frozenset[str],
) -> str:
    parsed = urlsplit(value)

    if parsed.scheme.casefold() != "https":
        raise ReferenceIndexDispatchError("Reference index URL must use HTTPS")

    host = _normalized_host(parsed.hostname)

    if host not in allowed_hosts:
        raise ReferenceIndexDispatchError("Reference index URL host is not allowed")

    return value


def _validate_source(
    source: SourceRecord,
) -> None:
    if not source.official:
        raise ReferenceIndexDispatchError("Reference source must be official")

    if not source.enabled:
        raise ReferenceIndexDispatchError("Reference source must be enabled")

    provider_type = str(source.provider_type or "").strip().casefold()

    if provider_type != "reference_index":
        raise ReferenceIndexDispatchError(
            "Reference source provider_type must be REFERENCE_INDEX"
        )


def _default_fetcher(
    source: SourceRecord,
    *,
    allowed_hosts: frozenset[str],
) -> ReferenceHttpProvider:
    return ReferenceHttpProvider(
        allowed_hosts=set(allowed_hosts),
        timeout_seconds=float(source.timeout_seconds or 20),
    )


def _berkshire_author(
    index_url: str,
) -> str:
    path = urlsplit(index_url).path.rstrip("/").casefold()

    if path == "/letters/letters.html":
        return "Warren Buffett"

    if path == "/letters/gealetters.html":
        return "Greg Abel"

    raise ReferenceIndexDispatchError("Unsupported Berkshire letter index path")


def fetch_reference_index_candidates(
    source: SourceRecord,
    *,
    fetcher: ReferenceHtmlFetcher | None = None,
) -> ReferenceIndexDispatchResult:
    _validate_source(source)

    domain = _normalized_host(source.domain)

    if domain in OAKTREE_HOSTS:
        allowed_hosts = OAKTREE_HOSTS
        index_url = _validated_index_url(
            source.feed_url or OAKTREE_DEFAULT_INDEX_URL,
            allowed_hosts=allowed_hosts,
        )

        active_fetcher = fetcher or _default_fetcher(
            source,
            allowed_hosts=allowed_hosts,
        )

        response = active_fetcher.fetch_html(index_url)

        candidates = OaktreeMemoIndexAdapter.parse(
            response.html,
            base_url=response.final_url,
        )

    elif domain in BERKSHIRE_HOSTS:
        allowed_hosts = BERKSHIRE_HOSTS
        index_url = _validated_index_url(
            source.feed_url or BERKSHIRE_BUFFETT_INDEX_URL,
            allowed_hosts=allowed_hosts,
        )

        author_name = _berkshire_author(index_url)

        active_fetcher = fetcher or _default_fetcher(
            source,
            allowed_hosts=allowed_hosts,
        )

        response = active_fetcher.fetch_html(index_url)

        candidates = BerkshireLetterIndexAdapter.parse(
            response.html,
            base_url=response.final_url,
            author_name=author_name,
        )

    else:
        raise ReferenceIndexDispatchError("Unsupported official reference domain")

    return ReferenceIndexDispatchResult(
        candidates=candidates,
        requested_urls=(index_url,),
        final_urls=(response.final_url,),
        status_codes=(int(response.status_code),),
        request_count=1,
        external_documents_downloaded=0,
    )
