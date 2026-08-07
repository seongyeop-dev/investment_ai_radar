from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.services.reference_scheduler import (
    ReferenceSchedulerAlreadyRunning,
    ReferenceSchedulerCommandTimeout,
    ReferenceSchedulerLock,
    build_reference_scheduler_logger,
    close_reference_scheduler_logger,
    create_verified_sqlite_backup,
    run_reference_scheduler_command,
    verify_sqlite_database,
)


@dataclass(frozen=True)
class ReferenceScheduledRunConfig:
    project_root: Path
    database_path: Path
    subscription_name: str = "Howard Marks"
    creation_limit: int = 3
    timeout_seconds: int = 900
    lock_stale_seconds: int = 1800
    log_retention_days: int = 30
    expect_created: int | None = None
    console_logging: bool = True


@dataclass(frozen=True)
class ReferenceScheduledRunOutcome:
    status: str
    returncode: int
    message: str
    backup_path: Path | None
    child_returncode: int | None
    elapsed_seconds: float | None


def _utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def validate_reference_scheduled_run_config(
    config: ReferenceScheduledRunConfig,
) -> None:
    if not config.subscription_name.strip():
        raise ValueError("subscription_name must not be empty")

    if config.creation_limit < 1:
        raise ValueError("creation_limit must be at least 1")

    if config.timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1")

    if config.lock_stale_seconds < 1:
        raise ValueError("lock_stale_seconds must be at least 1")

    if config.log_retention_days < 1:
        raise ValueError("log_retention_days must be at least 1")

    if config.expect_created is not None and config.expect_created < 0:
        raise ValueError("expect_created must not be negative")


def _reference_subscription_enabled(
    database_path: Path,
    subscription_name: str,
) -> bool | None:
    database_uri = f"file:{database_path.resolve().as_posix()}?mode=ro"

    try:
        with sqlite3.connect(
            database_uri,
            uri=True,
            timeout=10,
        ) as connection:
            connection.execute("PRAGMA query_only = ON")

            rows = connection.execute(
                """
                SELECT enabled
                FROM reference_subscriptions
                WHERE display_name = ?
                """,
                (subscription_name,),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).casefold():
            return None

        raise

    if len(rows) != 1:
        return None

    return bool(rows[0][0])


def build_reference_batch_command(
    config: ReferenceScheduledRunConfig,
) -> tuple[str, ...]:
    project_root = config.project_root.resolve()

    batch_script = project_root / "server" / "scripts" / "reference_subscription_batch_apply.py"

    command = [
        sys.executable,
        str(batch_script),
        "--database-path",
        str(config.database_path.resolve()),
        "--subscription-name",
        config.subscription_name,
        "--limit",
        str(config.creation_limit),
        "--confirm-validation-write",
        "--allow-real-database",
    ]

    if config.expect_created is not None:
        command.extend(
            (
                "--expect-created",
                str(config.expect_created),
            )
        )

    return tuple(command)


def build_reference_batch_environment(
    project_root: Path,
) -> dict[str, str]:
    environment = os.environ.copy()

    server_path = str(project_root.resolve() / "server")

    existing_python_path = environment.get("PYTHONPATH", "")

    if existing_python_path:
        environment["PYTHONPATH"] = server_path + os.pathsep + existing_python_path
    else:
        environment["PYTHONPATH"] = server_path

    return environment


def run_reference_scheduled_batch(
    config: ReferenceScheduledRunConfig,
    *,
    now: datetime | None = None,
    command_override: Sequence[str] | None = None,
    environment_override: dict[str, str] | None = None,
) -> ReferenceScheduledRunOutcome:
    validate_reference_scheduled_run_config(config)

    current = _utc(now or datetime.now(UTC))

    project_root = config.project_root.resolve()
    database_path = config.database_path.resolve()

    runtime_directory = project_root / ".local" / "run"
    log_directory = project_root / ".local" / "logs" / "reference_scheduler"
    backup_directory = project_root / ".local" / "data" / "backups"

    timestamp = current.strftime("%Y%m%d_%H%M%S_%f")

    backup_path = backup_directory / (
        f"investment_ai_radar_before_scheduled_reference_{timestamp}.db"
    )

    command = tuple(
        command_override
        if command_override is not None
        else build_reference_batch_command(config)
    )

    environment = (
        environment_override
        if environment_override is not None
        else build_reference_batch_environment(project_root)
    )

    logger = build_reference_scheduler_logger(
        log_directory,
        retention_days=(config.log_retention_days),
        console=config.console_logging,
    )

    lock = ReferenceSchedulerLock(
        runtime_directory / "reference_scheduler.lock",
        stale_after_seconds=(config.lock_stale_seconds),
        command=command,
    )

    acquired = False
    effective_backup: Path | None = None

    try:
        subscription_enabled = _reference_subscription_enabled(
            database_path,
            config.subscription_name,
        )

        if subscription_enabled is False:
            logger.info(
                "REFERENCE_SCHEDULED_RUN_SKIPPED reason=subscription_disabled subscription=%s",
                config.subscription_name,
            )

            return ReferenceScheduledRunOutcome(
                status="SKIPPED_DISABLED",
                returncode=0,
                message=(f"Reference subscription is disabled: {config.subscription_name}"),
                backup_path=None,
                child_returncode=None,
                elapsed_seconds=None,
            )

        try:
            metadata = lock.acquire(now=current)
            acquired = True
        except ReferenceSchedulerAlreadyRunning as exc:
            logger.warning(
                "REFERENCE_SCHEDULED_RUN_SKIPPED reason=already_running detail=%s",
                exc,
            )

            return ReferenceScheduledRunOutcome(
                status="SKIPPED_ALREADY_RUNNING",
                returncode=0,
                message=str(exc),
                backup_path=None,
                child_returncode=None,
                elapsed_seconds=None,
            )

        logger.info(
            "REFERENCE_SCHEDULED_RUN_START "
            "pid=%s host=%s started_at=%s "
            "database=%s subscription=%s limit=%s",
            metadata.pid,
            metadata.host,
            metadata.started_at.isoformat(),
            database_path,
            config.subscription_name,
            config.creation_limit,
        )

        if lock.recovered_stale_lock_path:
            logger.warning(
                "REFERENCE_SCHEDULER_STALE_LOCK_RECOVERED path=%s",
                lock.recovered_stale_lock_path,
            )

        before_verification = verify_sqlite_database(database_path)

        if before_verification.integrity != "ok":
            raise RuntimeError("Source database integrity verification failed")

        if before_verification.foreign_key_errors:
            raise RuntimeError("Source database foreign key verification failed")

        backup_verification = create_verified_sqlite_backup(
            database_path,
            backup_path,
        )
        effective_backup = backup_path

        logger.info(
            "REFERENCE_DATABASE_BACKUP_CREATED path=%s revision=%s",
            backup_path,
            backup_verification.revision,
        )

        try:
            result = run_reference_scheduler_command(
                command,
                working_directory=project_root,
                timeout_seconds=(config.timeout_seconds),
                environment=environment,
            )
        except ReferenceSchedulerCommandTimeout as exc:
            after_timeout_verification = verify_sqlite_database(database_path)

            logger.error(
                "REFERENCE_SCHEDULED_RUN_TIMEOUT "
                "timeout_seconds=%s revision=%s "
                "integrity=%s foreign_key_errors=%s "
                "backup=%s stdout=%r stderr=%r",
                exc.timeout_seconds,
                after_timeout_verification.revision,
                after_timeout_verification.integrity,
                len(after_timeout_verification.foreign_key_errors),
                backup_path,
                exc.stdout,
                exc.stderr,
            )

            return ReferenceScheduledRunOutcome(
                status="TIMEOUT",
                returncode=124,
                message=str(exc),
                backup_path=backup_path,
                child_returncode=None,
                elapsed_seconds=None,
            )

        if result.stdout.strip():
            logger.info(
                "REFERENCE_BATCH_STDOUT\n%s",
                result.stdout.rstrip(),
            )

        if result.stderr.strip():
            logger.warning(
                "REFERENCE_BATCH_STDERR\n%s",
                result.stderr.rstrip(),
            )

        after_verification = verify_sqlite_database(database_path)

        if after_verification.revision != before_verification.revision:
            raise RuntimeError("Database revision changed during scheduled reference run")

        if after_verification.integrity != "ok":
            raise RuntimeError("Database integrity failed after scheduled reference run")

        if after_verification.foreign_key_errors:
            raise RuntimeError("Database foreign key errors were found after scheduled run")

        if result.returncode != 0:
            returncode = result.returncode if result.returncode > 0 else 1

            logger.error(
                "REFERENCE_SCHEDULED_RUN_FAILED "
                "child_returncode=%s "
                "elapsed_seconds=%.3f backup=%s",
                result.returncode,
                result.elapsed_seconds,
                backup_path,
            )

            return ReferenceScheduledRunOutcome(
                status="FAILED",
                returncode=returncode,
                message=(f"Reference batch returned {result.returncode}"),
                backup_path=backup_path,
                child_returncode=(result.returncode),
                elapsed_seconds=(result.elapsed_seconds),
            )

        logger.info(
            "REFERENCE_SCHEDULED_RUN_SUCCESS "
            "child_returncode=0 "
            "elapsed_seconds=%.3f "
            "revision=%s backup=%s",
            result.elapsed_seconds,
            after_verification.revision,
            backup_path,
        )

        return ReferenceScheduledRunOutcome(
            status="SUCCESS",
            returncode=0,
            message=("Scheduled reference batch completed successfully"),
            backup_path=backup_path,
            child_returncode=0,
            elapsed_seconds=(result.elapsed_seconds),
        )
    except BaseException as exc:
        logger.exception(
            "REFERENCE_SCHEDULED_RUN_ERROR database=%s backup=%s error=%s",
            database_path,
            effective_backup,
            exc,
        )

        return ReferenceScheduledRunOutcome(
            status="ERROR",
            returncode=1,
            message=str(exc),
            backup_path=effective_backup,
            child_returncode=None,
            elapsed_seconds=None,
        )
    finally:
        if acquired:
            released = lock.release()

            if released:
                logger.info("REFERENCE_SCHEDULER_LOCK_RELEASED")
            else:
                logger.error("REFERENCE_SCHEDULER_LOCK_RELEASE_FAILED")

        close_reference_scheduler_logger(logger)
