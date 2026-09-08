import os
from pathlib import Path

import pytest

from scripts.test_environment import apply_test_environment


def test_test_environment_file_populates_missing_variables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable_name in (
        "SPACE_CORP_TEST_DATABASE_URL",
        "SPACE_CORP_TEST_MIGRATION_DATABASE_URL",
        "SPACE_CORP_TEST_POSTGRES_BIN",
    ):
        monkeypatch.delenv(variable_name, raising=False)
    environment_file = tmp_path / ".env.test"
    environment_file.write_text(
        "SPACE_CORP_TEST_DATABASE_URL=postgresql+psycopg://space_corp_app@localhost:5432/space_corp_test\n"
        "SPACE_CORP_TEST_MIGRATION_DATABASE_URL=postgresql+psycopg://space_corp@localhost:5432/space_corp_test\n"
        "SPACE_CORP_TEST_POSTGRES_BIN=/opt/postgresql/bin\n",
        encoding="utf-8",
    )

    apply_test_environment(environment_file)

    assert os.environ["SPACE_CORP_TEST_DATABASE_URL"] == (
        "postgresql+psycopg://space_corp_app@localhost:5432/space_corp_test"
    )
    assert os.environ["SPACE_CORP_TEST_MIGRATION_DATABASE_URL"] == (
        "postgresql+psycopg://space_corp@localhost:5432/space_corp_test"
    )
    assert os.environ["SPACE_CORP_TEST_POSTGRES_BIN"] == "/opt/postgresql/bin"


def test_test_environment_file_preserves_exported_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment_file = tmp_path / ".env.test"
    environment_file.write_text(
        "SPACE_CORP_TEST_DATABASE_URL=postgresql+psycopg://space_corp_app@localhost:5432/space_corp_test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SPACE_CORP_TEST_DATABASE_URL", "postgresql://localhost/override")

    apply_test_environment(environment_file)

    assert os.environ["SPACE_CORP_TEST_DATABASE_URL"] == "postgresql://localhost/override"
