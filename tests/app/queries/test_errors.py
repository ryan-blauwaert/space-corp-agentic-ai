from uuid import uuid4

import pytest

from app.queries.contracts import QueryContext
from app.queries.errors import QueryError, QueryErrorKind


@pytest.mark.parametrize("kind", list(QueryErrorKind))
def test_errors_preserve_context_without_rendering_it(kind):
    context = QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=uuid4())
    error = QueryError(context, kind)
    assert error.context is context
    assert error.kind is kind
    assert str(error) == f"Query failed: {kind.value}."
    assert str(context.workspace_id) not in repr(error)
