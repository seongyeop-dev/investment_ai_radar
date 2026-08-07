from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_REVISION = "20260803_0017"

BATCH_SCRIPTS = (
    ROOT / "server" / "scripts" / "reference_subscription_batch_apply.py",
    ROOT / "server" / "scripts" / "reference_subscription_batch_dry_run.py",
)


def _read_expected_revision(
    path: Path,
) -> str | None:
    source = path.read_text(encoding="utf-8")

    tree = ast.parse(source)

    for node in tree.body:
        target_name = None
        value = None

        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(
                node.targets[0],
                ast.Name,
            ):
                target_name = node.targets[0].id
                value = node.value

        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target,
            ast.Name,
        ):
            target_name = node.target.id
            value = node.value

        if target_name != "EXPECTED_REVISION":
            continue

        assert isinstance(
            value,
            ast.Constant,
        )

        return str(value.value)

    return None


def test_batch_apply_requires_candidate_schema() -> None:
    apply_path = BATCH_SCRIPTS[0]

    assert _read_expected_revision(apply_path) == EXPECTED_REVISION


def test_batch_scripts_do_not_use_legacy_revision() -> None:
    for path in BATCH_SCRIPTS:
        if not path.exists():
            continue

        revision = _read_expected_revision(path)

        if revision is None:
            continue

        assert revision == EXPECTED_REVISION
        assert revision != "20260730_0014"
        assert revision != "20260802_0015"
