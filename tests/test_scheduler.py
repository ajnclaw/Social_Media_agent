from scheduler import Scheduler
from task import (
    Task,
    TASK_READY,
    TASK_RUNNING,
    TASK_SUCCESS,
    TASK_FAILED,
    TASK_DENIED,
)


def make_task(step, depends_on=None, status=TASK_READY):
    task = Task(
        step=step,
        objective=f"Task {step}",
        depends_on=depends_on or [],
    )
    task.status = status
    return task


def test_get_task_returns_matching_task():
    tasks = [make_task(1), make_task(2)]
    scheduler = Scheduler()

    found = scheduler.get_task(tasks, 2)

    assert found is tasks[1]


def test_get_task_returns_none_when_missing():
    tasks = [make_task(1)]
    scheduler = Scheduler()

    assert scheduler.get_task(tasks, 99) is None


def test_task_with_no_dependencies_is_ready():
    tasks = [make_task(1)]
    scheduler = Scheduler()

    assert scheduler.get_ready_tasks(tasks) == [tasks[0]]


def test_task_blocked_until_dependency_succeeds():
    dependency = make_task(1, status=TASK_RUNNING)
    dependent = make_task(2, depends_on=[1])
    tasks = [dependency, dependent]
    scheduler = Scheduler()

    assert scheduler.get_ready_tasks(tasks) == []


def test_task_becomes_ready_once_dependency_succeeds():
    dependency = make_task(1, status=TASK_SUCCESS)
    dependent = make_task(2, depends_on=[1])
    tasks = [dependency, dependent]
    scheduler = Scheduler()

    assert scheduler.get_ready_tasks(tasks) == [dependent]


def test_non_ready_tasks_excluded_even_without_dependencies():
    tasks = [make_task(1, status=TASK_RUNNING)]
    scheduler = Scheduler()

    assert scheduler.get_ready_tasks(tasks) == []


def test_has_unfinished_tasks_true_when_ready_or_running():
    scheduler = Scheduler()

    assert scheduler.has_unfinished_tasks([make_task(1, status=TASK_READY)])
    assert scheduler.has_unfinished_tasks([make_task(1, status=TASK_RUNNING)])


def test_has_unfinished_tasks_false_when_all_terminal():
    tasks = [
        make_task(1, status=TASK_SUCCESS),
        make_task(2, status=TASK_FAILED),
    ]
    scheduler = Scheduler()

    assert scheduler.has_unfinished_tasks(tasks) is False


def test_mark_running_sets_status():
    task = make_task(1)
    Scheduler().mark_running(task)

    assert task.status == TASK_RUNNING


def test_mark_success_sets_status_and_result():
    task = make_task(1)
    Scheduler().mark_success(task, result="done")

    assert task.status == TASK_SUCCESS
    assert task.result == "done"


def test_mark_failed_sets_status_and_error():
    task = make_task(1)
    Scheduler().mark_failed(task, error="boom")

    assert task.status == TASK_FAILED
    assert task.error == "boom"


def test_mark_denied_sets_status_and_error():
    task = make_task(1)
    Scheduler().mark_denied(task, error="user declined")

    assert task.status == TASK_DENIED
    assert task.error == "user declined"


def test_reset_task_returns_to_ready_and_clears_result():
    task = make_task(1, status=TASK_FAILED)
    task.result = "stale"
    task.error = "stale error"

    Scheduler().reset_task(task)

    assert task.status == TASK_READY
    assert task.result is None
    assert task.error is None


def test_reset_task_chain_resets_task_and_its_dependencies():
    grandparent = make_task(1, status=TASK_SUCCESS)
    parent = make_task(2, depends_on=[1], status=TASK_SUCCESS)
    child = make_task(3, depends_on=[2], status=TASK_FAILED)
    tasks = [grandparent, parent, child]

    Scheduler().reset_task_chain(tasks, child)

    assert grandparent.status == TASK_READY
    assert parent.status == TASK_READY
    assert child.status == TASK_READY
