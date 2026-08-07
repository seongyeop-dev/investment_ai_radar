from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import sqlite3
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from types import TracebackType
from uuid import uuid4


class ReferenceSchedulerLockError(RuntimeError):
    """Base error for reference scheduler lock failures."""


class ReferenceSchedulerAlreadyRunning(ReferenceSchedulerLockError):
    """Raised when a non-stale scheduler lock already exists."""

    def __init__(
        self,
        metadata: ReferenceSchedulerLockMetadata | None,
    ) -> None:
        self.metadata = metadata

        if metadata is None:
            detail = "existing lock metadata is unreadable"
        else:
            detail = (
                f"pid={metadata.pid}, "
                f"host={metadata.host}, "
                f"started_at={metadata.started_at.isoformat()}"
            )

        super().__init__("Reference scheduler is already running: " + detail)


@dataclass(frozen=True)
class ReferenceSchedulerLockMetadata:
    token: str
    pid: int
    host: str
    started_at: datetime
    command: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "token": self.token,
            "pid": self.pid,
            "host": self.host,
            "started_at": self.started_at.isoformat(),
            "command": list(self.command),
        }

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, object],
    ) -> ReferenceSchedulerLockMetadata:
        started_at = datetime.fromisoformat(str(payload["started_at"]))

        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        else:
            started_at = started_at.astimezone(UTC)

        raw_command = payload.get(
            "command",
            [],
        )

        if not isinstance(
            raw_command,
            list,
        ):
            raise ValueError("Lock command must be a list")

        return cls(
            token=str(payload["token"]),
            pid=int(payload["pid"]),
            host=str(payload["host"]),
            started_at=started_at,
            command=tuple(str(value) for value in raw_command),
        )


class ReferenceSchedulerLock:
    """Atomic file lock for one reference batch at a time."""

    def __init__(
        self,
        path: Path,
        *,
        stale_after_seconds: int,
        command: Sequence[str] = (),
    ) -> None:
        if stale_after_seconds < 1:
            raise ValueError("stale_after_seconds must be at least 1")

        self.path = path
        self.stale_after_seconds = stale_after_seconds
        self.command = tuple(command)
        self.metadata: ReferenceSchedulerLockMetadata | None = None
        self.recovered_stale_lock_path: Path | None = None

    @staticmethod
    def _utc(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    def _new_metadata(
        self,
        now: datetime,
    ) -> ReferenceSchedulerLockMetadata:
        return ReferenceSchedulerLockMetadata(
            token=uuid4().hex,
            pid=os.getpid(),
            host=socket.gethostname(),
            started_at=self._utc(now),
            command=self.command,
        )

    def _write_new_lock(
        self,
        metadata: ReferenceSchedulerLockMetadata,
    ) -> None:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY

        descriptor = os.open(
            self.path,
            flags,
        )

        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as stream:
                json.dump(
                    metadata.to_payload(),
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.write("\n")
        except BaseException:
            self.path.unlink(missing_ok=True)
            raise

    def _read_metadata(
        self,
    ) -> ReferenceSchedulerLockMetadata | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))

            if not isinstance(
                payload,
                dict,
            ):
                return None

            return ReferenceSchedulerLockMetadata.from_payload(payload)
        except (
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return None

    def _is_stale(
        self,
        metadata: ReferenceSchedulerLockMetadata | None,
        *,
        now: datetime,
    ) -> bool:
        if metadata is None:
            return True

        age_seconds = (self._utc(now) - metadata.started_at).total_seconds()

        return age_seconds >= self.stale_after_seconds

    def _archive_stale_lock(
        self,
        *,
        now: datetime,
    ) -> Path:
        timestamp = self._utc(now).strftime("%Y%m%dT%H%M%SZ")

        archived_path = self.path.with_name(
            self.path.name + f".stale-{timestamp}-" + uuid4().hex[:8]
        )

        os.replace(
            self.path,
            archived_path,
        )

        return archived_path

    def acquire(
        self,
        *,
        now: datetime | None = None,
    ) -> ReferenceSchedulerLockMetadata:
        if self.metadata is not None:
            raise ReferenceSchedulerLockError("This lock instance is already acquired")

        current = self._utc(now or datetime.now(UTC))

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        metadata = self._new_metadata(current)

        for _attempt in range(3):
            try:
                self._write_new_lock(metadata)
            except FileExistsError:
                existing = self._read_metadata()

                if not self._is_stale(
                    existing,
                    now=current,
                ):
                    raise (ReferenceSchedulerAlreadyRunning(existing)) from None

                try:
                    archived = self._archive_stale_lock(now=current)
                except FileNotFoundError:
                    continue

                self.recovered_stale_lock_path = archived
                continue

            self.metadata = metadata
            return metadata

        raise ReferenceSchedulerLockError(
            "Could not acquire scheduler lock after concurrent retries"
        )

    def release(self) -> bool:
        owned_metadata = self.metadata

        if owned_metadata is None:
            return False

        current_metadata = self._read_metadata()

        if current_metadata is None or current_metadata.token != owned_metadata.token:
            self.metadata = None
            return False

        try:
            self.path.unlink()
        except FileNotFoundError:
            self.metadata = None
            return False

        self.metadata = None
        return True

    def __enter__(
        self,
    ) -> ReferenceSchedulerLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type
        del exc_value
        del traceback

        self.release()


def build_reference_scheduler_logger(
    log_directory: Path,
    *,
    retention_days: int = 30,
    console: bool = True,
) -> logging.Logger:
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")

    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = log_directory / "reference_scheduler.log"

    identity = hashlib.sha256(str(log_path.resolve()).encode("utf-8")).hexdigest()[:12]

    logger = logging.getLogger(f"investment_ai_radar.reference_scheduler.{identity}")

    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        ("%(asctime)sZ %(levelname)s %(message)s"),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime

    file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
        utc=True,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def close_reference_scheduler_logger(
    logger: logging.Logger,
) -> None:
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


@dataclass(frozen=True)
class SqliteDatabaseVerification:
    revision: str
    integrity: str
    foreign_key_errors: tuple[
        tuple[object, ...],
        ...,
    ]


@dataclass(frozen=True)
class ReferenceSchedulerCommandResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float


class ReferenceSchedulerCommandTimeout(TimeoutError):
    """Raised when the scheduled child process exceeds its limit."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.stdout = stdout
        self.stderr = stderr

        super().__init__(f"Reference scheduler command exceeded {timeout_seconds} seconds")


def verify_sqlite_database(
    path: Path,
) -> SqliteDatabaseVerification:
    resolved = path.resolve()

    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite database not found: {resolved}")

    connection = sqlite3.connect(resolved)

    try:
        revision_row = connection.execute(
            """
            SELECT version_num
            FROM alembic_version
            """
        ).fetchone()

        if revision_row is None:
            raise RuntimeError("Alembic revision was not found")

        integrity_row = connection.execute("PRAGMA integrity_check").fetchone()

        if integrity_row is None:
            raise RuntimeError("SQLite integrity result was not returned")

        foreign_key_errors = tuple(
            tuple(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()
        )
    finally:
        connection.close()

    return SqliteDatabaseVerification(
        revision=str(revision_row[0]),
        integrity=str(integrity_row[0]),
        foreign_key_errors=foreign_key_errors,
    )


def create_verified_sqlite_backup(
    source_path: Path,
    destination_path: Path,
) -> SqliteDatabaseVerification:
    source = source_path.resolve()
    destination = destination_path.resolve()

    source_verification = verify_sqlite_database(source)

    if source_verification.integrity != "ok":
        raise RuntimeError(
            "Source SQLite integrity check failed: " + source_verification.integrity
        )

    if source_verification.foreign_key_errors:
        raise RuntimeError("Source SQLite foreign key errors were found")

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():
        raise FileExistsError(f"Backup already exists: {destination}")

    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)

    try:
        source_connection.backup(destination_connection)
    except BaseException:
        destination_connection.close()
        source_connection.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        destination_connection.close()
        source_connection.close()

    try:
        backup_verification = verify_sqlite_database(destination)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

    if backup_verification.revision != source_verification.revision:
        destination.unlink(missing_ok=True)
        raise RuntimeError("Backup revision does not match source")

    if backup_verification.integrity != "ok":
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Backup SQLite integrity check failed: " + backup_verification.integrity
        )

    if backup_verification.foreign_key_errors:
        destination.unlink(missing_ok=True)
        raise RuntimeError("Backup SQLite foreign key errors were found")

    return backup_verification


def run_reference_scheduler_command(
    command: Sequence[str],
    *,
    working_directory: Path,
    timeout_seconds: int,
    environment: dict[str, str] | None = None,
) -> ReferenceSchedulerCommandResult:
    if not command:
        raise ValueError("command must not be empty")

    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1")

    started_at = time.monotonic()

    try:
        completed = subprocess.run(
            list(command),
            cwd=working_directory,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="replace",
            )

        raise ReferenceSchedulerCommandTimeout(
            timeout_seconds=timeout_seconds,
            stdout=stdout,
            stderr=stderr,
        ) from exc

    elapsed_seconds = time.monotonic() - started_at

    return ReferenceSchedulerCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        elapsed_seconds=elapsed_seconds,
    )
