from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.database import Database
from app.models.analyst_references import (
    AnalystIngestMode,
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
    AnalystUserState,
)
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.disclosures import (
    InformationEventRecord,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.providers.reference_feed import (
    ReferenceFeedItem,
)
from app.services.reference_sync import (
    AutomaticReferenceIngestService,
    reference_item_matches,
)

SOURCE_ID = "33333333-3333-4333-8333-333333333331"


def _source() -> SourceRecord:
    return SourceRecord(
        id=SOURCE_ID,
        name="Oaktree Official Reference Fixture",
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain="oaktreecapital.test",
        official=True,
        enabled=True,
        feed_url=("https://oaktreecapital.test/memos"),
        provider_type="REFERENCE_INDEX",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=10,
        max_items=50,
        original_source_name=None,
    )


def _subscription(
    *,
    match_mode: ReferenceMatchMode,
    match_terms: list[str],
) -> ReferenceSubscriptionRecord:
    return ReferenceSubscriptionRecord(
        source_id=SOURCE_ID,
        subject_type=ReferenceSubjectType.EXPERT,
        display_name="Howard Marks",
        match_mode=match_mode,
        match_terms=match_terms,
        enabled=True,
    )


def _item(
    *,
    provider_item_id: str = "memo-2026-07",
    title: str = "The Value of Patience",
    author_name: str | None = "Howard Marks",
    public_abstract: str | None = ("A public memo about market cycles."),
) -> ReferenceFeedItem:
    return ReferenceFeedItem(
        provider_item_id=provider_item_id,
        title=title,
        canonical_url=(f"https://oaktreecapital.test/insights/{provider_item_id}"),
        published_at=datetime(
            2026,
            7,
            30,
            3,
            0,
            tzinfo=UTC,
        ),
        author_name=author_name,
        public_abstract=public_abstract,
    )


def _count(
    database: Database,
    model: type,
) -> int:
    with database.session_scope() as session:
        value = session.scalar(select(func.count()).select_from(model))

        return int(value or 0)


def test_reference_matcher_supports_all_modes() -> None:
    item = _item(
        author_name="Howard S. Marks, Co-Chairman",
        title="Market Cycles and Risk",
        public_abstract=("A memo discussing patient investing."),
    )

    all_source = _subscription(
        match_mode=ReferenceMatchMode.ALL_SOURCE,
        match_terms=[],
    )
    author = _subscription(
        match_mode=ReferenceMatchMode.AUTHOR,
        match_terms=[
            "Howard S. Marks",
        ],
    )
    keyword = _subscription(
        match_mode=ReferenceMatchMode.KEYWORD,
        match_terms=[
            "patient investing",
        ],
    )
    unmatched = _subscription(
        match_mode=ReferenceMatchMode.KEYWORD,
        match_terms=[
            "semiconductor supply chain",
        ],
    )

    assert reference_item_matches(
        all_source,
        item,
    )
    assert reference_item_matches(
        author,
        item,
    )
    assert reference_item_matches(
        keyword,
        item,
    )
    assert not reference_item_matches(
        unmatched,
        item,
    )


def test_reference_dry_run_does_not_write(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()

        subscription = _subscription(
            match_mode=ReferenceMatchMode.AUTHOR,
            match_terms=[
                "Howard Marks",
                "Howard S. Marks",
            ],
        )
        session.add(subscription)
        session.flush()

        result = AutomaticReferenceIngestService(session).ingest(
            subscription=subscription,
            source=source,
            item=_item(),
            dry_run=True,
        )

        assert result.matched is True
        assert result.created is False
        assert result.duplicate is False
        assert result.reference_id is None
        assert result.reason == "DRY_RUN"

    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 0
    )


def test_reference_automatic_ingest_is_isolated(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()

        subscription = _subscription(
            match_mode=ReferenceMatchMode.AUTHOR,
            match_terms=[
                "Howard Marks",
                "Howard S. Marks",
            ],
        )
        session.add(subscription)
        session.flush()

        service = AutomaticReferenceIngestService(session)

        created = service.ingest(
            subscription=subscription,
            source=source,
            item=_item(),
            dry_run=False,
            now=datetime(
                2026,
                7,
                30,
                4,
                0,
                tzinfo=UTC,
            ),
        )

        assert created.matched is True
        assert created.created is True
        assert created.duplicate is False
        assert created.reference_id is not None
        assert created.reason == "CREATED"

        record = session.get(
            AnalystReferenceRecord,
            created.reference_id,
        )

        assert record is not None
        assert record.source_id == source.id
        assert record.subscription_id == subscription.id
        assert record.provider_item_id == "memo-2026-07"
        assert record.ingest_mode is AnalystIngestMode.AUTOMATIC
        assert record.user_state is AnalystUserState.NEW
        assert record.analyst_name == "Howard Marks"

        duplicate = service.ingest(
            subscription=subscription,
            source=source,
            item=_item(),
            dry_run=False,
        )

        assert duplicate.matched is True
        assert duplicate.created is False
        assert duplicate.duplicate is True
        assert duplicate.reference_id == record.id
        assert duplicate.reason == "DUPLICATE"

        reference_count = session.scalar(
            select(func.count()).select_from(AnalystReferenceRecord)
        )
        coverage_count = session.scalar(
            select(func.count()).select_from(AnalystReferenceCoverageRecord)
        )
        event_count = session.scalar(select(func.count()).select_from(InformationEventRecord))

        assert int(reference_count or 0) == 1
        assert int(coverage_count or 0) == 0
        assert int(event_count or 0) == 0


def test_reference_unmatched_item_is_not_written(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()

        subscription = _subscription(
            match_mode=ReferenceMatchMode.KEYWORD,
            match_terms=[
                "semiconductor supply chain",
            ],
        )
        session.add(subscription)
        session.flush()

        result = AutomaticReferenceIngestService(session).ingest(
            subscription=subscription,
            source=source,
            item=_item(),
        )

        assert result.matched is False
        assert result.created is False
        assert result.duplicate is False
        assert result.reason == "NOT_MATCHED"

    assert (
        _count(
            api_database,
            AnalystReferenceRecord,
        )
        == 0
    )
