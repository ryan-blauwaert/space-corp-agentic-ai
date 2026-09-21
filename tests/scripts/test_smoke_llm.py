import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from openai import OpenAI

from app.config import Settings
from app.llm.service import ModelService
from scripts import smoke_llm


@pytest.fixture
def harness(monkeypatch):
    settings = Settings(_env_file=None, llm_model_id="test-model", llm_api_key="SECRET key")
    monkeypatch.setattr(smoke_llm, "Settings", lambda: settings)
    monkeypatch.setattr(
        smoke_llm,
        "ModelService",
        lambda provider, **kwargs: ModelService(provider, sleep=lambda _: None, **kwargs),
    )
    requests = []
    clients = []
    replies = []

    def handler(request):
        requests.append(request)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def construct(**kwargs):
        client = OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        clients.append(client)
        return client

    monkeypatch.setattr("app.llm.configuration.OpenAI", construct)
    return settings, replies, requests, clients


def success(**overrides):
    return httpx.Response(
        200,
        json={
            "id": "resp_test",
            "status": "completed",
            "model": "test-model-revision",
            "error": None,
            "incomplete_details": None,
            "usage": {"input_tokens": 10, "output_tokens": 1},
            "output": [
                {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "SECRET response", "annotations": []}
                    ],
                }
            ],
            **overrides,
        },
    )


def parsed(capsys):
    captured = capsys.readouterr()
    assert "SECRET" not in captured.out + captured.err
    assert smoke_llm.SMOKE_PROMPT not in captured.out + captured.err
    return json.loads(captured.out), [json.loads(line) for line in captured.err.splitlines()]


def test_command_wires_provider_service_and_safe_telemetry(harness, capsys):
    _, replies, requests, clients = harness
    replies.append(success())
    assert smoke_llm.main([]) == 0
    summary, events = parsed(capsys)
    assert summary["outcome"] == "completed"
    assert [entry["event"] for entry in events] == ["model_attempt", "model_operation"]
    assert all(
        entry["request_id"] == summary["request_id"]
        and entry["operation_id"] == summary["operation_id"]
        for entry in events
    )
    assert events[-1]["prompt_id"] == smoke_llm.PROMPT_ID
    assert events[-1]["prompt_version"] == smoke_llm.PROMPT_VERSION
    assert events[-1]["model_id"] == "test-model"
    assert events[-1]["output_tokens"] == 1
    assert json.loads(requests[0].content) == {
        "model": "test-model",
        "input": smoke_llm.SMOKE_PROMPT,
        "max_output_tokens": 256,
        "store": False,
    }
    assert all(value == 30.0 for value in requests[0].extensions["timeout"].values())
    assert all(client.is_closed() for client in clients)


def test_overrides_and_truncated_output_fail_smoke(harness, capsys):
    _, replies, requests, clients = harness
    replies.append(success(status="incomplete", incomplete_details={"reason": "max_output_tokens"}))
    assert (
        smoke_llm.main(
            ["--max-output-tokens", "512", "--timeout-seconds", "2.5", "--max-attempts", "1"]
        )
        == 1
    )
    summary, events = parsed(capsys)
    assert summary["outcome"] == "output_limit"
    assert events[-1]["outcome"] == "output_limit"
    assert len(requests) == 1
    assert json.loads(requests[0].content)["max_output_tokens"] == 512
    assert all(value == 2.5 for value in requests[0].extensions["timeout"].values())
    assert clients[0].is_closed()


@pytest.mark.parametrize("attempts", [1, 2, 3])
def test_retry_exhaustion_matches_cli_limit(harness, capsys, attempts):
    _, replies, requests, clients = harness
    replies.extend(
        httpx.Response(503, json={"error": {"message": "SECRET upstream"}}) for _ in range(attempts)
    )
    assert smoke_llm.main(["--max-attempts", str(attempts)]) == 1
    summary, events = parsed(capsys)
    assert summary["error_kind"] == "unavailable"
    assert len(requests) == attempts
    assert events[-1]["attempt_count"] == attempts
    assert events[-1]["operation_id"] == summary["operation_id"]
    assert clients[0].is_closed()


def test_retry_then_success(harness, capsys):
    _, replies, requests, _ = harness
    replies.extend([httpx.Response(429, json={"error": {"message": "SECRET"}}), success()])
    assert smoke_llm.main([]) == 0
    summary, events = parsed(capsys)
    assert summary["outcome"] == "completed"
    assert len(requests) == 2
    assert events[-1]["attempt_count"] == 2
    assert events[0]["error_kind"] == "rate_limit"


def test_authentication_failure_does_not_retry(harness, capsys):
    _, replies, requests, clients = harness
    replies.append(httpx.Response(401, json={"error": {"message": "SECRET credential"}}))
    assert smoke_llm.main([]) == 1
    summary, events = parsed(capsys)
    assert summary["error_kind"] == "authentication"
    assert len(requests) == 1
    assert events[-1]["request_id"] == summary["request_id"]
    assert clients[0].is_closed()


@pytest.mark.parametrize("overrides", [{"llm_model_id": None}, {"llm_api_key": None}])
def test_missing_configuration_prevents_client_creation(harness, monkeypatch, capsys, overrides):
    settings, _, requests, clients = harness
    monkeypatch.setattr(smoke_llm, "Settings", lambda: settings.model_copy(update=overrides))
    assert smoke_llm.main([]) == 2
    captured = capsys.readouterr()
    assert "SPACE_CORP_LLM_MODEL_ID" in captured.err
    assert "SPACE_CORP_LLM_API_KEY" in captured.err
    assert captured.out == ""
    assert requests == clients == []


def test_invalid_configuration_does_not_print_validation_input(harness, monkeypatch, capsys):
    def invalid_settings():
        return Settings(_env_file=None, environment="SECRET invalid setting")

    monkeypatch.setattr(smoke_llm, "Settings", invalid_settings)
    assert smoke_llm.main([]) == 2
    captured = capsys.readouterr()
    assert "Invalid application settings" in captured.err
    assert "SECRET" not in captured.err
    assert harness[3] == []


@pytest.mark.parametrize(
    "args",
    [
        ["--max-output-tokens", "0"],
        ["--max-output-tokens", "-1"],
        ["--max-output-tokens", "1.5"],
        ["--timeout-seconds", "0"],
        ["--timeout-seconds", "nan"],
        ["--timeout-seconds", "inf"],
        ["--timeout-seconds", "bad"],
        ["--max-attempts", "0"],
        ["--max-attempts", "4"],
    ],
)
def test_invalid_arguments_prevent_client_creation(harness, args):
    with pytest.raises(SystemExit) as caught:
        smoke_llm.main(args)
    assert caught.value.code == 2
    assert harness[2] == harness[3] == []


def test_unexpected_setup_failure_is_safe(harness, monkeypatch, capsys):
    def broken_client(**kwargs):
        raise RuntimeError("SECRET setup error")

    monkeypatch.setattr("app.llm.configuration.OpenAI", broken_client)
    assert smoke_llm.main([]) == 1
    summary, events = parsed(capsys)
    assert summary["error_kind"] == "internal_error"
    assert events == []  # No attempt began.


@pytest.mark.parametrize("fail", [False, True])
def test_command_restores_logging_state(harness, fail, capsys):
    _, replies, _, _ = harness
    logger = logging.getLogger("app.llm.service")
    original = (logger.handlers[:], logger.level, logger.propagate, logger.disabled)
    replies.append(
        httpx.Response(401, json={"error": {"message": "SECRET"}}) if fail else success()
    )
    assert smoke_llm.main([]) == int(fail)
    assert (logger.handlers, logger.level, logger.propagate, logger.disabled) == original
    parsed(capsys)


def test_module_entrypoint_without_credentials_needs_no_database(tmp_path):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("SPACE_CORP_", "OPENAI_"))
    }
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    result = subprocess.run(
        [sys.executable, "-m", "scripts.smoke_llm"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert "SPACE_CORP_LLM_MODEL_ID" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_unexpected_call_failure_is_safe_and_correlated(harness, monkeypatch, capsys):
    _, _, requests, clients = harness

    def broken_generate(self, request):
        raise RuntimeError("SECRET internal failure")

    monkeypatch.setattr("app.llm.openai_provider.OpenAIProvider.generate", broken_generate)
    assert smoke_llm.main([]) == 1
    summary, events = parsed(capsys)
    assert summary["error_kind"] == "internal_error"
    assert events[-1]["error_kind"] == "internal_error"
    assert events[-1]["operation_id"] == summary["operation_id"]
    assert requests == []
    assert clients[0].is_closed()


def test_help_requires_no_settings(harness, monkeypatch, capsys):
    def forbidden_settings():
        pytest.fail("Help must not load settings")

    monkeypatch.setattr(smoke_llm, "Settings", forbidden_settings)
    with pytest.raises(SystemExit) as caught:
        smoke_llm.main(["--help"])
    assert caught.value.code == 0
    assert "--max-output-tokens" in capsys.readouterr().out
    assert harness[3] == []


@pytest.mark.parametrize(
    "details",
    [
        {"code": "insufficient_quota"},
        {"code": "credit_balance_exhausted"},
        {"code": "organization_spend_limit_exceeded"},
        {"code": "project_spend_limit_exceeded"},
        {"code": "organization_usage_limit_exceeded"},
        {"type": "insufficient_quota"},
    ],
)
def test_quota_failure_stops_after_one_attempt(harness, capsys, details):
    _, replies, requests, clients = harness
    replies.append(
        httpx.Response(429, json={"error": {"message": "SECRET billing detail", **details}})
    )
    assert smoke_llm.main([]) == 1  # Default allows three attempts for transient failures.
    summary, events = parsed(capsys)
    assert summary["error_kind"] == "quota_exceeded"
    assert len(requests) == 1
    assert len(events) == 2
    assert all(
        event["error_kind"] == "quota_exceeded"
        and event["attempt_count"] == 1
        and event["operation_id"] == summary["operation_id"]
        for event in events
    )
    assert clients[0].is_closed()
