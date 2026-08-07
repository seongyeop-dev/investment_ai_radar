from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.database import UTCDateTime


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ReferenceSourceChangeRecord(Base):
    __tablename__ = "reference_source_change_history"
    __table_args__ = (
        CheckConstraint(
            "operation IN ('CREATE', 'UPDATE')",
            name=("ck_reference_source_change_history_operation"),
        ),
        Index(
            "ix_reference_source_change_history_source_created",
            "source_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_id,
    )
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "sources.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    changed_fields: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    before_values: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    after_values: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
    )
    backup_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_now,
        nullable=False,
    )
