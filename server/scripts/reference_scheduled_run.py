from __future__ import annotations

import argparse
from pathlib import Path

from app.services.reference_scheduler_runner import (
    ReferenceScheduledRunConfig,
    run_reference_scheduled_batch,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the official reference collection batch with lock, backup, timeout, and logs."
        )
    )

    parser.add_argument(
        "--project-root",
        required=True,
    )
    parser.add_argument(
        "--database-path",
        required=True,
    )
    parser.add_argument(
        "--subscription-name",
        default="Howard Marks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
    )
    parser.add_argument(
        "--lock-stale-seconds",
        type=int,
        default=1800,
    )
    parser.add_argument(
        "--log-retention-days",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--expect-created",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--confirm-run",
        action="store_true",
        help=("Required safety confirmation for an operational database run."),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.confirm_run:
        raise RuntimeError("--confirm-run is required")

    config = ReferenceScheduledRunConfig(
        project_root=Path(args.project_root),
        database_path=Path(args.database_path),
        subscription_name=(args.subscription_name),
        creation_limit=args.limit,
        timeout_seconds=(args.timeout_seconds),
        lock_stale_seconds=(args.lock_stale_seconds),
        log_retention_days=(args.log_retention_days),
        expect_created=(args.expect_created),
    )

    outcome = run_reference_scheduled_batch(config)

    print("=" * 80)
    print("REFERENCE SCHEDULED RUN RESULT")
    print("=" * 80)
    print("Status:", outcome.status)
    print("Return code:", outcome.returncode)
    print("Message:", outcome.message)
    print("Backup:", outcome.backup_path)
    print(
        "Child return code:",
        outcome.child_returncode,
    )
    print(
        "Elapsed seconds:",
        outcome.elapsed_seconds,
    )
    print("=" * 80)

    return outcome.returncode


if __name__ == "__main__":
    raise SystemExit(main())
