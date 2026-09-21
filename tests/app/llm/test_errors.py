from uuid import uuid4

from app.llm.contracts import ModelCallContext
from app.llm.errors import ModelCallError, ModelErrorKind


def test_error_message_is_fixed_and_does_not_render_context() -> None:
    context = ModelCallContext(
        request_id=uuid4(),
        operation_id=uuid4(),
        model_id="model",
        prompt_id="prompt",
        prompt_version="1",
    )
    error = ModelCallError(context, ModelErrorKind.TIMEOUT)
    assert str(error) == "Model call failed: timeout."
    assert str(context.operation_id) not in str(error)
    assert error.context.request_id == context.request_id
