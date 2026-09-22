"""Bounded, single-process pending questions for the local MVP, not user sessions."""

import secrets
import time
from collections.abc import Callable
from threading import Lock
from uuid import UUID

from app.answers.contracts import AnswerTurn, CautiousAnswer
from app.queries.contracts import DeclinedPlan


class PendingAnswerUnavailable(Exception):
    """Unknown, expired, consumed, or inaccessible handle."""


class PendingAnswerCapacity(Exception):
    """All pending slots are occupied; existing approvals are preserved."""


class PendingAnswers:
    def __init__(
        self,
        *,
        ttl_seconds: int = 300,
        capacity: int = 128,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or capacity <= 0:
            raise ValueError("Pending answer bounds must be positive")
        self.ttl_seconds = ttl_seconds
        self._capacity = capacity
        self._clock = clock
        self._lock = Lock()
        self._entries: dict[str, tuple[float, AnswerTurn]] = {}

    def add(self, turn: AnswerTurn) -> str:
        # Copy/revalidate so mutation of a caller's object cannot change the retained plan.
        turn = AnswerTurn.model_validate_json(turn.model_dump_json())
        query, outcome = turn.request.query, turn.response.outcome
        if (
            query.scope_status != "awaiting_confirmation"
            or isinstance(query.plan, DeclinedPlan)
            or not isinstance(outcome, CautiousAnswer)
            or outcome.reason != "awaiting_confirmation"
        ):
            raise ValueError("Only pending scope can be retained")
        with self._lock:
            now = self._clock()
            self._entries = {k: v for k, v in self._entries.items() if v[0] > now}
            if len(self._entries) >= self._capacity:
                raise PendingAnswerCapacity
            token = secrets.token_urlsafe(32)
            self._entries[token] = (now + self.ttl_seconds, turn)
            return token

    def take(self, token: str, workspace_id: UUID) -> AnswerTurn:
        """Atomically consume before execution, including when execution later fails."""
        with self._lock:
            entry = self._entries.get(token)
            if entry is None:
                raise PendingAnswerUnavailable
            expires, turn = entry
            if expires <= self._clock():
                del self._entries[token]
                raise PendingAnswerUnavailable
            if turn.request.query.context.workspace_id != workspace_id:
                raise PendingAnswerUnavailable
            del self._entries[token]
            return turn

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
