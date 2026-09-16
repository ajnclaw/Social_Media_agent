import json
import logging
import time
import uuid
from datetime import datetime, timezone

from config import PROJECT_ROOT


LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _new_run_id():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


class RunLogger:
    """
    Emits human-readable lines to the console via the standard logging
    module, and builds a structured JSON trace of the run that gets
    written to logs/<run_id>.json once the run finishes.
    """

    def __init__(self, user_input):
        self.run_id = _new_run_id()
        self.started_at = time.time()

        self.logger = logging.getLogger(f"agent.{self.run_id}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"
                )
            )
            self.logger.addHandler(handler)

        self.trace = {
            "run_id": self.run_id,
            "user_input": user_input,
            "plan": [],
            "events": [],
            "tasks": [],
            "status": None,
            "duration_seconds": None,
        }

    def log_plan(self, tasks):
        self.trace["plan"] = [
            {
                "step": task.step,
                "objective": task.objective,
                "task_type": task.task_type,
                "depends_on": task.depends_on,
                "expected_output": task.expected_output,
            }
            for task in tasks
        ]

        self.logger.info("Plan created with %d task(s).", len(tasks))

        for task in tasks:
            self.logger.info(
                "  Task %s: %s (type=%s, depends_on=%s)",
                task.step, task.objective, task.task_type, task.depends_on,
            )

    def log_event(self, event_type, message, level="info", **fields):
        log_fn = getattr(self.logger, level, self.logger.info)
        log_fn(message)

        self.trace["events"].append({
            "type": event_type,
            "elapsed_seconds": round(time.time() - self.started_at, 3),
            "message": message,
            **fields,
        })

    def log_tool_call(self, tool_name, arguments, result):
        self.logger.info(
            "[Tool] %s(%s) -> success=%s",
            tool_name, arguments, result.get("success"),
        )

        self.trace["events"].append({
            "type": "tool_call",
            "elapsed_seconds": round(time.time() - self.started_at, 3),
            "tool_name": tool_name,
            "arguments": arguments,
            "success": result.get("success"),
            "output": result.get("output"),
            "error": result.get("error"),
            "denied": result.get("denied", False),
        })

    def log_llm_call(self, component, model, response):
        message = response.message
        content = message.content or ""

        tool_calls = [
            {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            }
            for tool_call in (message.tool_calls or [])
        ]

        preview = content if len(content) <= 300 else content[:300] + "..."
        tool_call_names = [tc["name"] for tc in tool_calls]

        self.logger.info(
            "[LLM/%s] %s -> %s%s",
            component,
            model,
            preview or "(no content)",
            f" tool_calls={tool_call_names}" if tool_calls else "",
        )

        self.trace["events"].append({
            "type": "llm_call",
            "elapsed_seconds": round(time.time() - self.started_at, 3),
            "component": component,
            "model": model,
            "content": content,
            "tool_calls": tool_calls,
        })

    def finalize(self, state):
        self.trace["status"] = state.status
        self.trace["duration_seconds"] = round(time.time() - self.started_at, 2)
        self.trace["tasks"] = [
            {
                "step": task.step,
                "status": task.status,
                "retries": task.retries,
                "failure_type": task.failure_type,
                "failure_history": task.failure_history,
            }
            for task in state.tasks
        ]

        path = LOG_DIR / f"{self.run_id}.json"
        path.write_text(
            json.dumps(self.trace, indent=2, default=str),
            encoding="utf-8",
        )

        self.logger.info(
            "Run finished with status '%s'. Trace written to %s",
            state.status, path,
        )

        return path