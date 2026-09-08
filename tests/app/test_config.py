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
        "SPACE_CORP_MIGRATION_DATABASE_URL",
        "SPACE_CORP_DEFAULT_WORKSPACE_ID",
    ):
        monkeypatch.delenv(variable_name, raising=False)


def load_settings() -> Settings:
    """Load settings without a developer's local dotenv file."""
    return Settings(_env_file=None)


def test_settings_use_development_defaults(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)

    settings = load_settings()

    assert settings.environment == "development"
    assert settings.application_name == "Agentic AI Operations Platform"
    assert settings.logging_level == "INFO"
    assert settings.database_url is None
    assert settings.migration_database_url is None
    assert settings.default_workspace_id is None


def test_settings_load_environment_overrides(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SPACE_CORP_ENVIRONMENT", "test")
    monkeypatch.setenv("SPACE_CORP_APPLICATION_NAME", "Test Operations API")
    monkeypatch.setenv("SPACE_CORP_LOGGING_LEVEL", "DEBUG")
    monkeypatch.setenv("SPACE_CORP_DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv(
        "SPACE_CORP_MIGRATION_DATABASE_URL", "postgresql://localhost/migration_test"
    )
    monkeypatch.setenv("SPACE_CORP_DEFAULT_WORKSPACE_ID", "11111111-1111-1111-1111-111111111111")

    settings = load_settings()

    assert settings.environment == "test"
    assert settings.application_name == "Test Operations API"
    assert settings.logging_level == "DEBUG"
    assert str(settings.database_url) == "postgresql://localhost/test"
    assert str(settings.migration_database_url) == "postgresql://localhost/migration_test"
    assert str(settings.default_workspace_id) == "11111111-1111-1111-1111-111111111111"


def test_settings_reject_unsupported_logging_level(
    monkeypatch: MonkeyPatch,
) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SPACE_CORP_LOGGING_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError):
        load_settings()


def test_settings_reject_unsupported_environment(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SPACE_CORP_ENVIRONMENT", "local")

    with pytest.raises(ValidationError):
        load_settings()


def test_settings_reject_non_postgresql_database_url(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SPACE_CORP_DATABASE_URL", "sqlite:///space-corp.db")

    with pytest.raises(ValidationError):
        load_settings()


def test_settings_reject_invalid_default_workspace_id(
    monkeypatch: MonkeyPatch,
) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("SPACE_CORP_DEFAULT_WORKSPACE_ID", "not-a-uuid")

    with pytest.raises(ValidationError):
        load_settings()


def test_settings_load_dotenv_file(tmp_path, monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "SPACE_CORP_ENVIRONMENT=test\n"
        "SPACE_CORP_APPLICATION_NAME=Dotenv Operations API\n"
        "SPACE_CORP_DEFAULT_WORKSPACE_ID=11111111-1111-1111-1111-111111111111\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=dotenv_file)

    assert settings.environment == "test"
    assert settings.application_name == "Dotenv Operations API"
    assert str(settings.default_workspace_id) == "11111111-1111-1111-1111-111111111111"
