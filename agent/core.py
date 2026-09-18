from .planner import Planner, find_self_dependent_tasks
from .scheduler import Scheduler
from .executor import Executor
from .evaluator import Evaluator
from .state import AgentState
from .task import TASK_SUCCESS, TASK_FAILED
from .recovery import Recovery
from .failure import FailureClassifier
from .retry import RetryPolicy
from .logger import RunLogger
from .responder import Responder


class Agent:
    def __init__(self):
        self.planner = Planner()
        self.scheduler = Scheduler()
        self.executor = Executor()
        self.evaluator = Evaluator()
        self.recovery = Recovery()
        self.failure_classifier = FailureClassifier()
        self.retry_policy = RetryPolicy()
        self.responder = Responder()

    def run(self, user_input, history=None):
        state = AgentState(user_input)
        run_logger = RunLogger(user_input)

        self.planner.set_logger(run_logger)
        self.executor.set_logger(run_logger)
        self.executor.tool_manager.set_logger(run_logger)
        self.recovery.set_logger(run_logger)
        self.recovery.tool_manager.set_logger(run_logger)
        self.responder.set_logger(run_logger)
        self.responder.tool_manager.set_logger(run_logger)

        try:
            tasks = self.planner.plan(user_input, history=history)
        except Exception as exc:
            run_logger.log_event(
                "planning_failed",
                f"Planning failed: {exc}",
                level="error",
            )

            state.status = "failed"
            state.trace_path = run_logger.finalize(state)
            return state

        state.tasks = tasks

        run_logger.log_plan(tasks)

        if not tasks:
            reply = self.responder.respond(user_input, history=history)

            run_logger.log_event(
                "conversational_reply",
                reply,
            )

            state.reply = reply
            state.status = "completed"
            state.trace_path = run_logger.finalize(state)
            return state

        self_dependent = find_self_dependent_tasks(tasks)

        if self_dependent:
            steps = ", ".join(str(task.step) for task in self_dependent)

            run_logger.log_event(
                "invalid_plan",
                f"Planner produced task(s) that depend on themselves: {steps}",
                level="error",
            )

            state.status = "failed"
            state.trace_path = run_logger.finalize(state)
            return state

        while self.scheduler.has_unfinished_tasks(state.tasks):
            ready_tasks = self.scheduler.get_ready_tasks(state.tasks)

            if not ready_tasks:
                run_logger.log_event(
                    "no_ready_tasks",
                    "No ready tasks remain.",
                    level="warning",
                )
                break

            for task in ready_tasks:
                run_logger.log_event(
                    "task_start",
                    f"--- Executing Task {task.step} ---",
                    step=task.step,
                )

                state.current_task = task
                self.scheduler.mark_running(task)

                if task.task_type == "verification":
                    dependency_step = (
                        task.depends_on[-1] if task.depends_on else "unknown"
                    )

                    run_logger.log_event(
                        "verification_start",
                        f"[Verification] Checking result from Task {dependency_step}",
                        step=task.step,
                    )

                    evaluation = self.evaluator.verify(
                        task,
                        context=state.task_results,
                    )

                else:
                    try:
                        result = self.executor.execute(
                            task,
                            context=state.task_results,
                        )
                    except Exception as exc:
                        result = {
                            "success": False,
                            "output": None,
                            "error": str(exc),
                        }

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

                    run_logger.log_event(
                        "task_success",
                        f"Task {task.step} completed.",
                        step=task.step,
                        output=evaluation.get("output"),
                    )

                else:
                    error = evaluation.get("error")

                    run_logger.log_event(
                        "task_failure",
                        f"Task {task.step} failed: {error}",
                        level="warning",
                        step=task.step,
                        error=error,
                    )

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

                    action = self.retry_policy.action(
                        task,
                        failure_type,
                    )

                    should_retry = self.retry_policy.should_retry(
                        task,
                        failure_type,
                    )

                    run_logger.log_event(
                        "failure_classified",
                        f"[Failure] Type: {failure_type}. "
                        f"Action: {action}, should_retry: {should_retry}",
                        step=task.step,
                        failure_type=failure_type,
                        action=action,
                        should_retry=should_retry,
                    )

                    if not should_retry:
                        run_logger.log_event(
                            "give_up",
                            f"[Failure] Task {task.step} will not be retried.",
                            level="error",
                            step=task.step,
                        )

                        self.scheduler.mark_failed(task, error)

                        state.status = "failed"
                        state.trace_path = run_logger.finalize(state)
                        return state

                    task.retries += 1

                    run_logger.log_event(
                        "retry_attempt",
                        f"[Retry] Attempt {task.retries}/{task.max_retries}",
                        step=task.step,
                        attempt=task.retries,
                    )
                    self.retry_policy.wait(task, failure_type)

                    if action == "retry":
                        run_logger.log_event(
                            "retry_transient",
                            "[Retry] Transient failure. Retrying task directly.",
                            step=task.step,
                        )

                        self.scheduler.reset_task(task)
                        continue

                    if action == "recover":
                        run_logger.log_event(
                            "recovery_start",
                            "[Recovery] Recoverable failure. Starting recovery.",
                            step=task.step,
                        )

                        dependency_task = None

                        if task.depends_on:
                            dependency_task = self.scheduler.get_task(
                                state.tasks,
                                task.depends_on[-1],
                            )

                        try:
                            recovery_result = self.recovery.repair(
                                task,
                                error,
                                context=state.task_results,
                                failed_dependency=dependency_task,
                            )
                        except Exception as exc:
                            recovery_result = {
                                "success": False,
                                "output": None,
                                "error": str(exc),
                            }

                        if recovery_result.get("success"):
                            run_logger.log_event(
                                "recovery_success",
                                "[Recovery] Repair completed.",
                                step=task.step,
                            )

                            self.scheduler.reset_task_chain(
                                state.tasks,
                                task,
                            )

                            continue

                        run_logger.log_event(
                            "recovery_failure",
                            "[Recovery] Unable to repair the problem.",
                            level="error",
                            step=task.step,
                            error=recovery_result.get("error"),
                        )

                        self.scheduler.mark_failed(
                            task,
                            recovery_result.get("error"),
                        )

                        state.status = "failed"
                        state.trace_path = run_logger.finalize(state)
                        return state

                    run_logger.log_event(
                        "unknown_action",
                        f"[Failure] Unknown failure action: {action}",
                        level="error",
                        step=task.step,
                        action=action,
                    )

                    self.scheduler.mark_failed(task, error)

                    state.status = "failed"
                    state.trace_path = run_logger.finalize(state)
                    return state

        state.status = "completed"
        state.trace_path = run_logger.finalize(state)

        return state