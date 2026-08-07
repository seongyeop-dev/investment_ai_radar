from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.time import SystemClock
from app.database import Base
from app.models.database import UTCDateTime


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return SystemClock().now()


def _enum(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        validate_strings=True,
        create_constraint=True,
    )


class ReferenceSubjectType(StrEnum):
    EXPERT = "EXPERT"
    INSTITUTION = "INSTITUTION"
    PUBLISHER = "PUBLISHER"


class ReferenceMatchMode(StrEnum):
    ALL_SOURCE = "ALL_SOURCE"
    AUTHOR = "AUTHOR"
    KEYWORD = "KEYWORD"


class ReferenceSubscriptionRecord(Base):
    __tablename__ = "reference_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "subject_type",
            "display_name",
            name="uq_reference_subscription_source_subject",
        ),
        Index(
            "ix_reference_subscriptions_enabled_source",
            "enabled",
            "source_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_id,
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey(
            "sources.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    subject_type: Mapped[ReferenceSubjectType] = mapped_column(
        _enum(
            ReferenceSubjectType,
            "reference_subject_type",
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    match_mode: Mapped[ReferenceMatchMode] = mapped_column(
        _enum(
            ReferenceMatchMode,
            "reference_match_mode",
        ),
        nullable=False,
        default=ReferenceMatchMode.ALL_SOURCE,
    )
    match_terms: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=_now,
        onupdate=_now,
    )

    @validates("display_name")
    def validate_display_name(
        self,
        key: str,
        value: str,
    ) -> str:
        del key
        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError("display_name must not be empty")

        if len(normalized) > 200:
            raise ValueError("display_name must not exceed 200 characters")

        return normalized

    @validates("match_terms")
    def normalize_match_terms(
        self,
        key: str,
        value: list[str],
    ) -> list[str]:
        del key

        if not isinstance(value, list):
            raise ValueError("match_terms must be a list")

        normalized_terms: list[str] = []
        seen: set[str] = set()

        for item in value:
            if not isinstance(item, str):
                raise ValueError("match_terms must contain strings")

            normalized = " ".join(item.split())

            if not normalized:
                continue

            if len(normalized) > 200:
                raise ValueError("match term must not exceed 200 characters")

            deduplication_key = normalized.casefold()

            if deduplication_key in seen:
                continue

            seen.add(deduplication_key)
            normalized_terms.append(normalized)

        return normalized_terms
