from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.analyst_references import (
    AnalystIngestMode,
    AnalystReferenceRecord,
)
from app.models.database import SourceRecord
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)

MAX_REFERENCE_SUBSCRIPTION_LIMIT = 100


class ReferenceSubscriptionRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def get(
        self,
        subscription_id: str,
    ) -> ReferenceSubscriptionRecord | None:
        return self.session.get(
            ReferenceSubscriptionRecord,
            subscription_id,
        )

    def source_for(
        self,
        source_id: str,
    ) -> SourceRecord | None:
        return self.session.get(
            SourceRecord,
            source_id,
        )

    def list_sources(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SourceRecord], int]:
        filters = [
            SourceRecord.source_type == "EXPERT_REFERENCE",
            SourceRecord.official.is_(True),
            SourceRecord.enabled.is_(True),
            SourceRecord.feed_url.is_not(None),
            SourceRecord.provider_type.is_not(None),
        ]

        if query and query.strip():
            term = query.strip()

            filters.append(
                or_(
                    SourceRecord.name.contains(
                        term,
                        autoescape=True,
                    ),
                    SourceRecord.domain.contains(
                        term,
                        autoescape=True,
                    ),
                )
            )

        count_statement = select(func.count()).select_from(SourceRecord).where(*filters)

        total = self.session.scalar(count_statement)

        rows = self.session.scalars(
            select(SourceRecord)
            .where(*filters)
            .order_by(
                SourceRecord.name.asc(),
                SourceRecord.domain.asc(),
                SourceRecord.id.asc(),
            )
            .limit(
                min(
                    max(limit, 1),
                    MAX_REFERENCE_SUBSCRIPTION_LIMIT,
                )
            )
            .offset(max(offset, 0))
        )

        return list(rows), int(total or 0)

    def by_identity(
        self,
        *,
        source_id: str,
        subject_type: ReferenceSubjectType,
        display_name: str,
    ) -> ReferenceSubscriptionRecord | None:
        return self.session.scalar(
            select(ReferenceSubscriptionRecord).where(
                ReferenceSubscriptionRecord.source_id == source_id,
                ReferenceSubscriptionRecord.subject_type == subject_type,
                ReferenceSubscriptionRecord.display_name == display_name,
            )
        )

    def automatic_reference_count(
        self,
        subscription_id: str,
    ) -> int:
        value = self.session.scalar(
            select(func.count())
            .select_from(AnalystReferenceRecord)
            .where(
                AnalystReferenceRecord.subscription_id == subscription_id,
                AnalystReferenceRecord.ingest_mode == AnalystIngestMode.AUTOMATIC,
            )
        )

        return int(value or 0)

    def list(
        self,
        *,
        subject_type: ReferenceSubjectType | None = None,
        match_mode: ReferenceMatchMode | None = None,
        enabled: bool | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[
        list[ReferenceSubscriptionRecord],
        int,
    ]:
        filters = []

        if subject_type is not None:
            filters.append(ReferenceSubscriptionRecord.subject_type == subject_type)

        if match_mode is not None:
            filters.append(ReferenceSubscriptionRecord.match_mode == match_mode)

        if enabled is not None:
            filters.append(ReferenceSubscriptionRecord.enabled.is_(enabled))

        if query and query.strip():
            term = query.strip()

            filters.append(
                or_(
                    ReferenceSubscriptionRecord.display_name.contains(
                        term,
                        autoescape=True,
                    ),
                    SourceRecord.name.contains(
                        term,
                        autoescape=True,
                    ),
                    SourceRecord.domain.contains(
                        term,
                        autoescape=True,
                    ),
                )
            )

        statement = select(ReferenceSubscriptionRecord).join(
            SourceRecord,
            SourceRecord.id == ReferenceSubscriptionRecord.source_id,
        )

        count_statement = (
            select(func.count())
            .select_from(ReferenceSubscriptionRecord)
            .join(
                SourceRecord,
                SourceRecord.id == ReferenceSubscriptionRecord.source_id,
            )
        )

        total = self.session.scalar(count_statement.where(*filters))

        rows = self.session.scalars(
            statement.where(*filters)
            .order_by(
                ReferenceSubscriptionRecord.enabled.desc(),
                ReferenceSubscriptionRecord.display_name.asc(),
                ReferenceSubscriptionRecord.id.asc(),
            )
            .limit(
                min(
                    max(limit, 1),
                    MAX_REFERENCE_SUBSCRIPTION_LIMIT,
                )
            )
            .offset(max(offset, 0))
        )

        return list(rows), int(total or 0)
