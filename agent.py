from planner import Planner
from scheduler import Scheduler
from executor import Executor
from evaluator import Evaluator
from state import AgentState
from task import TASK_SUCCESS, TASK_FAILED
from recovery import Recovery
from failure import FailureClassifier
from retry import RetryPolicy


class Agent:
    def __init__(self):
        self.planner = Planner()
        self.scheduler = Scheduler()
        self.executor = Executor()
        self.evaluator = Evaluator()
        self.recovery = Recovery()
        self.failure_classifier = FailureClassifier()
        self.retry_policy = RetryPolicy()

    def run(self, user_input):
        state = AgentState(user_input)

        print("\n=== PLANNING ===")

        tasks = self.planner.plan(user_input)
        state.tasks = tasks

        for task in tasks:
            print(
                f"Task {task.step}: "
                f"{task.objective} "
                f"(type={task.task_type}, "
                f"depends_on={task.depends_on})"
            )

        print("\n=== EXECUTION ===")

        while self.scheduler.has_unfinished_tasks(state.tasks):
            ready_tasks = self.scheduler.get_ready_tasks(
                state.tasks
            )

            if not ready_tasks:
                print("No ready tasks remain.")
                break

            for task in ready_tasks:
                print(
                    f"\n--- Executing Task {task.step} ---"
                )

                state.current_task = task
                self.scheduler.mark_running(task)

                if task.task_type == "verification":

                    print(
                        f"[Verification] Checking result from "
                        f"Task {task.depends_on[-1]}"
                    )

                    evaluation = self.evaluator.verify(
                        task,
                        context=state.task_results,
                    )

                else:

                    result = self.executor.execute(
                        task,
                        context=state.task_results,
                    )

                    evaluation = self.evaluator.evaluate(
                        task,
                        result,
                        state.task_results,
                    )

            if evaluation.get("success"):
                self.scheduler.mark_success(
                    task,
                    evaluation.get("output"),
                )

                state.add_task_result(
                    task,
                    evaluation.get("output"),
                )

                print(
                    f"Task {task.step} completed."
                )
            
            else:
                error = evaluation.get("error")

                print(
                    f"Task {task.step} failed: {error}"
                )

                # ---------------------------------
                # Classify the failure
                # ---------------------------------

                failure_type = self.failure_classifier.classify(
                    error,
                    task,
                )

                task.failure_type = failure_type

                task.failure_history.append(
                    {
                        "error": error,
                        "failure_type": failure_type,
                        "retry": task.retries,
                    }
                )

                print(
                    f"[Failure] Type: {failure_type}"
                )

                # ---------------------------------
                # Decide what to do
                # ---------------------------------

                action = self.retry_policy.action(
                    task,
                    failure_type,
                )

                should_retry = self.retry_policy.should_retry(
                    task,
                    failure_type,
                )

                print(
                    f"[Retry Policy] Action: {action}, "
                    f"Should retry: {should_retry}"
                )

                if not should_retry:
                    print(
                        f"[Failure] Task {task.step} "
                        f"will not be retried."
                    )

                    self.scheduler.mark_failed(
                        task,
                        error,
                    )

                    state.status = "failed"
                    return state

                # ---------------------------------
                # Consume a retry
                # ---------------------------------

                task.retries += 1

                print(
                    f"\n[Retry] Attempt "
                    f"{task.retries}/{task.max_retries}"
                )
                self.retry_policy.wait(
                    task,
                    failure_type,
                )

                # ---------------------------------
                # TRANSIENT FAILURE
                # ---------------------------------

                if action == "retry":

                    print(
                        "[Retry] Transient failure. "
                        "Retrying task directly."
                    )

                    self.scheduler.reset_task(task)

                    continue

                # ---------------------------------
                # RECOVERABLE FAILURE
                # ---------------------------------

                if action == "recover":

                    print(
                        "[Recovery] Recoverable failure. "
                        "Starting recovery."
                    )

                    dependency_task = None

                    if task.depends_on:
                        dependency_task = self.scheduler.get_task(
                            state.tasks,
                            task.depends_on[-1],
                        )

                    recovery_result = self.recovery.repair(
                        task,
                        error,
                        context=state.task_results,
                        failed_dependency=dependency_task,
                    )

                    if recovery_result.get("success"):

                        print(
                            "[Recovery] Repair completed."
                        )

                        self.scheduler.reset_task_chain(
                            state.tasks,
                            task,
                        )

                        continue

                    print(
                        "[Recovery] Unable to repair "
                        "the problem."
                    )

                    self.scheduler.mark_failed(
                        task,
                        recovery_result.get("error"),
                    )

                    state.status = "failed"
                    return state

                # ---------------------------------
                # Unknown action
                # ---------------------------------

                print(
                    f"[Failure] Unknown failure action: "
                    f"{action}"
                )

                self.scheduler.mark_failed(
                    task,
                    error,
                )

                state.status = "failed"
                return state

        state.status = "completed"

        print("\n=== COMPLETE ===")

        return state