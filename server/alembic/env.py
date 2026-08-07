from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from alembic import context
from app.database import Base
from app.models import analysis as analysis_models  # noqa: F401
from app.models import analyst_references as analyst_reference_models  # noqa: F401
from app.models import database as database_models  # noqa: F401
from app.models import disclosures as disclosure_models  # noqa: F401
from app.models import market_data as market_data_models  # noqa: F401
from app.models import reference_source_history as reference_source_history_models  # noqa: F401
from app.models import reference_subscriptions as reference_subscription_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configured_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        url = config.get_main_option("sqlalchemy.url").strip()
    if not url:
        raise RuntimeError("DATABASE_URL must be configured for Alembic")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_configured_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_migrations(supplied_connection)
        return

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _configured_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
