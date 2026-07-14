from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, SettingsConfigDict


class CommaSeparatedCorsEnvSource(EnvSettingsSource):
    def prepare_field_value(self, field_name, field, value, value_is_complex):  # type: ignore[no-untyped-def]
        if field_name == "cors_origins" and isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CommaSeparatedCorsDotEnvSource(DotEnvSettingsSource):
    def prepare_field_value(self, field_name, field, value, value_is_complex):  # type: ignore[no-untyped-def]
        if field_name == "cors_origins" and isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+asyncpg://factory:factory_dev_password@postgres:5432/factory_incidents",
        alias="DATABASE_URL",
    )
    backend_port: int = Field(default=8100, alias="BACKEND_PORT")
    internal_service_token: str = Field(default="change-me-in-local-env", alias="INTERNAL_SERVICE_TOKEN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3100"], alias="CORS_ORIGINS")
    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")
    default_sla_minutes: dict[str, int] = Field(
        default_factory=lambda: {"P1": 15, "P2": 60, "P3": 240, "P4": 1440},
        alias="DEFAULT_SLA_MINUTES",
    )
    dedupe_window_minutes: int = Field(default=60, alias="DEDUPE_WINDOW_MINUTES")
    llm_demo_mode: bool = Field(default=True, alias="LLM_DEMO_MODE")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="demo-analyzer", alias="LLM_MODEL")
    llm_timeout: float = Field(default=10.0, alias="LLM_TIMEOUT")
    vibration_p1_threshold: float = Field(default=8.0, alias="VIBRATION_P1_THRESHOLD")
    temperature_p1_threshold: float = Field(default=90.0, alias="TEMPERATURE_P1_THRESHOLD")
    defect_rate_p2_threshold: float = Field(default=5.0, alias="DEFECT_RATE_P2_THRESHOLD")
    repeat_escalation_count: int = Field(default=3, alias="REPEAT_ESCALATION_COUNT")
    low_confidence_threshold: float = Field(default=0.6, alias="LOW_CONFIDENCE_THRESHOLD")
    n8n_base_url: str = Field(default="http://n8n:5678", alias="N8N_BASE_URL")
    n8n_resume_timeout: float = Field(default=5.0, alias="N8N_RESUME_TIMEOUT")
    rpa_worker_url: str = Field(default="http://rpa-worker:8200", alias="RPA_WORKER_URL")
    rpa_worker_timeout: float = Field(default=30.0, alias="RPA_WORKER_TIMEOUT")
    rpa_artifact_root: str = Field(default="/artifacts/rpa", alias="RPA_ARTIFACT_ROOT")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        raise TypeError("CORS_ORIGINS must be a comma-separated string or list")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            CommaSeparatedCorsEnvSource(settings_cls),
            CommaSeparatedCorsDotEnvSource(settings_cls),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
