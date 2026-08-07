from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystPublisherType,
)
from app.providers.reference_feed import (
    ReferenceFeedItem,
)


@dataclass(frozen=True, slots=True)
class ReferenceIndexCandidate:
    provider_item_id: str
    title: str
    canonical_url: str
    published_at: datetime | None
    author_name: str | None = None
    public_abstract: str | None = None
    publisher_type: AnalystPublisherType = AnalystPublisherType.INSTITUTION
    access_type: AnalystAccessType = AnalystAccessType.PUBLIC
    document_type: AnalystDocumentType = AnalystDocumentType.OTHER

    def to_feed_item(self) -> ReferenceFeedItem:
        if self.published_at is None:
            raise ValueError("published_at must be verified before ingest")

        return ReferenceFeedItem(
            provider_item_id=self.provider_item_id,
            title=self.title,
            canonical_url=self.canonical_url,
            published_at=self.published_at,
            author_name=self.author_name,
            public_abstract=self.public_abstract,
            publisher_type=self.publisher_type,
            access_type=self.access_type,
            document_type=self.document_type,
        )


def _absolute_url(
    base_url: str,
    href: str,
) -> str:
    absolute = urljoin(
        base_url,
        href.strip(),
    )
    parsed = urlsplit(absolute)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("reference URL must be absolute HTTP(S)")

    return absolute


def _decode_html(
    content: str | bytes,
) -> str:
    if isinstance(content, bytes):
        return content.decode(
            "utf-8",
            errors="replace",
        )

    return content


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True,
        )
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return

        values = dict(attrs)
        href = values.get("href")

        if not href:
            return

        self._href = href
        self._text = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if tag.lower() != "a" or self._href is None:
            return

        text = " ".join(" ".join(self._text).split())

        self.anchors.append(
            (
                self._href,
                text,
            )
        )

        self._href = None
        self._text = []


class BerkshireLetterIndexAdapter:
    _letter_path = re.compile(
        r"(?:^|/)(?P<year>\d{4})ltr\.pdf$",
        re.IGNORECASE,
    )

    @classmethod
    def parse(
        cls,
        content: str | bytes,
        *,
        base_url: str,
        author_name: str | None = None,
    ) -> tuple[ReferenceIndexCandidate, ...]:
        parser = _AnchorCollector()
        parser.feed(_decode_html(content))

        candidates: dict[
            str,
            ReferenceIndexCandidate,
        ] = {}

        for href, anchor_text in parser.anchors:
            canonical_url = _absolute_url(
                base_url,
                href,
            )
            path = urlsplit(canonical_url).path

            match = cls._letter_path.search(path)

            if match is None:
                continue

            year = match.group("year")

            if anchor_text and year not in anchor_text:
                continue

            provider_item_id = path.rsplit("/", 1)[-1].lower()

            candidates[provider_item_id] = ReferenceIndexCandidate(
                provider_item_id=provider_item_id,
                title=(f"Berkshire Hathaway {year} Shareholder Letter"),
                canonical_url=canonical_url,
                published_at=None,
                author_name=author_name,
            )

        return tuple(
            sorted(
                candidates.values(),
                key=lambda item: item.provider_item_id,
                reverse=True,
            )
        )


@dataclass(slots=True)
class _OaktreeArticle:
    href: str | None = None
    title_parts: list[str] = field(default_factory=list)
    published_value: str | None = None
    published_text_parts: list[str] = field(default_factory=list)
    abstract_parts: list[str] = field(default_factory=list)


class _OaktreeCollector(HTMLParser):
    def __init__(
        self,
        base_url: str,
    ) -> None:
        super().__init__(
            convert_charrefs=True,
        )
        self.base_url = base_url
        self.candidates: list[ReferenceIndexCandidate] = []
        self._article: _OaktreeArticle | None = None
        self._capture: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized_tag = tag.lower()
        values = dict(attrs)

        if normalized_tag == "article":
            self._article = _OaktreeArticle()
            self._capture = None
            return

        if self._article is None:
            return

        if normalized_tag == "a":
            href = values.get("href")

            if not href:
                return

            absolute = _absolute_url(
                self.base_url,
                href,
            )
            path = urlsplit(absolute).path.rstrip("/")

            if "/insights/memo/" not in path:
                return

            self._article.href = absolute
            self._article.title_parts = []
            self._capture = "title"
            return

        if normalized_tag == "time":
            self._article.published_value = values.get("datetime")
            self._article.published_text_parts = []
            self._capture = "time"
            return

        if normalized_tag == "p":
            classes = {value for value in (values.get("class") or "").split() if value}

            if classes.intersection(
                {
                    "abstract",
                    "summary",
                    "description",
                }
            ):
                self._article.abstract_parts = []
                self._capture = "abstract"

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._article is None:
            return

        if self._capture == "title":
            self._article.title_parts.append(data)
        elif self._capture == "time":
            self._article.published_text_parts.append(data)
        elif self._capture == "abstract":
            self._article.abstract_parts.append(data)

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        normalized_tag = tag.lower()

        if normalized_tag in {
            "a",
            "time",
            "p",
        }:
            self._capture = None

        if normalized_tag != "article" or self._article is None:
            return

        self._finalize_article()
        self._article = None
        self._capture = None

    def _finalize_article(self) -> None:
        if self._article is None or not self._article.href:
            return

        title = " ".join(" ".join(self._article.title_parts).split())

        if not title:
            return

        published_at = _parse_date(
            self._article.published_value or " ".join(self._article.published_text_parts)
        )

        abstract = " ".join(" ".join(self._article.abstract_parts).split())

        path = urlsplit(self._article.href).path.rstrip("/")

        provider_item_id = "oaktree:" + path.rsplit("/", 1)[-1].lower()

        self.candidates.append(
            ReferenceIndexCandidate(
                provider_item_id=provider_item_id,
                title=title,
                canonical_url=self._article.href,
                published_at=published_at,
                author_name="Howard Marks",
                public_abstract=(abstract or None),
            )
        )


def _parse_date(
    value: str | None,
) -> datetime | None:
    normalized = " ".join((value or "").split())

    if not normalized:
        return None

    normalized = re.sub(
        r"(\.\d{6})\d+(?=Z|[+-]\d{2}:\d{2}$)",
        r"\1",
        normalized,
    )

    try:
        parsed = datetime.fromisoformat(
            normalized.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        parsed = None

    if parsed is None:
        for date_format in (
            "%b %d, %Y",
            "%B %d, %Y",
        ):
            try:
                parsed = datetime.strptime(
                    normalized,
                    date_format,
                )
                break
            except ValueError:
                continue

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def _parse_oaktree_embedded_candidates(
    content: str | bytes,
    *,
    base_url: str,
) -> tuple[ReferenceIndexCandidate, ...]:
    decoded = html.unescape(_decode_html(content))

    decoder = json.JSONDecoder()
    marker = '{"InsightId":'
    position = 0

    base_host = (urlsplit(base_url).hostname or "").casefold()

    candidates: list[ReferenceIndexCandidate] = []

    while True:
        index = decoded.find(
            marker,
            position,
        )

        if index < 0:
            break

        try:
            payload, consumed = decoder.raw_decode(decoded[index:])
        except json.JSONDecodeError:
            position = index + len(marker)
            continue

        position = index + max(
            consumed,
            len(marker),
        )

        if not isinstance(payload, dict):
            continue

        more_link = payload.get("MoreLink")
        title_value = payload.get("Title")

        if not isinstance(more_link, str) or not isinstance(title_value, str):
            continue

        category = str(payload.get("CategoryText") or "").casefold()

        read_more = str(payload.get("ReadMoreText") or "").casefold()

        css_type = str(payload.get("CssClassType") or "").casefold()

        if category != "memos" or read_more != "read" or css_type != "article":
            continue

        canonical_url = _absolute_url(
            base_url,
            more_link,
        )

        parsed_url = urlsplit(canonical_url)

        candidate_host = (parsed_url.hostname or "").casefold()

        path = parsed_url.path.rstrip("/")

        if candidate_host != base_host:
            continue

        if "/insights/memo/" not in path:
            continue

        title = " ".join(title_value.split())

        if not title:
            continue

        iso_date = payload.get("IsoDate")
        formatted_date = payload.get("FormattedDate")

        published_at = _parse_date(iso_date if isinstance(iso_date, str) else None)

        if published_at is None:
            published_at = _parse_date(
                formatted_date
                if isinstance(
                    formatted_date,
                    str,
                )
                else None
            )

        provider_item_id = "oaktree:" + path.rsplit("/", 1)[-1].lower()

        candidates.append(
            ReferenceIndexCandidate(
                provider_item_id=provider_item_id,
                title=title,
                canonical_url=canonical_url,
                published_at=published_at,
                author_name="Howard Marks",
            )
        )

    return tuple(candidates)


class OaktreeMemoIndexAdapter:
    @staticmethod
    def parse(
        content: str | bytes,
        *,
        base_url: str,
    ) -> tuple[ReferenceIndexCandidate, ...]:
        parser = _OaktreeCollector(base_url)
        parser.feed(_decode_html(content))

        unique: dict[
            str,
            ReferenceIndexCandidate,
        ] = {}

        discovered = (
            *parser.candidates,
            *_parse_oaktree_embedded_candidates(
                content,
                base_url=base_url,
            ),
        )

        for candidate in discovered:
            unique[candidate.provider_item_id] = candidate

        minimum = datetime.min.replace(tzinfo=UTC)

        return tuple(
            sorted(
                unique.values(),
                key=lambda item: (
                    item.published_at or minimum,
                    item.provider_item_id,
                ),
                reverse=True,
            )
        )
