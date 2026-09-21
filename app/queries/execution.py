"""Shared validation and transaction boundary for application-owned query executors."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Database
from app.queries.contracts import QUERY_PLAN, QueryContext, QueryPageRequest, QueryPlan
from app.queries.errors import QueryError, QueryErrorKind


def validate_request(
    context: QueryContext, plan: object, page: QueryPageRequest | None
) -> tuple[QueryContext, QueryPlan, QueryPageRequest]:
    """Revalidate even model_construct/model_copy inputs before database access."""
    try:
        return (
            QueryContext.model_validate(context.model_dump(warnings=False)),
            QUERY_PLAN.validate_python(
                plan.model_dump(warnings=False) if isinstance(plan, BaseModel) else plan
            ),
            QueryPageRequest.model_validate(
                page.model_dump(warnings=False) if page is not None else {}
            ),
        )
    except ValidationError:
        raise QueryError(context, QueryErrorKind.INVALID_PLAN) from None


@contextmanager
def pinned_query_session(
    database: Database, context: QueryContext
) -> Iterator[tuple[Session, UUID]]:
    """Resolve the caller-authorized workspace pin and sanitize database failures."""
    try:
        with database.query_session(context.workspace_id) as session:
            release = session.scalar(select(func.public.current_workspace_catalog_release()))
            if release is None:
                raise QueryError(context, QueryErrorKind.NOT_FOUND)
            yield session, release
    except DBAPIError as error:
        kind = (
            QueryErrorKind.TIMEOUT
            if getattr(error.orig, "sqlstate", None) == "57014"
            else QueryErrorKind.DATABASE_UNAVAILABLE
        )
        raise QueryError(context, kind) from None
    except SQLAlchemyError:
        raise QueryError(context, QueryErrorKind.DATABASE_UNAVAILABLE) from None
