from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVOMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        frozen=True,
    )

    # Application
    app_name: str = Field(default="evomind-observability")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)

    # Schema versioning
    schema_version: str = Field(default="1.1.0")
    rule_version: str = Field(default="1.0.0")
    telemetry_version: str = Field(default="1.1.0")

    # Database
    database_path: str = Field(default="evomind.db")

    # Telemetry
    otel_exporter_endpoint: str = Field(default="http://localhost:4317")
    otel_exporter_insecure: bool = Field(default=True)
    otel_service_name: str = Field(default="evomind-observability")
    otel_trace_sampler: str = Field(default="always_on")
    otel_enabled: bool = Field(default=True)

    # SQL privacy
    mask_sql: bool = Field(default=False)
    sql_truncation_length: int = Field(default=200, ge=0)

    # Rule defaults
    rule_promotion_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    rule_demotion_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    rule_min_evidence: int = Field(default=3, ge=1)
    rule_initial_alpha: float = Field(default=1.0, gt=0.0)
    rule_initial_beta: float = Field(default=1.0, gt=0.0)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1024, le=65535)

    @field_validator("otel_trace_sampler")
    @classmethod
    def _validate_sampler(cls, v: str) -> str:
        allowed = {"always_on", "always_off", "parent_based_always_on"}
        if v not in allowed:
            msg = f"otel_trace_sampler must be one of {allowed}, got {v}"
            raise ValueError(msg)
        return v

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    @property
    def is_telemetry_enabled(self) -> bool:
        return self.otel_enabled
