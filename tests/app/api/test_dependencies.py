from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request

from app.api.dependencies import get_database, get_default_workspace_id
from app.config import Settings
from app.database import Database


def make_request(
    *,
    database: Database | None = None,
    settings: Settings | None = None,
) -> Request:
    application = FastAPI()
    application.state.database = database
    application.state.settings = settings or Settings()

    return Request({"type": "http", "app": application})


def test_get_database_returns_configured_database() -> None:
    database = Mock(spec=Database)

    assert get_database(make_request(database=database)) is database


def test_get_database_rejects_missing_configuration() -> None:
    with pytest.raises(HTTPException) as error:
        get_database(make_request())

    assert error.value.status_code == 503
    assert error.value.detail == "The Facility API database is not configured."


def test_get_default_workspace_id_returns_server_configuration() -> None:
    workspace_id = uuid4()
    request = make_request(settings=Settings(default_workspace_id=workspace_id))

    assert get_default_workspace_id(request) == workspace_id


def test_get_default_workspace_id_rejects_missing_configuration() -> None:
    with pytest.raises(HTTPException) as error:
        get_default_workspace_id(make_request())

    assert error.value.status_code == 503
    assert error.value.detail == "SPACE_CORP_DEFAULT_WORKSPACE_ID must be configured."
