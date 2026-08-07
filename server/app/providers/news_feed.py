from __future__ import annotations

import re
import time
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree

import httpx

from app.core.backoff import ReconnectBackoff
from app.core.config import Settings
from app.models.database import SourceRecord
from app.models.disclosures import NewsProviderType, ProviderStatus


@dataclass(frozen=True, slots=True)
class NewsFeedItem:
    provider_item_id: str
    title: str
    original_url: str
    published_at: datetime
    source_updated_at: datetime | None
    snippet: str | None
    original_source_name: str | None = None


@dataclass(frozen=True, slots=True)
class NewsFeedResult:
    status: ProviderStatus
    items: tuple[NewsFeedItem, ...] = ()
    error_code: str | None = None


def _text(value: str | None, maximum: int) -> str:
    without_markup = re.sub(r"<[^>]+>", " ", unescape(value or ""))
    return re.sub(r"\s+", " ", without_markup).strip()[:maximum]


def _time(value: str | None) -> datetime:
    if not value:
        raise ValueError("feed item is missing a publication time")
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class NewsFeedProvider:
    def __init__(
        self,
        settings: Settings,
        source: SourceRecord,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.settings = settings
        self.source = source
        self.client = client
        self.sleep = sleep or time.sleep
        self.max_attempts = max_attempts
        self.backoff = ReconnectBackoff(jitter_ratio=0, maximum_seconds=4)

    @property
    def status(self) -> ProviderStatus:
        configured = (
            self.settings.news_sync_enabled
            and self.settings.news_feed_sync_enabled
            and self.source.enabled
            and bool(self.source.feed_url)
            and self.source.provider_type
            in {
                NewsProviderType.RSS.value,
                NewsProviderType.ATOM.value,
                NewsProviderType.OFFICIAL_IR_FEED.value,
            }
        )
        return ProviderStatus.READY if configured else ProviderStatus.NOT_CONFIGURED

    def fetch(self, *, limit: int | None = None) -> NewsFeedResult:
        if self.status is ProviderStatus.NOT_CONFIGURED:
            return NewsFeedResult(status=ProviderStatus.NOT_CONFIGURED)
        timeout = min(
            self.source.timeout_seconds,
            self.settings.news_request_timeout_seconds,
        )
        safe_limit = min(
            limit or self.source.max_items,
            self.source.max_items,
            self.settings.news_max_items_per_source,
        )
        for attempt in range(self.max_attempts):
            try:
                with self._client_context() as client:
                    response = client.get(
                        self.source.feed_url,
                        timeout=float(timeout),
                        headers={"User-Agent": "InvestmentAIRadar/2B feed-metadata-reader"},
                        follow_redirects=True,
                    )
                if response.status_code in {403, 429}:
                    if attempt + 1 < self.max_attempts:
                        self.sleep(self.backoff.delay(attempt))
                        continue
                    return NewsFeedResult(
                        status=(
                            ProviderStatus.RATE_LIMITED
                            if response.status_code == 429
                            else ProviderStatus.ERROR
                        ),
                        error_code=f"HTTP_{response.status_code}",
                    )
                response.raise_for_status()
                return NewsFeedResult(
                    status=ProviderStatus.READY,
                    items=tuple(self.parse(response.content)[:safe_limit]),
                )
            except (
                httpx.TimeoutException,
                httpx.TransportError,
                httpx.HTTPStatusError,
                ElementTree.ParseError,
                ValueError,
            ):
                if attempt + 1 < self.max_attempts:
                    self.sleep(self.backoff.delay(attempt))
                    continue
                return NewsFeedResult(
                    status=ProviderStatus.ERROR,
                    error_code="INVALID_OR_UNAVAILABLE_FEED",
                )
        return NewsFeedResult(status=ProviderStatus.ERROR, error_code="FEED_FAILED")

    @staticmethod
    def parse(content: bytes) -> list[NewsFeedItem]:
        root = ElementTree.fromstring(content)
        local_name = root.tag.rsplit("}", 1)[-1].lower()
        return (
            NewsFeedProvider._parse_atom(root)
            if local_name == "feed"
            else NewsFeedProvider._parse_rss(root)
        )

    @staticmethod
    def _parse_rss(root: ElementTree.Element) -> list[NewsFeedItem]:
        items: list[NewsFeedItem] = []
        for node in root.findall(".//item"):
            title = _text(node.findtext("title"), 500)
            link = _text(node.findtext("link"), 1000)
            item_id = _text(node.findtext("guid"), 500) or link
            if not title or not link or not item_id:
                raise ValueError("invalid RSS item")
            items.append(
                NewsFeedItem(
                    provider_item_id=item_id,
                    title=title,
                    original_url=link,
                    published_at=_time(node.findtext("pubDate") or node.findtext("published")),
                    source_updated_at=(
                        _time(node.findtext("updated")) if node.findtext("updated") else None
                    ),
                    snippet=_text(
                        node.findtext("description") or node.findtext("summary"),
                        1000,
                    )
                    or None,
                )
            )
        return items

    @staticmethod
    def _parse_atom(root: ElementTree.Element) -> list[NewsFeedItem]:
        namespace = {"a": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {}
        entry_path = ".//a:entry" if namespace else ".//entry"
        items: list[NewsFeedItem] = []
        for node in root.findall(entry_path, namespace):
            prefix = "a:" if namespace else ""
            title = _text(node.findtext(f"{prefix}title", namespaces=namespace), 500)
            item_id = _text(node.findtext(f"{prefix}id", namespaces=namespace), 500)
            link_node = node.find(f"{prefix}link", namespace)
            link = _text(link_node.get("href") if link_node is not None else None, 1000)
            published = node.findtext(
                f"{prefix}published", namespaces=namespace
            ) or node.findtext(f"{prefix}updated", namespaces=namespace)
            if not title or not item_id or not link:
                raise ValueError("invalid Atom item")
            updated = node.findtext(f"{prefix}updated", namespaces=namespace)
            summary = node.findtext(f"{prefix}summary", namespaces=namespace) or node.findtext(
                f"{prefix}content", namespaces=namespace
            )
            items.append(
                NewsFeedItem(
                    provider_item_id=item_id,
                    title=title,
                    original_url=link,
                    published_at=_time(published),
                    source_updated_at=_time(updated) if updated else None,
                    snippet=_text(summary, 1000) or None,
                )
            )
        return items

    def _client_context(self):
        return nullcontext(self.client) if self.client is not None else httpx.Client()
