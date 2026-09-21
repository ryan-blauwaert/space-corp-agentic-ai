"""Run a bounded, text-only model smoke call without accessing operational data."""

import argparse
import json
import logging
import math
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from uuid import uuid4

from pydantic import ValidationError

from app.config import Settings
from app.llm.configuration import configured_provider
from app.llm.contracts import ModelCallContext, ModelFinishReason, ModelRequest
from app.llm.errors import ModelCallError
from app.llm.service import ModelService

SMOKE_PROMPT = "Reply with the single word READY. Do not use tools."
PROMPT_ID = "model-smoke"
PROMPT_VERSION = "1"


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Must be a positive integer.") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("Must be a positive integer.")
    return number


def _positive_seconds(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Must be a positive finite number of seconds.") from None
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Must be a positive finite number of seconds.")
    return number


@contextmanager
def _telemetry_output() -> Iterator[None]:
    """Install only our safe service output, restoring logger state on exit."""
    logger = logging.getLogger("app.llm.service")
    previous = (logger.handlers[:], logger.level, logger.propagate, logger.disabled)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.disabled = False
    try:
        yield
    finally:
        logger.handlers, level, logger.propagate, logger.disabled = previous
        logger.setLevel(level)
        handler.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-output-tokens",
        type=_positive_int,
        default=256,
        help="Output cap, including reasoning tokens (default: 256).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=_positive_seconds,
        default=30.0,
        help="Per-attempt SDK timeout (default: 30 seconds).",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="Total attempt limit; 1 disables retries (default: 3).",
    )
    options = parser.parse_args(argv)

    try:
        settings = Settings()
    except ValidationError:
        # Validation errors can contain credentials and other configuration values.
        print(
            "Invalid application settings. Check your environment and .env file.", file=sys.stderr
        )
        return 2
    if (
        settings.llm_model_id is None
        or settings.llm_api_key is None
        or not (settings.llm_api_key.get_secret_value().strip())
    ):
        print(
            "Set SPACE_CORP_LLM_MODEL_ID and SPACE_CORP_LLM_API_KEY in your environment or .env.",
            file=sys.stderr,
        )
        return 2

    context = ModelCallContext(
        request_id=uuid4(),
        operation_id=uuid4(),
        model_id=settings.llm_model_id,
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
    )
    request = ModelRequest(
        context=context,
        prompt=SMOKE_PROMPT,
        max_output_tokens=options.max_output_tokens,
        timeout_seconds=options.timeout_seconds,
    )
    summary: dict[str, str | None] = {
        "request_id": str(context.request_id),
        "operation_id": str(context.operation_id),
    }
    try:
        with _telemetry_output(), configured_provider(settings) as provider:
            response = ModelService(provider, max_attempts=options.max_attempts).generate(request)
    except ModelCallError as error:
        summary.update(outcome="failed", error_kind=error.kind.value)
        exit_code = 1
    except Exception:
        # CLI boundary: report safely; never print SDK/setup exceptions or tracebacks.
        summary.update(outcome="failed", error_kind="internal_error")
        exit_code = 1
    else:
        summary.update(outcome=response.finish_reason.value, error_kind=None)
        exit_code = 0 if response.finish_reason == ModelFinishReason.COMPLETED else 1
    print(json.dumps(summary))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
