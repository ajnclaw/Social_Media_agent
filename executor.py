from config import DEFAULT_MAX_ITERATIONS, DEFAULT_MODEL
from tools import TOOL_SCHEMAS, ToolManager
from llm_client import chat


SYSTEM_PROMPT = """
You are an AI task executor.

Your job is to actually perform the assigned task.

CRITICAL RULES:

- If the task requires creating, modifying, reading, executing,
  searching, or otherwise operating on something, you MUST use
  the appropriate tool.
- Do NOT answer with an explanation instead of performing the operation.
- Do NOT invent results.
- Do NOT claim success unless the required operation was actually
  performed and confirmed by a tool result.
- Use the available tools to obtain real evidence.
- You may call multiple tools.
- If a tool fails, analyze the failure and try to recover when possible.
- Never substitute a different implementation for the requested one.
- Preserve exact requirements from the task.
"""

class Executor:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.tool_manager = ToolManager()
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def execute(
        self,
        task,
        context=None,
        max_iterations=DEFAULT_MAX_ITERATIONS,
    ):
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": self._build_task_prompt(
                    task,
                    context,
                ),
            },
        ]

        last_tool_output = None

        for iteration in range(max_iterations):
            response = chat(
                "executor",
                self.model,
                messages,
                tools=TOOL_SCHEMAS,
                logger=self.logger,
            )

            messages.append(response.message)

            print(f"\n[Executor iteration {iteration + 1}]")

            if response.message.content:
                print(response.message.content)

            tool_calls = response.message.tool_calls

            if not tool_calls:
                content = response.message.content or ""

                if self._requires_tool(task) and last_tool_output is None:
                    return {
                        "success": False,
                        "output": content,
                        "error": (
                            "Task requires an operation, "
                            "but the executor did not call a tool."
                        ),
                    }

                return {
                    "success": True,
                    "output": (
                        last_tool_output
                        if last_tool_output is not None
                        else content
                    ),
                }

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                arguments = tool_call.function.arguments

                print(
                    f"[Tool call] "
                    f"{tool_name}({arguments})"
                )

                result = self.tool_manager.execute(
                    tool_name,
                    arguments,
                )
                print(f"[Tool result] {result}")

                if result.get("denied"):
                    return {
                        "success": False,
                        "output": None,
                        "error": result.get("error"),
                        "denied": True,
                    }



                if result.get("success"):
                    last_tool_output = result.get("output")

                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": str(result),
                    }
                )

        return {
            "success": False,
            "error": "Maximum executor iterations reached.",
        }

    def _build_task_prompt(self, task, context):
        prompt = f"""
    Task:

    {task.objective}
    """

        if context:
            prompt += """

    Results from previous tasks:

    """

            for step, result in context.items():
                prompt += f"""
    Task {step} result:
    {result}
    """

        prompt += """

    Complete the task using the available tools.

    Important:
    - Do not merely describe a tool call.
    - If an operation is required, actually call the tool.
    - Do not claim success unless the required operation has actually been performed.
    - If you need information from a previous task, use the provided task result.
    """

        return prompt

    def _requires_tool(self, task):
        keywords = [
            "create",
            "write",
            "modify",
            "edit",
            "read",
            "execute",
            "run",
            "delete",
            "save",
            "search",
        ]

        objective = task.objective.lower()

        return any(
            keyword in objective
            for keyword in keywords
        )