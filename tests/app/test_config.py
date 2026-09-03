import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.config import Settings


def clear_settings_environment(monkeypatch: MonkeyPatch) -> None:
    for variable_name in (
        "SPACE_CORP_ENVIRONMENT",
        "SPACE_CORP_APPLICATION_NAME",
        "SPACE_CORP_LOGGING_LEVEL",
        "SPACE_CORP_DATABASE_URL",
    ):
        monkeypatch.delenv(variable_name, raising=False)


def test_settings_use_development_defaults(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)

    settings = Settings()

    assert settings.environment == "development"
    assert settings.application_name == "Agentic AI Operations Platform"
    assert settings.logging_level == "INFO"
    assert settings.database_url is None


def test_settings_load_environment_overrides(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SPACE_CORP_ENVIRONMENT", "test")
    monkeypatch.setenv("SPACE_CORP_APPLICATION_NAME", "Test Operations API")
    monkeypatch.setenv("SPACE_CORP_LOGGING_LEVEL", "DEBUG")
    monkeypatch.setenv("SPACE_CORP_DATABASE_URL", "postgresql://localhost/test")

    settings = Settings()

    assert settings.environment == "test"
    assert settings.application_name == "Test Operations API"
    assert settings.logging_level == "DEBUG"
    assert settings.database_url == "postgresql://localhost/test"


def test_settings_reject_unsupported_logging_level(
    monkeypatch: MonkeyPatch,
) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SPACE_CORP_LOGGING_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError):
        Settings()
