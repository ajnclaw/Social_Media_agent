import time

from .task import (
    FAILURE_TRANSIENT,
    FAILURE_RECOVERABLE,
    FAILURE_PERMANENT,
)


class RetryPolicy:

    def should_retry(self, task, failure_type):

        if failure_type == FAILURE_PERMANENT:
            return False

        if task.retries >= task.max_retries:
            return False

        if failure_type == FAILURE_TRANSIENT:
            return True

        if failure_type == FAILURE_RECOVERABLE:
            return True

        return False

    def action(self, task, failure_type):

        if failure_type == FAILURE_TRANSIENT:
            return "retry"

        if failure_type == FAILURE_RECOVERABLE:
            return "recover"

        return "stop"

    def get_delay(self, task, failure_type):

        if failure_type != FAILURE_TRANSIENT:
            return 0

        # Exponential backoff:
        #
        # retry 1 -> 1 second
        # retry 2 -> 2 seconds
        # retry 3 -> 4 seconds
        # retry 4 -> 8 seconds

        return 2 ** (task.retries - 1)

    def wait(self, task, failure_type):

        delay = self.get_delay(
            task,
            failure_type,
        )

        if delay <= 0:
            return

        print(
            f"[Retry] Waiting {delay} second(s) "
            f"before retry..."
        )

        time.sleep(delay)