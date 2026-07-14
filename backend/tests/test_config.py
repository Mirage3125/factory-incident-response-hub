from factory_hub.config import Settings


def test_settings_loads_core_defaults_and_env_overrides(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("BACKEND_PORT", "8111")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "stage-1-secret-token")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3100,http://127.0.0.1:3100")

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.backend_port == 8111
    assert settings.internal_service_token == "stage-1-secret-token"
    assert settings.cors_origins == ["http://localhost:3100", "http://127.0.0.1:3100"]
    assert settings.timezone == "Asia/Shanghai"
    assert settings.default_sla_minutes == {"P1": 15, "P2": 60, "P3": 240, "P4": 1440}
