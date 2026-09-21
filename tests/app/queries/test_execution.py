from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.database import Database
from app.queries.contracts import QueryContext, QueryPageRequest
from app.queries.errors import QueryError, QueryErrorKind
from app.queries.execution import pinned_query_session, validate_request


def context():
    return QueryContext(request_id=uuid4(), operation_id=uuid4(), workspace_id=uuid4())


def test_validate_request_preserves_trusted_values_and_defaults():
    ctx = context()
    validated, plan, page = validate_request(ctx, {"operation": "inventory"}, None)
    assert validated == ctx
    assert plan.operation == "inventory"
    assert page == QueryPageRequest()


@pytest.mark.parametrize("target", ["context", "page"])
def test_validate_request_rejects_unvalidated_copies(target):
    ctx, page = context(), QueryPageRequest()
    if target == "context":
        ctx = ctx.model_copy(update={"workspace_id": "not-a-uuid"})
    else:
        page = page.model_copy(update={"limit": 1000})
    with pytest.raises(QueryError) as caught:
        validate_request(ctx, {"operation": "inventory"}, page)
    assert caught.value.kind == QueryErrorKind.INVALID_PLAN


@pytest.mark.parametrize("failure", ["missing-pin", "database", "resource"])
def test_session_boundary_preserves_safe_errors_and_always_closes(failure):
    database, session, ctx, closed = Mock(spec=Database), Mock(), context(), []
    session.scalar.return_value = None if failure == "missing-pin" else uuid4()

    @contextmanager
    def transaction(workspace):
        assert workspace == ctx.workspace_id
        try:
            yield session
        finally:
            closed.append(True)

    database.query_session = transaction
    with pytest.raises(QueryError) as caught:
        with pinned_query_session(database, ctx):
            if failure == "database":
                raise SQLAlchemyError("private details")
            if failure == "resource":
                raise QueryError(ctx, QueryErrorKind.RESOURCE_LIMIT)
            pytest.fail("Missing pins must fail before yielding")
    assert (
        caught.value.kind
        == {
            "missing-pin": QueryErrorKind.NOT_FOUND,
            "database": QueryErrorKind.DATABASE_UNAVAILABLE,
            "resource": QueryErrorKind.RESOURCE_LIMIT,
        }[failure]
    )
    assert closed == [True]
    assert "private" not in str(caught.value)
