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
    tool. A request to check, search, recall, save, or forget/delete
    information in memory -- on its own, with nothing else asked --
    should always be left with no tasks: return {"tasks": []} and let
    the assistant handle it conversationally (it has its own memory
    tools, including delete_memory). Only give a memory operation its
    own task when it is genuinely one dependency-linked step inside a
    larger multi-step plan the user explicitly asked for -- and even
    then, phrase it as "Search memory for X" or "Delete the memory key
    X", never "Read memory.json".

18. If you can answer the request accurately using only your own
    reasoning or general knowledge -- no lookup of real-time or
    external information, no code execution, no file involved --
    return {"tasks": []} and let the assistant answer directly. This
    includes simple arithmetic, definitions, general facts, and
    opinions. Do NOT invent a file-based or tool-based task just to
    "show the work" for something you can just answer. This does not
    apply when the request needs current/real-world data (weather,
    exchange rates, a place's coordinates) or needs something actually
    executed -- those still need a plan so the right tool gets called.

19. "Searching", "looking up", "checking", "retrieving", or "finding"
    information for the FIRST time is task_type "execution", never
    "verification" -- it produces new information, it doesn't check an
    existing result against an expectation. task_type "verification"
    is reserved exclusively for a task whose entire job is comparing a
    PRIOR task's output against expected_output. Concretely: the first
    task in any plan can never be "verification" (there is nothing
    before it to verify yet), and a plan should usually alternate
    execution -> verification -> execution -> verification, not have
    several verification tasks in a row. When in doubt about which
    type a task is, ask: "does this task produce a new answer, or does
    it check a previous step's answer against a known value?" -- the
    former is always "execution".

20. A request to set, check, or list reminders -- on its own, with
    nothing else asked -- should always be left with no tasks: return
    {"tasks": []} and let the assistant handle it conversationally (it
    has its own set_reminder/list_reminders tools, and can resolve
    relative times like "in 10 minutes" itself). Only give it its own
    task when it is genuinely one dependency-linked step inside a
    larger multi-step plan the user explicitly asked for.

21. create_video, run_command, and post_to_youtube are slow,
    resource-heavy, and/or externally-visible -- create_video takes
    several minutes of local compute and writes real files, run_command
    executes an arbitrary shell command, post_to_youtube publishes
    publicly. Never create a task using any of these three unless the
    conversation makes it unmistakable the user wants it actually done
    now, not just discussed or brainstormed. A message that merely
    mentions, imagines, or is emotionally exploring a topic ("I wish
    someone would explain X", "I don't know how to talk to my husband
    about his behavior") is a request for a conversational answer, NOT
    an instruction to produce a video, run a command, or publish
    anything -- return {"tasks": []} for these every time, even if the
    topic resembles a video you've made before. Only plan one of these
    three tools when the user has given a clear, specific go-ahead --
    either directly in this message ("make a 30 second video about X"),
    or in direct response to the assistant's own confirmation question
    from a prior turn shown in the conversation history above.

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
    Render prior chat turns as plain text. A compacted summary entry
    (see compactor.py) always survives regardless of max_turns -- only
    the regular, un-compacted turns get capped to the most recent
    ones, so a long session doesn't grow the prompt unbounded while
    still keeping the condensed gist of everything before that.
    Shared between the planner and the responder.
    """
    if not history:
        return ""

    summary_entries = [turn for turn in history if "summary" in turn]
    regular_entries = [turn for turn in history if "summary" not in turn]

    lines = ["Conversation so far:"]

    for turn in summary_entries:
        lines.append(f"Summary of earlier conversation: {turn['summary']}")

    for turn in regular_entries[-max_turns:]:
        lines.append(f"- User asked: {turn['user_input']}")
        lines.append(f"  Result: {turn['status']}")

        if turn.get("reply"):
            lines.append(f"  Assistant replied: {turn['reply']}")

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