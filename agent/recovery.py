from .config import DEFAULT_MODEL
from .tools import TOOL_SCHEMAS, ToolManager
from .llm_client import chat


SYSTEM_PROMPT = """
You are an AI agent recovery system.

Your job is to REPAIR a failed task.

A task has already been executed and then failed verification.

You must analyze:

1. What was expected.
2. What actually happened.
3. What artifact, file, command, or operation caused the failure.
4. What concrete change is required to fix it.

IMPORTANT:

- Do NOT merely explain the problem.
- Do NOT just inspect the directory.
- Do NOT call list_files unless you genuinely need it to locate
  the specific artifact involved in the failure.
- You MUST inspect the relevant artifact when necessary.
- If a file is responsible for the failure, read that file.
- If the file contains incorrect content, edit that file.
- Do not modify unrelated files.
- After identifying the problem, perform the actual repair using tools.
- Do not claim that a repair happened unless an appropriate
  modification/repair tool actually succeeded.

For example:

Expected output:
hello world

Actual output:
goodbye world

If the task runs hello.py, you should:

1. Read hello.py.
2. Determine why it produces goodbye world.
3. Edit hello.py so it produces hello world.
4. Confirm the edit operation succeeded.

Do NOT simply say that hello.py should be changed.
Actually change it.
"""


class Recovery:

    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.tool_manager = ToolManager()
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def repair(
        self,
        task,
        error,
        context=None,
        failed_dependency=None,
    ):
        prompt = self._build_prompt(
            task,
            error,
            context,
            failed_dependency,
        )

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        repair_performed = False
        last_tool_output = None

        for iteration in range(5):

            response = chat(
                "recovery",
                self.model,
                messages,
                tools=TOOL_SCHEMAS,
                logger=self.logger,
            )

            messages.append(response.message)

            print(
                f"\n[Recovery iteration {iteration + 1}]"
            )

            if response.message.content:
                print(response.message.content)

            tool_calls = response.message.tool_calls

            if not tool_calls:

                if repair_performed:
                    return {
                        "success": True,
                        "output": last_tool_output,
                        "error": None,
                    }

                return {
                    "success": False,
                    "output": response.message.content or "",
                    "error": (
                        "Recovery stopped without performing "
                        "a repair."
                    ),
                }

            for tool_call in tool_calls:

                tool_name = tool_call.function.name
                arguments = tool_call.function.arguments

                print(
                    f"[Recovery tool call] "
                    f"{tool_name}({arguments})"
                )

                result = self.tool_manager.execute(
                    tool_name,
                    arguments,
                )

                print(
                    f"[Recovery tool result] {result}"
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": str(result),
                    }
                )

                # Only actual modification tools count
                # as a repair.
                if (
                    result.get("success")
                    and tool_name in {
                        "write_file",
                        "edit_file",
                        "create_directory",
                    }
                ):
                    repair_performed = True
                    last_tool_output = result.get("output")

        return {
            "success": False,
            "output": last_tool_output,
            "error": (
                "Recovery reached maximum iterations "
                "without completing a repair."
            ),
        }

    def _build_prompt(
        self,
        task,
        error,
        context,
        failed_dependency=None,
    ):

        prompt = f"""
A task failed verification.

FAILED TASK:

{task.objective}

FAILURE:

{error}
"""

        if failed_dependency:

            prompt += f"""
TASK THAT PRODUCED THE FAILED RESULT:

Task {failed_dependency.step}

Task objective:

{failed_dependency.objective}
"""

        prompt += """
PREVIOUS TASK RESULTS:
"""

        if context:

            for step, result in context.items():

                prompt += f"""
Task {step} result:

{result}
"""

        prompt += """
Your goal is to repair the underlying cause of the failure.

Do not just describe the solution.

Use the available tools to perform the repair.

For this failure:

1. Identify the artifact, file, or operation
   that produced the incorrect result.

2. Inspect that artifact using the appropriate tool.

3. Determine the actual cause of the failure.

4. If the artifact is incorrect, modify it.

5. Do not modify unrelated files.

6. Only finish after an actual repair operation
   has succeeded.

For example, if:

Expected output:
hello world

Actual output:
goodbye world

and the failed dependency says:

Task objective:
Run hello.py

then inspect hello.py.

If hello.py contains:

print("goodbye world")

change it so that it produces:

hello world

Do NOT merely explain what should be changed.

Actually perform the repair using the available tools.
"""

        return prompt