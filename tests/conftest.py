import os

import pytest
from sqlalchemy.engine import make_url


TEST_DATABASE_URL_ENVIRONMENT_VARIABLE = "SPACE_CORP_TEST_DATABASE_URL"
TEST_DATABASE_NAME_PREFIX = "space_corp_test"


@pytest.fixture
def integration_database_url(monkeypatch: pytest.MonkeyPatch) -> str:
    database_url = os.getenv(TEST_DATABASE_URL_ENVIRONMENT_VARIABLE)

    if database_url is None:
        pytest.skip(
            f"{TEST_DATABASE_URL_ENVIRONMENT_VARIABLE} is not configured."
        )

    database_name = make_url(database_url).database
    if database_name is None or not database_name.startswith(TEST_DATABASE_NAME_PREFIX):
        pytest.fail(
            f"{TEST_DATABASE_URL_ENVIRONMENT_VARIABLE} must use a database name "
            f"starting with {TEST_DATABASE_NAME_PREFIX!r}."
        )

    monkeypatch.setenv("SPACE_CORP_DATABASE_URL", database_url)
    return database_url
