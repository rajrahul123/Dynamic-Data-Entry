"""Application settings loaded from environment variables and `.env`."""

from functools import lru_cache
from typing import Annotated

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PRODUCTION_ENVIRONMENTS = {"production", "prod"}


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

    cors_origins: Annotated[str | list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Accept ``CORS_ORIGINS`` as a JSON array or a comma-separated string."""
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                text = text[1:-1]
            value = [
                item.strip().strip("\"'").strip()
                for item in text.split(",")
                if item.strip()
            ]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _deny_wildcard_origin_in_production(cls, value, info):
        environment = (info.data.get("environment") or "").lower()
        if environment in PRODUCTION_ENVIRONMENTS and "*" in value:
            raise ValueError("CORS_ORIGINS must not contain '*' in production")
        return value

    # JWT authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Per-IP auth rate limits (slowapi syntax, e.g. "5/minute", "3/hour")
    auth_login_rate_limit: str = "5/minute"
    auth_register_rate_limit: str = "3/minute"
    auth_forgot_password_rate_limit: str = "3/minute"
    auth_reset_password_rate_limit: str = "5/minute"

    # Password-reset OTP flow
    password_reset_otp_expire_minutes: int = 10

    # SMTP / outbound email. If ``smtp_host`` is left unset the app cannot
    # deliver mail and instead logs the reset OTP (dev convenience only);
    # production deployments must configure a real SMTP relay.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    emails_from_email: EmailStr | None = "megteach34@gmail.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()