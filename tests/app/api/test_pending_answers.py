from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.api.pending_answers import PendingAnswerCapacity, PendingAnswers, PendingAnswerUnavailable
from tests.app.answers.test_service import subject_for
from tests.app.answers.test_validation import change_request, request_for


def pending_turn():
    request = change_request(
        request_for("q1-positive-unrelated-and-deduplicated"),
        lambda q: q.update(scope_status="awaiting_confirmation", response=None),
    )
    service, _ = subject_for(request)
    return service.ask(request.query.context, request.question)


def test_confirmation_is_atomic_and_one_use():
    store, turn = PendingAnswers(), pending_turn()
    token = store.add(turn)

    def take(_):
        try:
            return store.take(token, turn.request.query.context.workspace_id)
        except PendingAnswerUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(take, range(16)))
    assert sum(result is not None for result in results) == 1
    assert next(result for result in results if result is not None) == turn


def test_capacity_expiry_and_workspace_isolation():
    clock = Mock(return_value=0)
    store, turn = PendingAnswers(capacity=1, ttl_seconds=5, clock=clock), pending_turn()
    token = store.add(turn)
    with pytest.raises(PendingAnswerCapacity):
        store.add(turn)
    with pytest.raises(PendingAnswerUnavailable):
        store.take(token, uuid4())
    assert store.take(token, turn.request.query.context.workspace_id) == turn
    token = store.add(turn)
    clock.return_value = 5
    with pytest.raises(PendingAnswerUnavailable):
        store.take(token, turn.request.query.context.workspace_id)
    store.add(turn)
    clock.return_value = 10
    # add also prunes abandoned expired entries without eviction of live entries.
    token = store.add(turn)
    store.clear()
    with pytest.raises(PendingAnswerUnavailable):
        store.take(token, turn.request.query.context.workspace_id)


def test_store_copies_and_rejects_nonpending_turns():
    store, turn = PendingAnswers(), pending_turn()
    token = store.add(turn)
    retained = store.take(token, turn.request.query.context.workspace_id)
    assert retained == turn and retained is not turn
    assert retained.request.query.plan is not turn.request.query.plan
    request = request_for()
    service, _ = subject_for(request)
    with pytest.raises(ValueError, match="pending scope"):
        store.add(service.ask(request.query.context, request.question))


@pytest.mark.parametrize("bounds", [{"capacity": 0}, {"ttl_seconds": 0}])
def test_invalid_store_bounds(bounds):
    with pytest.raises(ValueError):
        PendingAnswers(**bounds)
