from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.errors import database_error
from app.database import Database


def get_database(request: Request) -> Database:
    database: Database | None = getattr(request.app.state, "database", None)
    if database is None:
        raise database_error()
    return database


def get_session(request: Request) -> Generator[Session, None, None]:
    database = get_database(request)
    with database.session_scope() as session:
        yield session
