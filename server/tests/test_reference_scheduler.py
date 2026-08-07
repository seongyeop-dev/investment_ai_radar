from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.reference_scheduler import (
    ReferenceSchedulerAlreadyRunning,
    ReferenceSchedulerLock,
    build_reference_scheduler_logger,
    close_reference_scheduler_logger,
)

NOW = datetime(
    2026,
    8,
    1,
    2,
    0,
    tzinfo=UTC,
)


def test_scheduler_lock_acquires_and_releases(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "reference_scheduler.lock"

    lock = ReferenceSchedulerLock(
        lock_path,
        stale_after_seconds=3600,
        command=("reference-batch",),
    )

    metadata = lock.acquire(now=NOW)

    assert lock_path.is_file()
    assert metadata.command == ("reference-batch",)
    assert lock.release() is True
    assert not lock_path.exists()


def test_scheduler_lock_blocks_second_owner(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "reference_scheduler.lock"

    first = ReferenceSchedulerLock(
        lock_path,
        stale_after_seconds=3600,
    )
    second = ReferenceSchedulerLock(
        lock_path,
        stale_after_seconds=3600,
    )

    first.acquire(now=NOW)

    try:
        with pytest.raises(ReferenceSchedulerAlreadyRunning):
            second.acquire(now=(NOW + timedelta(minutes=5)))
    finally:
        first.release()


def test_scheduler_lock_recovers_stale_file(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "reference_scheduler.lock"

    stale_started_at = NOW - timedelta(hours=2)

    lock_path.write_text(
        json.dumps(
            {
                "token": "stale-token",
                "pid": 1234,
                "host": "old-host",
                "started_at": (stale_started_at.isoformat()),
                "command": ["old-reference-batch"],
            }
        ),
        encoding="utf-8",
    )

    lock = ReferenceSchedulerLock(
        lock_path,
        stale_after_seconds=3600,
    )

    lock.acquire(now=NOW)

    try:
        assert lock.recovered_stale_lock_path is not None
        assert lock.recovered_stale_lock_path.is_file()
        assert lock_path.is_file()
    finally:
        lock.release()


def test_scheduler_lock_keeps_replaced_owner(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "reference_scheduler.lock"

    lock = ReferenceSchedulerLock(
        lock_path,
        stale_after_seconds=3600,
    )

    lock.acquire(now=NOW)

    lock_path.write_text(
        json.dumps(
            {
                "token": "replacement-token",
                "pid": 9999,
                "host": "replacement-host",
                "started_at": NOW.isoformat(),
                "command": [],
            }
        ),
        encoding="utf-8",
    )

    assert lock.release() is False
    assert lock_path.is_file()


def test_scheduler_logger_writes_utf8_log(
    tmp_path: Path,
) -> None:
    logger = build_reference_scheduler_logger(
        tmp_path,
        retention_days=7,
        console=False,
    )

    try:
        logger.info("스케줄러 UTF-8 로그 기록 확인")

        for handler in logger.handlers:
            handler.flush()
    finally:
        close_reference_scheduler_logger(logger)

    log_path = tmp_path / "reference_scheduler.log"

    assert log_path.is_file()
    assert "스케줄러 UTF-8 로그 기록 확인" in log_path.read_text(encoding="utf-8")
