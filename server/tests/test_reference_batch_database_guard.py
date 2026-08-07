from __future__ import annotations

import ast
import sqlite3
import sys
from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SCRIPT_PATH = ROOT / "server" / "scripts" / "reference_subscription_batch_apply.py"


def _load_batch_module():
    spec = spec_from_file_location(
        "reference_subscription_batch_apply_guard_test",
        SCRIPT_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = module_from_spec(spec)

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


BATCH = _load_batch_module()


def _create_database(
    path: Path,
) -> Path:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT INTO alembic_version (
                version_num
            )
            VALUES (?)
            """,
            (BATCH.EXPECTED_REVISION,),
        )

        connection.commit()

    return path.resolve()


def test_original_validation_database_remains_allowed(
    tmp_path: Path,
) -> None:
    path = _create_database(tmp_path / BATCH.EXPECTED_VALIDATION_DATABASE_NAME)

    revision = BATCH.verify_validation_database(
        path,
        allow_real_database=False,
        allow_disposable_validation_database=False,
    )

    assert revision == BATCH.EXPECTED_REVISION


def test_disposable_database_requires_explicit_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disposable_root = (tmp_path / "batch_apply_validation").resolve()

    monkeypatch.setattr(
        BATCH,
        "DISPOSABLE_VALIDATION_ROOT",
        disposable_root,
    )

    path = _create_database(
        disposable_root / "20260803T000000" / BATCH.EXPECTED_DISPOSABLE_VALIDATION_DATABASE_NAME
    )

    with pytest.raises(
        RuntimeError,
        match=("--allow-disposable-validation-database is required"),
    ):
        BATCH.verify_validation_database(
            path,
            allow_real_database=False,
            allow_disposable_validation_database=False,
        )


def test_disposable_database_is_allowed_inside_run_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disposable_root = (tmp_path / "batch_apply_validation").resolve()

    monkeypatch.setattr(
        BATCH,
        "DISPOSABLE_VALIDATION_ROOT",
        disposable_root,
    )

    path = _create_database(
        disposable_root / "20260803T000000" / BATCH.EXPECTED_DISPOSABLE_VALIDATION_DATABASE_NAME
    )

    revision = BATCH.verify_validation_database(
        path,
        allow_real_database=False,
        allow_disposable_validation_database=True,
    )

    assert revision == BATCH.EXPECTED_REVISION


def test_disposable_database_outside_root_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disposable_root = (tmp_path / "allowed").resolve()

    monkeypatch.setattr(
        BATCH,
        "DISPOSABLE_VALIDATION_ROOT",
        disposable_root,
    )

    path = _create_database(
        tmp_path / "outside" / BATCH.EXPECTED_DISPOSABLE_VALIDATION_DATABASE_NAME
    )

    with pytest.raises(
        RuntimeError,
        match="must be under",
    ):
        BATCH.verify_validation_database(
            path,
            allow_real_database=False,
            allow_disposable_validation_database=True,
        )


def test_arbitrary_filename_remains_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disposable_root = (tmp_path / "batch_apply_validation").resolve()

    monkeypatch.setattr(
        BATCH,
        "DISPOSABLE_VALIDATION_ROOT",
        disposable_root,
    )

    path = _create_database(disposable_root / "20260803T000000" / "arbitrary.db")

    with pytest.raises(
        RuntimeError,
        match="Unsupported database file",
    ):
        BATCH.verify_validation_database(
            path,
            allow_real_database=False,
            allow_disposable_validation_database=True,
        )


def test_real_and_disposable_flags_are_mutually_exclusive(
    tmp_path: Path,
) -> None:
    path = _create_database(tmp_path / BATCH.EXPECTED_REAL_DATABASE_NAME)

    with pytest.raises(
        RuntimeError,
        match="cannot be used together",
    ):
        BATCH.verify_validation_database(
            path,
            allow_real_database=True,
            allow_disposable_validation_database=True,
        )


def test_main_forwards_disposable_database_flag() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    tree = ast.parse(source)

    calls = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "verify_validation_database"
        )
    ]

    assert len(calls) == 1

    keyword = next(
        (
            item
            for item in calls[0].keywords
            if item.arg == "allow_disposable_validation_database"
        ),
        None,
    )

    assert keyword is not None

    assert ast.unparse(keyword.value) == "args.allow_disposable_validation_database"
