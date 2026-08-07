from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReferenceSourceChangeRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: str
    source_id: str = Field(
        alias="sourceId",
    )
    operation: str
    changed_fields: list[str] = Field(
        alias="changedFields",
    )
    before_values: dict[str, object] | None = Field(
        alias="beforeValues",
    )
    after_values: dict[
        str,
        object,
    ] = Field(
        alias="afterValues",
    )
    backup_path: str | None = Field(
        alias="backupPath",
    )
    created_at: datetime = Field(
        alias="createdAt",
    )


class ReferenceSourceChangeList(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )

    items: list[ReferenceSourceChangeRead]
    total: int
    limit: int
    offset: int
