from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "server" / "scripts" / "validate_runtime_database.py"
BOOTSTRAP_PATH = ROOT / "server" / "scripts" / "reference_real_source_bootstrap.py"
START_REAL_PATH = ROOT / "scripts" / "start_real_environment.ps1"
DEV_LAN_PATH = ROOT / "scripts" / "dev-lan.ps1"
EXPECTED_REVISION = "20260803_0017"


def _load_module(
    name: str,
    path: Path,
):
    spec = spec_from_file_location(name, path)

    assert spec is not None
    assert spec.loader is not None

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_module(
    "runtime_database_validator_test",
    VALIDATOR_PATH,
)
BOOTSTRAP = _load_module(
    "reference_real_source_bootstrap_test",
    BOOTSTRAP_PATH,
)


def _create_database(
    path: Path,
    *,
    revision: str | None = EXPECTED_REVISION,
    include_alembic_table: bool = True,
    foreign_key_violation: bool = False,
) -> Path:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sqlite3.connect(path) as connection:
        if include_alembic_table:
            connection.execute(
                """
                CREATE TABLE alembic_version (
                    version_num TEXT NOT NULL
                )
                """
            )

            if revision is not None:
                connection.execute(
                    """
                    INSERT INTO alembic_version (
                        version_num
                    )
                    VALUES (?)
                    """,
                    (revision,),
                )

        connection.execute(
            """
            CREATE TABLE sample_items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO sample_items (
                name
            )
            VALUES ('runtime-validator-fixture')
            """
        )

        if foreign_key_violation:
            connection.execute(
                """
                CREATE TABLE parent_items (
                    id INTEGER PRIMARY KEY
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE child_items (
                    id INTEGER PRIMARY KEY,
                    parent_id INTEGER NOT NULL,
                    FOREIGN KEY (parent_id)
                        REFERENCES parent_items (id)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO child_items (
                    id,
                    parent_id
                )
                VALUES (1, 999)
                """
            )

        connection.commit()

    return path.resolve()


def _assert_validation_error(
    path: Path,
    *,
    check: str,
) -> None:
    with pytest.raises(VALIDATOR.RuntimeDatabaseValidationError) as captured:
        VALIDATOR.validate_runtime_database(path)

    assert captured.value.check == check


def test_runtime_validator_rejects_missing_database(
    tmp_path: Path,
) -> None:
    _assert_validation_error(
        tmp_path / "missing.db",
        check="file_exists",
    )


def test_runtime_validator_rejects_missing_alembic_table(
    tmp_path: Path,
) -> None:
    path = _create_database(
        tmp_path / "missing-alembic.db",
        include_alembic_table=False,
    )

    _assert_validation_error(
        path,
        check="alembic_version",
    )


@pytest.mark.parametrize(
    "revision",
    [
        "20260730_0014",
        "20260803_0016",
    ],
)
def test_runtime_validator_rejects_non_current_revision(
    tmp_path: Path,
    revision: str,
) -> None:
    path = _create_database(
        tmp_path / revision / "runtime.db",
        revision=revision,
    )

    _assert_validation_error(
        path,
        check="revision",
    )


def test_runtime_validator_accepts_current_revision_read_only(
    tmp_path: Path,
) -> None:
    path = _create_database(
        tmp_path / "current" / "runtime.db",
    )
    before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    before_mtime = path.stat().st_mtime_ns

    result = VALIDATOR.validate_runtime_database(path)

    after_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    after_mtime = path.stat().st_mtime_ns

    assert result.revision == EXPECTED_REVISION
    assert result.quick_check == "ok"
    assert result.foreign_key_errors == 0
    assert "?mode=ro" in (VALIDATOR.readonly_sqlite_uri(path))
    assert after_hash == before_hash
    assert after_mtime == before_mtime


def test_runtime_validator_rejects_quick_check_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _create_database(
        tmp_path / "quick-check" / "runtime.db",
    )
    real_connect = VALIDATOR.sqlite3.connect
    connect_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class QuickCheckCursor:
        def fetchall(self):
            return [("not ok",)]

    class QuickCheckConnection:
        def __init__(self, connection) -> None:
            self.connection = connection

        def execute(self, statement: str):
            if statement.strip().upper() == "PRAGMA QUICK_CHECK":
                return QuickCheckCursor()
            return self.connection.execute(statement)

        def close(self) -> None:
            self.connection.close()

    def connect_read_only(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return QuickCheckConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(
        VALIDATOR.sqlite3,
        "connect",
        connect_read_only,
    )

    _assert_validation_error(
        path,
        check="quick_check",
    )
    assert len(connect_calls) == 1
    assert str(connect_calls[0][0][0]).endswith("?mode=ro")
    assert connect_calls[0][1]["uri"] is True


def test_runtime_validator_rejects_foreign_key_errors(
    tmp_path: Path,
) -> None:
    path = _create_database(
        tmp_path / "foreign-key" / "runtime.db",
        foreign_key_violation=True,
    )

    _assert_validation_error(
        path,
        check="foreign_key_check",
    )


def test_runtime_validator_cli_exit_codes(
    tmp_path: Path,
) -> None:
    current_path = _create_database(
        tmp_path / "cli-current" / "runtime.db",
    )
    legacy_path = _create_database(
        tmp_path / "cli-legacy" / "runtime.db",
        revision="20260730_0014",
    )

    success = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--database-path",
            str(current_path),
            "--expected-revision",
            EXPECTED_REVISION,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    failure = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--database-path",
            str(legacy_path),
            "--expected-revision",
            EXPECTED_REVISION,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert success.returncode == 0
    assert "DATABASE_VALIDATION_OK" in success.stdout
    assert failure.returncode != 0
    assert "check=revision" in failure.stderr


def test_start_real_validates_before_starting_processes() -> None:
    source = START_REAL_PATH.read_text(encoding="utf-8")

    validator_call = source.index("& $PythonCommand")
    failure_guard = source.index(
        "if ($LASTEXITCODE -ne 0)",
        validator_call,
    )
    first_process_start = source.index("Start-Process")

    assert ".local\\data\\investment_ai_radar.db" in source
    assert "validate_runtime_database.py" in source
    assert "20260803_0017" in source
    assert validator_call < failure_guard < first_process_start
    assert "alembic" not in source.casefold()


def test_dev_lan_separates_development_and_real_databases() -> None:
    source = DEV_LAN_PATH.read_text(encoding="utf-8")

    assert "[switch]$UseLocalDatabase" in source
    assert "[switch]$UseRealDatabase" in source
    assert ".local\\data\\lan\\investment_ai_radar_lan.db" in source
    assert ".local\\data\\investment_ai_radar.db" in source
    assert "$UseLocalDatabase -and $UseRealDatabase" in source
    assert "LAN development database must differ from the real database." in source
    assert "-UseRealDatabase flag for LAN access." in source


def test_dev_lan_validates_real_database_without_migration() -> None:
    source = DEV_LAN_PATH.read_text(encoding="utf-8")

    real_guard = source.index("if ($UseRealDatabase) {")
    validator_call = source.index(
        "$databaseValidator",
        real_guard,
    )
    local_migration_guard = source.index(
        "elseif ($UseLocalDatabase) {",
        validator_call,
    )
    migration_call = source.index(
        "$upgradeResult = @(& $python -m alembic upgrade head 2>&1)",
        local_migration_guard,
    )
    first_process_start = source.index("Start-Process")
    real_database_section = source[real_guard:local_migration_guard]

    assert "20260803_0017" in source
    assert "validate_runtime_database.py" in source
    assert validator_call < local_migration_guard
    assert local_migration_guard < migration_call
    assert migration_call < first_process_start
    assert "alembic" not in real_database_section.casefold()


def test_real_source_bootstrap_requires_current_revision(
    tmp_path: Path,
) -> None:
    assert BOOTSTRAP.EXPECTED_REVISION == EXPECTED_REVISION

    legacy_path = _create_database(
        tmp_path / "legacy" / BOOTSTRAP.EXPECTED_DATABASE_NAME,
        revision="20260730_0014",
    )
    current_path = _create_database(
        tmp_path / "current" / BOOTSTRAP.EXPECTED_DATABASE_NAME,
    )

    with pytest.raises(
        RuntimeError,
        match="Unexpected database revision",
    ):
        BOOTSTRAP.verify_database(legacy_path)

    snapshot = BOOTSTRAP.verify_database(current_path)

    assert snapshot["revision"] == EXPECTED_REVISION
    assert snapshot["integrity"] == "ok"
    assert snapshot["foreign_key_errors"] == 0
