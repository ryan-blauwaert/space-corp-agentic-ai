"""Safe query failure categories; no SQL, evidence, or model output in messages."""

from enum import StrEnum

from app.queries.contracts import QueryContext


class QueryErrorKind(StrEnum):
    INVALID_PLAN = "invalid_plan"
    NOT_FOUND = "not_found"
    MODEL_FAILURE = "model_failure"
    DATABASE_UNAVAILABLE = "database_unavailable"
    TIMEOUT = "timeout"


class QueryError(Exception):
    def __init__(self, context: QueryContext, kind: QueryErrorKind) -> None:
        self.context = context
        self.kind = kind
        super().__init__(f"Query failed: {kind.value}.")
