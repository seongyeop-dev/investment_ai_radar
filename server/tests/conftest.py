from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database import Database
from app.main import create_app


@pytest.fixture
def api_database() -> Database:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    database = Database(settings.database_url)
    database.create_schema()
    return database


@pytest.fixture
def api_app(api_database: Database) -> FastAPI:
    settings = Settings.from_env({"DATABASE_URL": "sqlite+pysqlite://"})
    return create_app(settings, database=api_database)


@pytest.fixture
def api_client(api_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(api_app, raise_server_exceptions=False) as client:
        yield client
