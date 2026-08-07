from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_has_minimal_real_status() -> None:
    client = TestClient(create_app(Settings.from_env({})))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert response.json()["service"] == "investment-ai-radar"
    assert "time" in response.json()


def test_system_info_reports_unconfigured_services_without_fake_data() -> None:
    client = TestClient(create_app(Settings.from_env({})))
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "local"
    assert body["databaseConfigured"] is False
    assert body["databaseReachable"] is False
    assert body["databaseType"] == "NOT_CONFIGURED"
    assert body["emailConfigured"] is False
    assert body["schedulerConfigured"] is False
    assert body["marketProvidersConfigured"] is False
    assert body["newsProvidersConfigured"] is False
    assert body["aiAutomationEnabled"] is False
    assert body["automaticTradingEnabled"] is False
    assert body["version"] == "0.2.0"
    assert "time" in body


def test_ai_automation_cannot_be_enabled_from_environment() -> None:
    settings = Settings.from_env({"AI_AUTOMATION_ENABLED": "true"})
    assert settings.ai_automation_enabled is False


def test_database_type_is_reported_without_exposing_database_url() -> None:
    settings = Settings.from_env(
        {
            "APP_ENV": "development",
            "DATABASE_URL": "sqlite+pysqlite:///private/local/path.db",
        }
    )
    client = TestClient(create_app(settings))
    body = client.get("/api/v1/system/info").json()
    assert body["environment"] == "development"
    assert body["databaseType"] == "SQLITE"
    assert "databaseUrl" not in body
    assert "private/local/path.db" not in str(body)


def test_default_cors_origins_include_real_and_validation_web() -> None:
    settings = Settings.from_env({})

    assert settings.allowed_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    )


def test_cors_allows_only_configured_local_and_lan_web_origins() -> None:
    origins = (
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://192.168.50.10:3000",
    )
    settings = Settings.from_env({"ALLOWED_ORIGINS": ",".join(origins)})
    client = TestClient(create_app(settings))

    for origin in origins:
        allowed = client.options(
            "/api/v1/system/info",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.headers["access-control-allow-origin"] == origin
        assert allowed.headers["access-control-allow-origin"] != "*"

    denied = client.options(
        "/api/v1/system/info",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in denied.headers
