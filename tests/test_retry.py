import agent.retry as retry_module
from agent.retry import RetryPolicy
from agent.task import (
    Task,
    FAILURE_TRANSIENT,
    FAILURE_RECOVERABLE,
    FAILURE_PERMANENT,
)


def make_task(retries=0, max_retries=2):
    task = Task(
        step=1,
        objective="Test task",
    )
    task.retries = retries
    task.max_retries = max_retries
    return task


def test_should_retry_false_for_permanent_failure_even_with_retries_left():
    task = make_task(retries=0, max_retries=2)

    assert RetryPolicy().should_retry(task, FAILURE_PERMANENT) is False


def test_should_retry_true_for_transient_failure_within_budget():
    task = make_task(retries=0, max_retries=2)

    assert RetryPolicy().should_retry(task, FAILURE_TRANSIENT) is True


def test_should_retry_false_for_transient_failure_once_exhausted():
    task = make_task(retries=2, max_retries=2)

    assert RetryPolicy().should_retry(task, FAILURE_TRANSIENT) is False


def test_should_retry_true_for_recoverable_failure_within_budget():
    task = make_task(retries=1, max_retries=2)

    assert RetryPolicy().should_retry(task, FAILURE_RECOVERABLE) is True


def test_should_retry_false_for_recoverable_failure_once_exhausted():
    task = make_task(retries=2, max_retries=2)

    assert RetryPolicy().should_retry(task, FAILURE_RECOVERABLE) is False


def test_action_is_retry_for_transient_failure():
    task = make_task()

    assert RetryPolicy().action(task, FAILURE_TRANSIENT) == "retry"


def test_action_is_recover_for_recoverable_failure():
    task = make_task()

    assert RetryPolicy().action(task, FAILURE_RECOVERABLE) == "recover"


def test_action_is_stop_for_permanent_failure():
    task = make_task()

    assert RetryPolicy().action(task, FAILURE_PERMANENT) == "stop"


def test_get_delay_is_zero_for_non_transient_failures():
    task = make_task(retries=1)

    assert RetryPolicy().get_delay(task, FAILURE_RECOVERABLE) == 0
    assert RetryPolicy().get_delay(task, FAILURE_PERMANENT) == 0


def test_get_delay_backs_off_exponentially_for_transient_failures():
    policy = RetryPolicy()

    assert policy.get_delay(make_task(retries=1), FAILURE_TRANSIENT) == 1
    assert policy.get_delay(make_task(retries=2), FAILURE_TRANSIENT) == 2
    assert policy.get_delay(make_task(retries=3), FAILURE_TRANSIENT) == 4
    assert policy.get_delay(make_task(retries=4), FAILURE_TRANSIENT) == 8


def test_wait_sleeps_for_computed_delay_on_transient_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(retry_module.time, "sleep", lambda seconds: calls.append(seconds))

    task = make_task(retries=1)
    RetryPolicy().wait(task, FAILURE_TRANSIENT)

    assert calls == [1]


def test_wait_does_not_sleep_for_non_transient_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(retry_module.time, "sleep", lambda seconds: calls.append(seconds))

    task = make_task(retries=1)
    RetryPolicy().wait(task, FAILURE_RECOVERABLE)

    assert calls == []
