"""Application settings loaded from environment variables and `.env`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Dynamic Data Entry Platform"
    environment: str = "development"
    debug: bool = True
    api_version: str = "0.1.0"

    database_url: str | None = None

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # JWT authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Per-IP auth rate limits (slowapi syntax, e.g. "5/minute", "3/hour")
    auth_login_rate_limit: str = "5/minute"
    auth_register_rate_limit: str = "3/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()