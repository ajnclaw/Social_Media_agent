# task.py


TASK_READY = "ready"
TASK_RUNNING = "running"
TASK_SUCCESS = "success"
TASK_FAILED = "failed"
TASK_DENIED = "denied"
TASK_BLOCKED = "blocked"

FAILURE_TRANSIENT = "transient"
FAILURE_RECOVERABLE = "recoverable"
FAILURE_PERMANENT = "permanent"


class Task:
    def __init__(
        self,
        step,
        objective,
        depends_on=None,
        expected_output=None,
        task_type="execution",
        max_retries=2,
    ):
        self.step = step
        self.objective = objective
        self.depends_on = depends_on or []
        self.expected_output = expected_output
        self.task_type = task_type

        self.status = TASK_READY
        self.result = None
        self.error = None
        self.retries = 0
        self.max_retries = max_retries
        self.failure_type = None
        self.failure_history = []

    def __repr__(self):
        return (
            f"Task("
            f"step={self.step}, "
            f"type={self.task_type}, "
            f"status={self.status}, "
            f"objective={self.objective!r}, "
            f"expected_output={self.expected_output!r}"
            f")"
        )