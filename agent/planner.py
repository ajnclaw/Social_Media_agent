import json

from .config import DEFAULT_MODEL
from .task import Task

from .llm_client import chat


SYSTEM_PROMPT = """
You are a task planner for an AI agent.

Break the user's request into clear, executable tasks.

Return ONLY valid JSON.
Do not use markdown.
Do not include explanations.

Each task must contain:

- step
- objective
- depends_on
- expected_output
- task_type

task_type must be one of:

- "execution"
- "verification"

Rules:

1. Execution tasks perform actual operations.
2. Verification tasks verify the result of a previous task.
3. Verification tasks should depend on the task they verify.
4. Use expected_output when an exact result is known.
5. Do not invent expected outputs.
6. Verification tasks must have an expected_output.
7. File creation tasks may have expected_output set to null.
8. Tasks must be independently understandable.
9. Use dependencies whenever one task requires the result of another.

10. Do not create, modify, overwrite, or delete files unless the
    user explicitly requested that operation.

11. If the user asks you to inspect, run, test, or verify an existing
    file or resource, assume that the resource already exists.

12. Never add a setup or preparation task merely to make a later
    task succeed.

13. Preserve the existing environment when the user asks to test,
    execute, inspect, or verify something.

14. Only create or modify something when that operation is explicitly
    part of the user's request.

15. A verification task must depend on an actual execution task that
    exists earlier in this same plan. Never give a verification task
    an empty depends_on, and never make a task depend on its own step
    number -- a task cannot verify itself.

16. If the request is a question you cannot answer by performing a
    real operation (e.g. a question about the user, or something you
    have no way to look up or execute), do not invent a verification
    task with nothing behind it. Return {"tasks": []} instead.

17. The agent's persistent memory is NOT a regular file, even though
    it happens to be stored as one. Never create a task that reads
    "memory.json" or treats memory as something to open with a file
    tool. A request to check, search, or recall saved information
    should either be left with no tasks (return {"tasks": []} and let
    the assistant handle it conversationally) or, if it's genuinely
    part of a larger operation, phrased as an objective like "Search
    memory for X" -- never "Read memory.json".

Example:

{
  "tasks": [
    {
      "step": 1,
      "objective": "Create hello.py containing exactly print(\"hello world\")",
      "depends_on": [],
      "expected_output": null,
      "task_type": "execution"
    },
    {
      "step": 2,
      "objective": "Execute hello.py",
      "depends_on": [1],
      "expected_output": "hello world",
      "task_type": "execution"
    },
    {
      "step": 3,
      "objective": "Verify that the output from Task 2 matches the expected output",
      "depends_on": [2],
      "expected_output": "hello world",
      "task_type": "verification"
    }
  ]
}
"""


def build_tasks(data):
    """
    Convert the planner's parsed JSON response into Task objects.
    Tolerates a bare list of tasks (no {"tasks": [...]} wrapper) and
    a missing "step" field -- both of which a small local model
    occasionally produces despite the system prompt's schema.
    """
    tasks_data = data if isinstance(data, list) else data.get("tasks", [])

    tasks = []

    for index, item in enumerate(tasks_data, start=1):
        task = Task(
            step=item.get("step", index),
            objective=item["objective"],
            depends_on=item.get("depends_on", []),
            expected_output=item.get("expected_output"),
            task_type=item.get("task_type", "execution"),
        )

        tasks.append(task)

    return tasks


def find_self_dependent_tasks(tasks):
    """
    Return any tasks whose depends_on includes their own step number.
    The scheduler can never mark a self-dependent task ready (it waits
    forever on its own success), so this deadlocks silently -- caught
    here as an explicit planning failure instead. This only catches a
    direct self-reference (A depends on A), not longer cycles
    (A depends on B depends on A); full cycle detection is a bigger
    fix for if that's ever actually observed.
    """
    return [task for task in tasks if task.step in task.depends_on]


MAX_HISTORY_TURNS = 5


def format_history(history, max_turns=MAX_HISTORY_TURNS):
    """
    Render a bounded window of prior chat turns as plain text, capped
    to the most recent turns so a long chat session doesn't grow the
    prompt unbounded. Shared between the planner and the responder.
    """
    if not history:
        return ""

    lines = ["Conversation so far:"]

    for turn in history[-max_turns:]:
        lines.append(f"- User asked: {turn['user_input']}")
        lines.append(f"  Result: {turn['status']}")

        for task_line in turn.get("tasks", []):
            lines.append(f"    {task_line}")

    return "\n".join(lines)


def build_prompt_with_history(user_input, history=None):
    """
    Combine the new request with a bounded window of prior chat turns,
    so the planner can resolve references like "run it" or "that file"
    to something a previous turn created.
    """
    history_text = format_history(history)

    if not history_text:
        return user_input

    return (
        f"{history_text}\n\n"
        f"New request: {user_input}\n\n"
        "Only plan for the new request above. Use the conversation "
        "history only to resolve references like 'it' or 'that file', "
        "and to know what already exists from previous turns."
    )


class Planner:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def plan(self, user_input, history=None):
        prompt = build_prompt_with_history(user_input, history)

        response = chat(
            "planner",
            self.model,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            logger=self.logger,
        )

        content = response["message"]["content"]
        data = json.loads(content)

        return build_tasks(data)