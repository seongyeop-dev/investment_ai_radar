from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import SourceRecord
from app.models.reference_source_history import (
    ReferenceSourceChangeRecord,
)

MAX_REFERENCE_SOURCE_HISTORY_LIMIT = 100


class ReferenceSourceHistoryReadService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def list(
        self,
        source_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> (
        tuple[
            list[ReferenceSourceChangeRecord],
            int,
        ]
        | None
    ):
        source = self.session.get(
            SourceRecord,
            source_id,
        )

        if source is None:
            return None

        filters = (ReferenceSourceChangeRecord.source_id == source_id,)

        total = self.session.scalar(
            select(func.count()).select_from(ReferenceSourceChangeRecord).where(*filters)
        )

        rows = self.session.scalars(
            select(ReferenceSourceChangeRecord)
            .where(*filters)
            .order_by(
                ReferenceSourceChangeRecord.created_at.desc(),
                ReferenceSourceChangeRecord.id.desc(),
            )
            .limit(
                min(
                    max(limit, 1),
                    MAX_REFERENCE_SOURCE_HISTORY_LIMIT,
                )
            )
            .offset(max(offset, 0))
        )

        return (
            list(rows),
            int(total or 0),
        )
