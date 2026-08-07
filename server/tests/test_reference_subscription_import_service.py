from __future__ import annotations

from sqlalchemy import func, select

from app.database import Database
from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)
from app.schemas.reference_subscriptions import (
    ReferenceSubscriptionImportRequest,
)
from app.services.reference_subscriptions import (
    ReferenceSubscriptionImportBlockedError,
    ReferenceSubscriptionImportService,
)


def _source(
    *,
    official: bool = True,
    enabled: bool = True,
) -> SourceRecord:
    return SourceRecord(
        name="Oaktree Official Insights",
        source_type="EXPERT_REFERENCE",
        source_grade=SourceGrade.A,
        domain="oaktreecapital.com",
        official=official,
        enabled=enabled,
        feed_url=("https://www.oaktreecapital.com/insights/rss"),
        provider_type="RSS",
        language="en",
        request_interval_seconds=21600,
        timeout_seconds=10,
        max_items=50,
        original_source_name=None,
    )


def _payload(
    source_id: str,
    *,
    confirm: bool,
) -> ReferenceSubscriptionImportRequest:
    return ReferenceSubscriptionImportRequest(
        source_id=source_id,
        subject_type=ReferenceSubjectType.EXPERT,
        display_name="  Howard   Marks  ",
        match_mode=ReferenceMatchMode.AUTHOR,
        match_terms=[
            " Howard Marks ",
            "howard marks",
            "Howard S. Marks",
            "",
        ],
        confirm=confirm,
    )


def _subscription_count(
    database: Database,
) -> int:
    with database.session_scope() as session:
        count = session.scalar(select(func.count()).select_from(ReferenceSubscriptionRecord))

        return int(count or 0)


def test_preview_normalizes_without_writing(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()

        payload = _payload(
            source.id,
            confirm=False,
        )

        preview = ReferenceSubscriptionImportService(session).preview(payload)

        assert preview.confirmed is False
        assert preview.would_create is True

        assert preview.normalized_display_name == "Howard Marks"
        assert preview.normalized_match_terms == [
            "Howard Marks",
            "Howard S. Marks",
        ]
        assert preview.validation_warnings == []
        assert preview.duplicate.duplicate is False

    assert _subscription_count(api_database) == 0


def test_confirm_creates_one_subscription(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()

        result = ReferenceSubscriptionImportService(session).confirm(
            _payload(
                source.id,
                confirm=True,
            )
        )

        assert result.confirmed is True
        assert result.subscription.display_name == "Howard Marks"
        assert result.subscription.match_terms == [
            "Howard Marks",
            "Howard S. Marks",
        ]
        assert result.subscription.enabled is True

    assert _subscription_count(api_database) == 1


def test_duplicate_subscription_is_blocked(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source()
        session.add(source)
        session.flush()

        service = ReferenceSubscriptionImportService(session)

        service.confirm(
            _payload(
                source.id,
                confirm=True,
            )
        )

        duplicate_preview = service.preview(
            _payload(
                source.id,
                confirm=False,
            )
        )

        assert duplicate_preview.would_create is False
        assert duplicate_preview.duplicate.duplicate is True
        assert "DUPLICATE_SUBSCRIPTION" in duplicate_preview.validation_warnings

        try:
            service.confirm(
                _payload(
                    source.id,
                    confirm=True,
                )
            )
        except ReferenceSubscriptionImportBlockedError:
            pass
        else:
            raise AssertionError("Duplicate confirm must be blocked")


def test_unofficial_source_is_blocked(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source(
            official=False,
        )
        session.add(source)
        session.flush()

        preview = ReferenceSubscriptionImportService(session).preview(
            _payload(
                source.id,
                confirm=False,
            )
        )

        assert preview.would_create is False
        assert "SOURCE_NOT_OFFICIAL" in preview.validation_warnings


def test_disabled_source_is_blocked(
    api_database: Database,
) -> None:
    with api_database.session_scope() as session:
        source = _source(
            enabled=False,
        )
        session.add(source)
        session.flush()

        preview = ReferenceSubscriptionImportService(session).preview(
            _payload(
                source.id,
                confirm=False,
            )
        )

        assert preview.would_create is False
        assert "SOURCE_DISABLED" in preview.validation_warnings
