from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DRY_RUN_PATH = ROOT / "server" / "scripts" / "reference_subscription_batch_dry_run.py"

APPLY_PATH = ROOT / "server" / "scripts" / "reference_subscription_batch_apply.py"

LIVE_RUN_PATH = ROOT / "server" / "scripts" / "reference_live_dry_run.py"


def _load_script(
    path: Path,
) -> tuple[str, ast.Module]:
    source = path.read_text(
        encoding="utf-8",
    )

    return source, ast.parse(source)


def _imported_names(
    tree: ast.Module,
) -> set[str]:
    names: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom,
            ),
        ):
            continue

        for alias in node.names:
            names.add(alias.asname or alias.name)

    return names


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


def _assert_dispatcher_call(
    tree: ast.Module,
    *,
    expected_argument: str,
) -> ast.Call:
    dispatcher_calls = _named_calls(
        tree,
        "fetch_reference_index_candidates",
    )

    assert len(dispatcher_calls) == 1

    call = dispatcher_calls[0]

    assert len(call.args) == 1

    argument = call.args[0]

    if expected_argument == "source":
        assert isinstance(argument, ast.Name)
        assert argument.id == "source"

    elif expected_argument == "item.source":
        assert isinstance(
            argument,
            ast.Attribute,
        )
        assert argument.attr == "source"
        assert isinstance(
            argument.value,
            ast.Name,
        )
        assert argument.value.id == "item"

    else:
        raise AssertionError("Unsupported expected argument")

    return call


def test_subscription_batch_dry_run_uses_dispatcher() -> None:
    source, tree = _load_script(DRY_RUN_PATH)

    assert "fetch_reference_index_candidates" in _imported_names(tree)

    _assert_dispatcher_call(
        tree,
        expected_argument="source",
    )

    assert "ReferenceHttpProvider" not in source
    assert "OaktreeMemoIndexAdapter" not in source
    assert ".fetch_html(" not in source

    assert "dispatch_result.final_urls[0]" in source
    assert "dispatch_result.status_codes[0]" in source
    assert "dispatch_result.request_count" in source
    assert "dispatch_result.external_documents_downloaded" in source


def test_subscription_batch_apply_uses_dispatcher() -> None:
    source, tree = _load_script(APPLY_PATH)

    assert "fetch_reference_index_candidates" in _imported_names(tree)

    _assert_dispatcher_call(
        tree,
        expected_argument="source",
    )

    assert "ReferenceHttpProvider" not in source
    assert "OaktreeMemoIndexAdapter" not in source
    assert ".fetch_html(" not in source
    assert "Only the Oaktree validation source" not in source

    assert "dispatch_result.final_urls[0]" in source
    assert "dispatch_result.status_codes[0]" in source
    assert "dispatch_result.request_count" in source
    assert "dispatch_result.external_documents_downloaded" in source


def test_disabled_subscription_stops_before_apply_dispatch() -> None:
    _, tree = _load_script(APPLY_PATH)

    dispatch_call = _assert_dispatcher_call(
        tree,
        expected_argument="source",
    )

    disabled_guards = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.If) and ast.unparse(node.test) == "not subscription.enabled")
    ]

    assert len(disabled_guards) == 1
    assert disabled_guards[0].lineno < dispatch_call.lineno

    assert any(isinstance(node, ast.Return) for node in ast.walk(disabled_guards[0]))


def test_apply_passes_dispatched_candidates_to_ingest() -> None:
    _, tree = _load_script(APPLY_PATH)

    ingest_calls = _named_calls(
        tree,
        "ingest_reference_candidates",
    )

    assert len(ingest_calls) == 1

    candidates_keyword = next(
        (keyword for keyword in ingest_calls[0].keywords if keyword.arg == "candidates"),
        None,
    )

    assert candidates_keyword is not None

    # Only candidates with a verified publication date
    # may enter analyst_references.
    assert ast.unparse(candidates_keyword.value) == "partition.date_verified"


def test_live_dry_run_uses_dispatcher_only() -> None:
    source, tree = _load_script(LIVE_RUN_PATH)

    assert "fetch_reference_index_candidates" in _imported_names(tree)

    _assert_dispatcher_call(
        tree,
        expected_argument="item.source",
    )

    assert "ReferenceHttpProvider(" not in source
    assert "OaktreeMemoIndexAdapter" not in source
    assert "BerkshireLetterIndexAdapter" not in source
    assert ".fetch_html(" not in source

    assert "berkshirehathaway.com/letters/letters.html" in source
    assert "berkshirehathaway.com/letters/gealetters.html" in source
    assert "oaktreecapital.com/insights" in source


def test_live_dry_run_declares_zero_database_writes() -> None:
    source, _ = _load_script(LIVE_RUN_PATH)

    assert "Database writes: 0" in source
    assert "External documents downloaded:" in source
