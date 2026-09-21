import pytest
from openai import OpenAI
from pydantic import SecretStr

from app.config import Settings
from app.llm.configuration import configured_provider


@pytest.mark.parametrize(
    "model,key,missing",
    [
        (None, None, "MODEL_ID"),
        ("chosen-model", None, "API_KEY"),
        ("chosen-model", "   ", "API_KEY"),
    ],
)
def test_configuration_required_only_at_provider_creation(model, key, missing, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-use-ambient-key")
    settings = Settings(
        _env_file=None, llm_model_id=model, llm_api_key=SecretStr(key) if key is not None else None
    )
    with pytest.raises(ValueError, match=missing):
        with configured_provider(settings):
            pytest.fail("Missing configuration")


@pytest.mark.parametrize("fail_inside", [False, True])
def test_configured_model_and_client_lifetime(monkeypatch, fail_inside):
    clients = []

    def construct(**kwargs):
        assert kwargs == {
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "max_retries": 0,
        }
        client = OpenAI(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.llm.configuration.OpenAI", construct)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid")
    settings = Settings(
        _env_file=None,
        llm_model_id="chosen-model",
        llm_api_key="test-key",
        llm_reasoning_effort="medium",
    )
    assert "test-key" not in repr(settings)
    try:
        with configured_provider(settings) as provider:
            assert provider.model_id == "chosen-model"
            assert provider.reasoning_effort == "medium"
            assert not clients[0].is_closed()
            if fail_inside:
                raise RuntimeError("test")
    except RuntimeError:
        assert fail_inside
    assert clients[0].is_closed()
