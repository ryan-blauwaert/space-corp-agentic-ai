"""Required CI coverage must not silently become a successful partial run."""

from unittest.mock import MagicMock

import pytest

from tests.conftest import pytest_sessionfinish, pytest_sessionstart


@pytest.mark.parametrize(
    "required,skipped,fails", [(True, True, True), (True, False, False), (False, True, False)]
)
def test_required_run_rejects_skips(required: bool, skipped: bool, fails: bool) -> None:
    session = MagicMock()
    session.exitstatus = pytest.ExitCode.OK
    session.config.getoption.return_value = required
    session.config.pluginmanager.get_plugin.return_value.stats = {
        "skipped": [object()] if skipped else []
    }
    pytest_sessionfinish(session, 0)
    assert session.exitstatus == (pytest.ExitCode.TESTS_FAILED if fails else pytest.ExitCode.OK)


def test_required_run_rejects_missing_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPACE_CORP_TEST_DATABASE_URL", raising=False)
    session = MagicMock()
    session.config.getoption.return_value = True
    with pytest.raises(pytest.UsageError, match="SPACE_CORP_TEST_DATABASE_URL"):
        pytest_sessionstart(session)
