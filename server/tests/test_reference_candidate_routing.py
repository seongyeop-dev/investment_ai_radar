from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from app.providers.reference_index import (
    ReferenceIndexCandidate,
)
from app.services.reference_discovery_staging import (
    partition_reference_candidates,
)

ROOT = Path(__file__).resolve().parents[2]

BATCH_PATH = ROOT / "server" / "scripts" / "reference_subscription_batch_apply.py"


def _candidate(
    *,
    provider_item_id: str,
    published_at: datetime | None,
) -> ReferenceIndexCandidate:
    return ReferenceIndexCandidate(
        provider_item_id=provider_item_id,
        title=f"Candidate {provider_item_id}",
        canonical_url=(f"https://www.berkshirehathaway.com/letters/{provider_item_id}"),
        published_at=published_at,
        author_name="Warren Buffett",
    )


def _named_calls(
    tree: ast.Module,
    name: str,
) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        )
    ]


def _keyword(
    call: ast.Call,
    name: str,
) -> ast.keyword:
    keyword = next(
        (item for item in call.keywords if item.arg == name),
        None,
    )

    assert keyword is not None
    return keyword


def test_partition_separates_candidates_by_date() -> None:
    verified = _candidate(
        provider_item_id="verified.pdf",
        published_at=datetime(
            2025,
            2,
            22,
            tzinfo=UTC,
        ),
    )

    unverified = _candidate(
        provider_item_id="unverified.pdf",
        published_at=None,
    )

    partition = partition_reference_candidates(
        [
            unverified,
            verified,
        ]
    )

    assert partition.date_verified == (verified,)

    assert partition.date_unverified == (unverified,)

    assert partition.date_unverified[0].published_at is None


def test_empty_partition_is_supported() -> None:
    partition = partition_reference_candidates([])

    assert partition.date_verified == ()
    assert partition.date_unverified == ()


def test_batch_apply_routes_candidates_by_date() -> None:
    source = BATCH_PATH.read_text(encoding="utf-8")

    tree = ast.parse(source)

    partition_calls = _named_calls(
        tree,
        "partition_reference_candidates",
    )

    staging_calls = _named_calls(
        tree,
        "stage_unverified_reference_candidates",
    )

    ingest_calls = _named_calls(
        tree,
        "ingest_reference_candidates",
    )

    assert len(partition_calls) == 1
    assert len(staging_calls) == 1
    assert len(ingest_calls) == 1

    staging_candidates = _keyword(
        staging_calls[0],
        "candidates",
    )

    ingest_candidates = _keyword(
        ingest_calls[0],
        "candidates",
    )

    assert ast.unparse(staging_candidates.value) == "partition.date_unverified"

    assert ast.unparse(ingest_candidates.value) == "partition.date_verified"

    assert partition_calls[0].lineno < staging_calls[0].lineno < ingest_calls[0].lineno


def test_disabled_guard_precedes_candidate_routing() -> None:
    source = BATCH_PATH.read_text(encoding="utf-8")

    tree = ast.parse(source)

    disabled_guards = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.If) and ast.unparse(node.test) == "not subscription.enabled")
    ]

    dispatch_calls = _named_calls(
        tree,
        "fetch_reference_index_candidates",
    )

    partition_calls = _named_calls(
        tree,
        "partition_reference_candidates",
    )

    assert len(disabled_guards) == 1
    assert len(dispatch_calls) == 1
    assert len(partition_calls) == 1

    assert disabled_guards[0].lineno < dispatch_calls[0].lineno < partition_calls[0].lineno


def test_batch_apply_does_not_generate_a_fallback_date() -> None:
    source = BATCH_PATH.read_text(encoding="utf-8")

    assert "published_at = " not in source
    assert "published_at=" not in source
    assert "datetime.now(" not in source
    assert "SystemClock" not in source
