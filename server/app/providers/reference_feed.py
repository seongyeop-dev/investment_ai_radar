from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystPublisherType,
)


@dataclass(frozen=True, slots=True)
class ReferenceFeedItem:
    provider_item_id: str
    title: str
    canonical_url: str
    published_at: datetime
    author_name: str | None = None
    public_abstract: str | None = None
    publisher_type: AnalystPublisherType = AnalystPublisherType.INSTITUTION
    access_type: AnalystAccessType = AnalystAccessType.PUBLIC
    document_type: AnalystDocumentType = AnalystDocumentType.OTHER

    def __post_init__(self) -> None:
        provider_item_id = " ".join(self.provider_item_id.split())
        title = " ".join(self.title.split())
        canonical_url = self.canonical_url.strip()

        author_name = " ".join(self.author_name.split()) if self.author_name else None
        public_abstract = (
            " ".join(self.public_abstract.split()) if self.public_abstract else None
        )

        if not provider_item_id:
            raise ValueError("provider_item_id must not be empty")

        if len(provider_item_id) > 300:
            raise ValueError("provider_item_id must not exceed 300 characters")

        if not title:
            raise ValueError("title must not be empty")

        if len(title) > 500:
            raise ValueError("title must not exceed 500 characters")

        if not canonical_url:
            raise ValueError("canonical_url must not be empty")

        if len(canonical_url) > 1000:
            raise ValueError("canonical_url must not exceed 1000 characters")

        if author_name and len(author_name) > 200:
            raise ValueError("author_name must not exceed 200 characters")

        if public_abstract and len(public_abstract) > 300:
            raise ValueError("public_abstract must not exceed 300 characters")

        object.__setattr__(
            self,
            "provider_item_id",
            provider_item_id,
        )
        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "canonical_url",
            canonical_url,
        )
        object.__setattr__(
            self,
            "author_name",
            author_name,
        )
        object.__setattr__(
            self,
            "public_abstract",
            public_abstract,
        )
