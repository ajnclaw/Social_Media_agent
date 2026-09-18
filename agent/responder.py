from .config import DEFAULT_MAX_ITERATIONS, DEFAULT_MODEL
from .llm_client import chat
from .planner import format_history
from .tools import TOOL_SCHEMAS, ToolManager


SYSTEM_PROMPT = """
You are a helpful AI assistant having a conversation with the user.

Respond naturally and conversationally, in plain text -- not JSON.
Keep your response concise and directly relevant to what the user said.

You have access to a small set of read-only tools (listing/reading
files, searching memory, and calling known external APIs). Use them
when they would let you give a real answer instead of guessing -- for
example, call the weather API instead of saying you have no real-time
information, if a known weather API is available to you.

Before asking the user for information, or before reaching for an
external API, call search_memory FIRST -- they may have already told
you. What the user actually told you is more trustworthy than an
approximation like IP-based geolocation, so only fall back to an
external lookup when memory has nothing relevant, and only ask the
user directly when memory has nothing and no tool can find it either.

If answering the question needs more than one saved fact (e.g. BMI
needs both height and weight), search for each fact you need -- a
single search_memory call that surfaces one relevant fact doesn't mean
the others aren't saved too. Don't stop checking after the first hit.

You can also save a fact to persistent memory when the user asks you
to remember something (e.g. "remember my location is Hisar") -- use a
short, stable key so it updates a prior fact instead of duplicating
it. Only save something when the user is clearly asking you to
remember it, not for every detail they mention in passing.

Do not claim you looked something up unless you actually called a
tool and got a real result back.

Recent conversation history may be included for context; use it only
to understand what was discussed, not as something to repeat back.
"""

# Read-only, plus call_api and save_memory. No file/shell mutation
# here -- that's the Executor's job, gated behind its own approval
# flow. save_memory is the one deliberate exception: remembering a
# fact the user asked it to remember is core conversational behavior,
# and it's still approval-gated like everything else in APPROVAL_
# REQUIRED_TOOLS, so the user sees exactly what gets saved.
RESPONDER_TOOL_NAMES = {
    "list_files",
    "read_file",
    "search_memory",
    "save_memory",
    "call_api",
}

RESPONDER_TOOL_SCHEMAS = [
    schema
    for schema in TOOL_SCHEMAS
    if schema["function"]["name"] in RESPONDER_TOOL_NAMES
]


class Responder:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.tool_manager = ToolManager()
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def respond(
        self,
        user_input,
        history=None,
        max_iterations=DEFAULT_MAX_ITERATIONS,
    ):
        history_text = format_history(history)

        if history_text:
            prompt = f"{history_text}\n\nNew message: {user_input}"
        else:
            prompt = user_input

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        for iteration in range(max_iterations):
            response = chat(
                "responder",
                self.model,
                messages,
                tools=RESPONDER_TOOL_SCHEMAS,
                logger=self.logger,
            )

            messages.append(response.message)

            tool_calls = response.message.tool_calls

            if not tool_calls:
                return response.message.content or ""

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                arguments = tool_call.function.arguments

                result = self.tool_manager.execute(tool_name, arguments)

                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": str(result),
                    }
                )

        return (
            "I wasn't able to finish looking into that -- "
            "could you rephrase or try again?"
        )
