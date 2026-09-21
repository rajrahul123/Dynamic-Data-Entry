"""Tests for environment-driven configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


class TestCorsOrigins:
    def test_defaults_are_local_development_origins(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        settings = Settings(_env_file=None)

        assert settings.cors_origins == DEFAULT_CORS_ORIGINS

    def test_comma_separated_env_var(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example,https://admin.example")

        settings = Settings(_env_file=None)

        assert settings.cors_origins == ["https://app.example", "https://admin.example"]

    def test_json_array_env_var(self, monkeypatch):
        monkeypatch.setenv(
            "CORS_ORIGINS",
            '["https://app.example", "https://admin.example"]',
        )

        settings = Settings(_env_file=None)

        assert settings.cors_origins == ["https://app.example", "https://admin.example"]

    def test_whitespace_padding_is_stripped(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "  https://app.example , https://api.example  ")

        settings = Settings(_env_file=None)

        assert settings.cors_origins == ["https://app.example", "https://api.example"]

    def test_explicit_list_from_constructor(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        origins = ["https://app.example"]
        settings = Settings(_env_file=None, cors_origins=origins)

        assert settings.cors_origins == ["https://app.example"]

    def test_wildcard_allowed_outside_production(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        settings = Settings(_env_file=None, environment="development", cors_origins="*")

        assert settings.cors_origins == ["*"]

    def test_wildcard_rejected_in_production(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "*")

        with pytest.raises(
            ValidationError, match="CORS_ORIGINS must not contain '\\*' in production"
        ):
            Settings(_env_file=None, environment="production")

    def test_explicit_origins_allowed_in_production(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example,https://admin.example")

        settings = Settings(_env_file=None, environment="production", debug=False)

        assert settings.cors_origins == ["https://app.example", "https://admin.example"]
        assert settings.environment == "production"