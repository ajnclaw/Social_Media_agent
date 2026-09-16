from task import (
    TASK_READY,
    TASK_RUNNING,
    TASK_SUCCESS,
    TASK_FAILED,
    TASK_DENIED,
)


class Scheduler:

    def get_task(self, tasks, step):

        for task in tasks:

            if task.step == step:
                return task

        return None

    def get_ready_tasks(self, tasks):

        ready = []

        for task in tasks:

            if task.status != TASK_READY:
                continue

            dependencies_satisfied = all(
                self.get_task(
                    tasks,
                    dependency,
                ).status == TASK_SUCCESS
                for dependency in task.depends_on
            )

            if dependencies_satisfied:
                ready.append(task)

        return ready

    def has_unfinished_tasks(self, tasks):

        return any(
            task.status in {
                TASK_READY,
                TASK_RUNNING,
            }
            for task in tasks
        )

    def mark_running(self, task):

        task.status = TASK_RUNNING

    def mark_success(self, task, result=None):

        task.status = TASK_SUCCESS
        task.result = result

    def mark_failed(self, task, error=None):

        task.status = TASK_FAILED
        task.error = error

    def reset_task(self, task):

        task.status = TASK_READY
        task.result = None
        task.error = None

    def reset_task_chain(self, tasks, task):
        """
        Reset the failed task and its immediate dependencies so the
        scheduler re-runs them with fresh data. Does NOT walk further
        back up the graph: Recovery repairs the underlying artifact
        directly, so re-running an upstream creation task would just
        overwrite that repair with its original, now-stale instructions.
        """

        self.reset_task(task)

        for dependency_step in task.depends_on:

            dependency = self.get_task(
                tasks,
                dependency_step,
            )

            if dependency:

                self.reset_task(dependency)

    def mark_denied(self, task, error=None):
        task.status = TASK_DENIED
        task.error = error