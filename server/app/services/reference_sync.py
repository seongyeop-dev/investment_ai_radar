from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analyst_references import (
    AnalystIngestMode,
    AnalystReferenceRecord,
    AnalystTranslationStatus,
    AnalystUserState,
)
from app.models.database import SourceRecord
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubscriptionRecord,
)
from app.providers.reference_feed import (
    ReferenceFeedItem,
)
from app.repositories.analyst_references import (
    AnalystReferenceRepository,
)
from app.services.analyst_references import (
    normalize_analyst_reference_url,
)
from app.services.reference_freshness import calculate_reference_freshness
from app.services.reference_translation import (
    plan_reference_translation,
)
from app.services.reference_translation_title_selection import (
    select_title_translation,
)


class ReferenceTitleTranslationProvider(
    Protocol,
):
    name: str

    def translate(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class ReferenceTranslationFields:
    source_language: str
    translated_title_ko: str | None
    translation_status: AnalystTranslationStatus
    translation_provider: str | None
    translation_error: str | None
    translated_at: datetime | None


def build_reference_translation_fields(
    *,
    title: str,
    public_abstract: str | None,
    provider: (ReferenceTitleTranslationProvider | None),
    now: datetime,
) -> ReferenceTranslationFields:
    plan = plan_reference_translation(
        title=title,
        public_abstract=public_abstract,
    )

    if plan.source_language == "ko":
        return ReferenceTranslationFields(
            source_language="ko",
            translated_title_ko=None,
            translation_status=(AnalystTranslationStatus.NOT_NEEDED),
            translation_provider=None,
            translation_error=None,
            translated_at=None,
        )

    if plan.source_language != "en":
        return ReferenceTranslationFields(
            source_language=plan.source_language,
            translated_title_ko=None,
            translation_status=(AnalystTranslationStatus.NOT_REQUESTED),
            translation_provider=None,
            translation_error=None,
            translated_at=None,
        )

    if provider is None:
        return ReferenceTranslationFields(
            source_language="en",
            translated_title_ko=None,
            translation_status=(AnalystTranslationStatus.PENDING),
            translation_provider=None,
            translation_error=("TRANSLATION_PROVIDER_NOT_CONFIGURED"),
            translated_at=None,
        )

    try:
        selection = select_title_translation(
            source_title=title,
            provider=provider,
        )
    except Exception as exc:
        return ReferenceTranslationFields(
            source_language="en",
            translated_title_ko=None,
            translation_status=(AnalystTranslationStatus.PENDING),
            translation_provider=provider.name,
            translation_error=(f"TRANSLATION_PROVIDER_ERROR:{exc.__class__.__name__}"),
            translated_at=None,
        )

    if selection.selected is None:
        return ReferenceTranslationFields(
            source_language="en",
            translated_title_ko=None,
            translation_status=(AnalystTranslationStatus.PENDING),
            translation_provider=provider.name,
            translation_error=("TITLE_REVIEW_REQUIRED"),
            translated_at=None,
        )

    return ReferenceTranslationFields(
        source_language="en",
        translated_title_ko=(selection.selected.translation),
        translation_status=(AnalystTranslationStatus.COMPLETED),
        translation_provider=provider.name,
        translation_error=None,
        translated_at=now,
    )


@dataclass(frozen=True, slots=True)
class ReferenceIngestResult:
    matched: bool
    created: bool
    duplicate: bool
    reference_id: str | None
    reason: str


def normalize_reference_match_text(
    value: str | None,
) -> str:
    if not value:
        return ""

    normalized = re.sub(
        r"[^\w]+",
        " ",
        value.casefold(),
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def _contains_phrase(
    text: str,
    phrase: str,
) -> bool:
    if not text or not phrase:
        return False

    return phrase == text or f" {phrase} " in f" {text} "


def reference_item_matches(
    subscription: ReferenceSubscriptionRecord,
    item: ReferenceFeedItem,
) -> bool:
    if not subscription.enabled:
        return False

    if subscription.match_mode is ReferenceMatchMode.ALL_SOURCE:
        return True

    terms = tuple(
        term
        for term in (
            normalize_reference_match_text(value) for value in subscription.match_terms
        )
        if term
    )

    if not terms:
        return False

    if subscription.match_mode is ReferenceMatchMode.AUTHOR:
        author = normalize_reference_match_text(item.author_name)

        return any(_contains_phrase(author, term) for term in terms)

    if subscription.match_mode is ReferenceMatchMode.KEYWORD:
        searchable = normalize_reference_match_text(
            " ".join(
                value
                for value in (
                    item.title,
                    item.author_name,
                    item.public_abstract,
                )
                if value
            )
        )

        return any(_contains_phrase(searchable, term) for term in terms)

    return False


class AutomaticReferenceIngestService:
    def __init__(
        self,
        session: Session,
        *,
        translation_provider: (ReferenceTitleTranslationProvider | None) = None,
    ) -> None:
        self.session = session
        self.repository = AnalystReferenceRepository(session)
        self.translation_provider = translation_provider

    def ingest(
        self,
        *,
        subscription: ReferenceSubscriptionRecord,
        source: SourceRecord,
        item: ReferenceFeedItem,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> ReferenceIngestResult:
        if not subscription.enabled:
            return ReferenceIngestResult(
                matched=False,
                created=False,
                duplicate=False,
                reference_id=None,
                reason="SUBSCRIPTION_DISABLED",
            )

        if str(subscription.source_id) != str(source.id):
            return ReferenceIngestResult(
                matched=False,
                created=False,
                duplicate=False,
                reference_id=None,
                reason="SOURCE_MISMATCH",
            )

        if not source.official or not source.enabled:
            return ReferenceIngestResult(
                matched=False,
                created=False,
                duplicate=False,
                reference_id=None,
                reason="SOURCE_UNAVAILABLE",
            )

        if not reference_item_matches(
            subscription,
            item,
        ):
            return ReferenceIngestResult(
                matched=False,
                created=False,
                duplicate=False,
                reference_id=None,
                reason="NOT_MATCHED",
            )

        canonical_url, _ = normalize_analyst_reference_url(item.canonical_url)

        source_fingerprint = sha256(
            (f"{source.id}|{item.provider_item_id}|{canonical_url}").encode()
        ).hexdigest()

        duplicate = self._duplicate(
            source_id=str(source.id),
            provider_item_id=item.provider_item_id,
            canonical_url=canonical_url,
            source_fingerprint=source_fingerprint,
        )

        if duplicate is not None:
            return ReferenceIngestResult(
                matched=True,
                created=False,
                duplicate=True,
                reference_id=duplicate.id,
                reason="DUPLICATE",
            )

        if dry_run:
            return ReferenceIngestResult(
                matched=True,
                created=False,
                duplicate=False,
                reference_id=None,
                reason="DRY_RUN",
            )

        current = self._utc(now or datetime.now(UTC))
        published_at = self._utc(item.published_at)

        translation = build_reference_translation_fields(
            title=item.title,
            public_abstract=item.public_abstract,
            provider=self.translation_provider,
            now=current,
        )

        reference = AnalystReferenceRecord(
            source_id=str(source.id),
            subscription_id=str(subscription.id),
            provider_item_id=item.provider_item_id,
            ingest_mode=(AnalystIngestMode.AUTOMATIC),
            user_state=AnalystUserState.NEW,
            discovered_at=current,
            publisher_name=source.name,
            publisher_type=item.publisher_type,
            title=item.title,
            analyst_name=item.author_name,
            published_at=published_at,
            canonical_url=canonical_url,
            access_type=item.access_type,
            document_type=item.document_type,
            publisher_rating_raw=None,
            publisher_target_price_raw=None,
            target_currency=None,
            public_abstract=item.public_abstract,
            source_language=(translation.source_language),
            translated_title_ko=(translation.translated_title_ko),
            translated_abstract_ko=None,
            translation_status=(translation.translation_status),
            translation_provider=(translation.translation_provider),
            translation_error=(translation.translation_error),
            translated_at=translation.translated_at,
            source_retrieved_at=current,
            source_fingerprint=source_fingerprint,
            freshness_status=calculate_reference_freshness(
                published_at,
                now=current,
            ),
            is_active=True,
        )

        self.session.add(reference)
        self.session.flush()

        return ReferenceIngestResult(
            matched=True,
            created=True,
            duplicate=False,
            reference_id=reference.id,
            reason="CREATED",
        )

    def _duplicate(
        self,
        *,
        source_id: str,
        provider_item_id: str,
        canonical_url: str,
        source_fingerprint: str,
    ) -> AnalystReferenceRecord | None:
        provider_duplicate = self.session.scalar(
            select(AnalystReferenceRecord).where(
                AnalystReferenceRecord.source_id == source_id,
                AnalystReferenceRecord.provider_item_id == provider_item_id,
            )
        )

        if provider_duplicate is not None:
            return provider_duplicate

        canonical_duplicate = self.repository.by_canonical_url(canonical_url)

        if canonical_duplicate is not None:
            return canonical_duplicate

        return self.repository.by_source_fingerprint(source_fingerprint)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)
