from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystPublisherType,
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
)
from app.models.database import PortfolioItemRecord

MAX_ANALYST_REFERENCE_LIMIT = 100


class AnalystReferenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        reference_id: str,
    ) -> AnalystReferenceRecord | None:
        return self.session.get(
            AnalystReferenceRecord,
            reference_id,
        )

    def by_canonical_url(
        self,
        canonical_url: str,
    ) -> AnalystReferenceRecord | None:
        return self.session.scalar(
            select(AnalystReferenceRecord).where(
                AnalystReferenceRecord.canonical_url == canonical_url
            )
        )

    def by_source_fingerprint(
        self,
        source_fingerprint: str,
    ) -> AnalystReferenceRecord | None:
        return self.session.scalar(
            select(AnalystReferenceRecord).where(
                AnalystReferenceRecord.source_fingerprint == source_fingerprint
            )
        )

    def portfolio_items(
        self,
        portfolio_item_ids: list[str],
    ) -> list[PortfolioItemRecord]:
        if not portfolio_item_ids:
            return []

        return list(
            self.session.scalars(
                select(PortfolioItemRecord)
                .where(PortfolioItemRecord.id.in_(portfolio_item_ids))
                .order_by(PortfolioItemRecord.id.asc())
            )
        )

    def coverages(
        self,
        reference_id: str,
    ) -> list[AnalystReferenceCoverageRecord]:
        return list(
            self.session.scalars(
                select(AnalystReferenceCoverageRecord)
                .where(AnalystReferenceCoverageRecord.analyst_reference_id == reference_id)
                .order_by(
                    AnalystReferenceCoverageRecord.created_at.asc(),
                    AnalystReferenceCoverageRecord.id.asc(),
                )
            )
        )

    def list(
        self,
        *,
        portfolio_item_id: str | None = None,
        publisher_type: AnalystPublisherType | None = None,
        access_type: AnalystAccessType | None = None,
        document_type: AnalystDocumentType | None = None,
        freshness_status: AnalystFreshnessStatus | None = None,
        include_inactive: bool = False,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AnalystReferenceRecord], int]:
        filters = []

        if not include_inactive:
            filters.append(AnalystReferenceRecord.is_active.is_(True))

        if publisher_type is not None:
            filters.append(AnalystReferenceRecord.publisher_type == publisher_type)

        if access_type is not None:
            filters.append(AnalystReferenceRecord.access_type == access_type)

        if document_type is not None:
            filters.append(AnalystReferenceRecord.document_type == document_type)

        if freshness_status is not None:
            filters.append(AnalystReferenceRecord.freshness_status == freshness_status)

        if query and query.strip():
            term = query.strip()
            filters.append(
                or_(
                    AnalystReferenceRecord.title.contains(
                        term,
                        autoescape=True,
                    ),
                    AnalystReferenceRecord.publisher_name.contains(
                        term,
                        autoescape=True,
                    ),
                    AnalystReferenceRecord.analyst_name.contains(
                        term,
                        autoescape=True,
                    ),
                )
            )

        statement = select(AnalystReferenceRecord)
        count_statement = select(func.count()).select_from(AnalystReferenceRecord)

        if portfolio_item_id is not None:
            statement = statement.join(
                AnalystReferenceCoverageRecord,
                AnalystReferenceCoverageRecord.analyst_reference_id
                == AnalystReferenceRecord.id,
            )
            count_statement = count_statement.join(
                AnalystReferenceCoverageRecord,
                AnalystReferenceCoverageRecord.analyst_reference_id
                == AnalystReferenceRecord.id,
            )
            filters.append(
                AnalystReferenceCoverageRecord.portfolio_item_id == portfolio_item_id
            )

        total = self.session.scalar(count_statement.where(*filters))

        rows = self.session.scalars(
            statement.where(*filters)
            .order_by(
                AnalystReferenceRecord.published_at.desc(),
                AnalystReferenceRecord.created_at.desc(),
                AnalystReferenceRecord.id.asc(),
            )
            .limit(
                min(
                    max(limit, 1),
                    MAX_ANALYST_REFERENCE_LIMIT,
                )
            )
            .offset(max(offset, 0))
        )

        return list(rows), int(total or 0)
