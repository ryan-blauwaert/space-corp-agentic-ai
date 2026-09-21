"""Opt-in provider construction; operational API startup needs no model key."""

from collections.abc import Iterator
from contextlib import contextmanager

from openai import OpenAI

from app.config import Settings
from app.llm.openai_provider import OpenAIProvider


@contextmanager
def configured_provider(settings: Settings) -> Iterator[OpenAIProvider]:
    """Own the SDK client lifetime and require explicit application credentials."""
    if settings.llm_model_id is None:
        raise ValueError("SPACE_CORP_LLM_MODEL_ID is required for model calls.")
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value().strip():
        raise ValueError("SPACE_CORP_LLM_API_KEY is required for model calls.")
    with OpenAI(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url="https://api.openai.com/v1",
        max_retries=0,
    ) as client:
        yield OpenAIProvider(client, settings.llm_model_id, settings.llm_reasoning_effort)
