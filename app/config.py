"""Environment-based configuration. Secrets are SecretStr and never rendered."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.errors import ConfigError

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "https://api.mistral.ai/v1"
    llm_model: str = Field(min_length=1)
    llm_api_key: SecretStr | None = None
    llm_timeout: float = Field(default=60.0, gt=0)
    # json_schema = structured output (falls back to json_object if the endpoint rejects it)
    llm_response_format: Literal["json_schema", "json_object"] = "json_schema"

    fundraisingbox_apitoken: SecretStr | None = None

    upload_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    session_ttl_seconds: int = Field(default=1800, gt=0)
    session_max_count: int = Field(default=200, gt=0)

    @property
    def llm_requires_key(self) -> bool:
        host = urlparse(self.llm_base_url).hostname or ""
        return host not in _LOCAL_HOSTS


def _format_validation_error(exc: ValidationError) -> str:
    names = sorted({str(err["loc"][0]).upper() for err in exc.errors() if err["loc"]})
    return "Invalid or missing configuration: " + ", ".join(names)


def load_settings(**overrides: object) -> Settings:
    """Build settings, turning validation problems into a clear ConfigError."""
    try:
        settings = Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from None
    if settings.llm_requires_key and settings.llm_api_key is None:
        raise ConfigError(
            "Invalid or missing configuration: LLM_API_KEY (required for non-local model endpoints)"
        )
    return settings


@lru_cache
def get_settings() -> Settings:
    return load_settings()


def require_fundraisingbox_token(settings: Settings) -> str:
    """Return the FundraisingBox token or raise a clear ConfigError."""
    if settings.fundraisingbox_apitoken is None:
        raise ConfigError(
            "FundraisingBox is not configured: FUNDRAISINGBOX_APITOKEN is missing",
            code="fundraisingbox_not_configured",
        )
    return settings.fundraisingbox_apitoken.get_secret_value()
