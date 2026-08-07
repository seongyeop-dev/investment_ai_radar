from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

if TYPE_CHECKING:
    from app.core.config import Settings


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        if not url.strip():
            raise ValueError("DATABASE_URL is not configured")
        engine_options: dict[str, object] = {"pool_pre_ping": True}
        self.is_sqlite = url.startswith("sqlite")
        if self.is_sqlite:
            engine_options["connect_args"] = {"check_same_thread": False}
        if url in {"sqlite://", "sqlite+pysqlite://"}:
            engine_options["poolclass"] = StaticPool
        self.engine: Engine = create_engine(url, **engine_options)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        if not settings.database_configured:
            raise RuntimeError("DATABASE_URL must be explicitly configured")
        if settings.app_env.lower() in {
            "production",
            "prod",
        } and settings.database_url.startswith("sqlite"):
            raise RuntimeError("SQLite is for local tests only, not production")
        return cls(settings.database_url)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def reachable(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def session_dependency(self) -> Callable[[], Generator[Session, None, None]]:
        def dependency() -> Generator[Session, None, None]:
            with self.session_scope() as session:
                yield session

        return dependency
