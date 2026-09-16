import json

from config import DEFAULT_MODEL
from task import Task

import ollama


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


class Planner:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model

    def plan(self, user_input):
        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
        )

        content = response["message"]["content"]


        data = json.loads(content)

        tasks = []

        for item in data["tasks"]:
            task = Task(
                step=item["step"],
                objective=item["objective"],
                depends_on=item.get("depends_on", []),
                expected_output=item.get("expected_output"),
                task_type=item.get("task_type", "execution"),
            )

            tasks.append(task)

        return tasks