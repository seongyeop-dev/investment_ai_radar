from __future__ import annotations

import ast
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "reference_subscription_batch_apply.py"
)


def _is_disabled_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False

    test = node.test

    if not isinstance(test, ast.UnaryOp):
        return False

    if not isinstance(test.op, ast.Not):
        return False

    operand = test.operand

    return (
        isinstance(operand, ast.Attribute)
        and operand.attr == "enabled"
        and isinstance(operand.value, ast.Name)
        and operand.value.id == "subscription"
    )


def _is_dispatch_call(
    node: ast.AST,
) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "fetch_reference_index_candidates"
    )


def test_disabled_subscription_guard_precedes_external_fetch() -> None:
    source = SCRIPT_PATH.read_text(
        encoding="utf-8-sig",
    )
    tree = ast.parse(source)

    guards = [node for node in ast.walk(tree) if _is_disabled_guard(node)]

    dispatch_calls = [node for node in ast.walk(tree) if _is_dispatch_call(node)]

    direct_fetch_calls = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr == "fetch_html"
        )
    ]

    assert len(guards) == 1
    assert len(dispatch_calls) == 1

    # Batch apply must not bypass the common dispatcher.
    assert direct_fetch_calls == []

    # Disabled subscriptions must return before
    # the dispatcher can perform an external request.
    assert guards[0].lineno < dispatch_calls[0].lineno


def test_disabled_subscription_guard_is_reachable() -> None:
    source = SCRIPT_PATH.read_text(
        encoding="utf-8-sig",
    )

    assert "ReferenceSubscriptionRecord.enabled.is_(True)" not in source
    assert "if not subscription.enabled:" in source
    assert "REFERENCE_SUBSCRIPTION_SKIPPED_DISABLED" in source
    assert "Expected exactly one subscription" in source
