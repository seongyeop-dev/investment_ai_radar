from __future__ import annotations

import app.models as model_exports
from app.database import Base
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)


def test_reference_subscription_is_exported_and_registered() -> None:
    assert model_exports.ReferenceSubscriptionRecord is ReferenceSubscriptionRecord
    assert model_exports.ReferenceSubjectType is ReferenceSubjectType
    assert model_exports.ReferenceMatchMode is ReferenceMatchMode

    table = Base.metadata.tables["reference_subscriptions"]

    assert table.c.id.primary_key is True
    assert table.c.source_id.nullable is False
    assert table.c.display_name.nullable is False
    assert table.c.enabled.nullable is False

    source_foreign_key = next(iter(table.c.source_id.foreign_keys))

    assert source_foreign_key.target_fullname == "sources.id"
