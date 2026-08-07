from __future__ import annotations

from types import SimpleNamespace

import app.services.reference_batch_ingest as batch_module
from app.services.reference_batch_ingest import (
    ingest_reference_candidates,
)


def test_batch_forwards_translation_provider(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeIngestService:
        def __init__(
            self,
            session,
            *,
            translation_provider=None,
        ) -> None:
            captured["session"] = session
            captured["translation_provider"] = translation_provider

        def ingest(self, **kwargs):
            raise AssertionError("No candidates should be ingested")

    monkeypatch.setattr(
        batch_module,
        "_existing_automatic_cutoff",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        batch_module,
        "AutomaticReferenceIngestService",
        FakeIngestService,
    )

    session = object()
    provider = object()

    summary = ingest_reference_candidates(
        session,
        subscription=SimpleNamespace(
            id="subscription-id",
        ),
        source=object(),
        candidates=(),
        dry_run=False,
        translation_provider=provider,
    )

    assert captured["session"] is session
    assert captured["translation_provider"] is provider
    assert summary.examined == 0
    assert summary.processed == 0
    assert summary.created == 0
