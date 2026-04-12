from __future__ import annotations

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def make_settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "jwt_secret_key": "secret",
        "admin_email": "admin@example.com",
        "admin_password": "password123",
    }
    base.update(kwargs)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_debug_true_when_true_string() -> None:
    s = make_settings(debug="true")
    assert s.debug is True


def test_debug_false_when_release() -> None:
    s = make_settings(debug="release")
    assert s.debug is False


def test_debug_false_when_production() -> None:
    s = make_settings(debug="production")
    assert s.debug is False


def test_cors_origins_from_comma_string() -> None:
    s = make_settings(cors_origins="http://localhost:3000,http://localhost:5173")
    assert s.cors_origins == ["http://localhost:3000", "http://localhost:5173"]


def test_missing_database_url_raises() -> None:
    field = Settings.model_fields["database_url"]
    assert field.is_required()


def test_missing_jwt_secret_raises() -> None:
    field = Settings.model_fields["jwt_secret_key"]
    assert field.is_required()
