from datetime import datetime

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

If the user corrects a fact ("actually I live in Delhi now"), that's
still save_memory with the same key -- overwriting is how a correction
is stored, not a delete. Only call delete_memory when the user
explicitly asks to forget, delete, or remove something -- e.g. "forget
my old address" or "delete what you know about my weight". If you
don't already know the exact key it was saved under, search_memory
first rather than guessing one.

When the user asks to be reminded, alerted, or notified about
something -- at a specific time, or after a delay like "in 10 minutes"
-- call set_reminder. This actually schedules a real notification, so
only call it when they're clearly asking to be reminded, not for every
future-tense thing they mention. The current date and time are given
below; resolve any relative time ("in 10 minutes", "tomorrow at 9am")
against it into an absolute ISO 8601 datetime yourself before calling
the tool -- never pass the relative phrase through as-is. Use
list_reminders if the user asks what reminders they have, or before
setting a new one that might duplicate an existing one.

Do not claim you looked something up unless you actually called a
tool and got a real result back.

Recent conversation history may be included for context; use it only
to understand what was discussed, not as something to repeat back.
"""

# Read-only, plus call_api, save_memory, and the reminder tools. No
# file/shell mutation here -- that's the Executor's job, gated behind
# its own approval flow. save_memory/set_reminder are deliberate
# exceptions: remembering a fact or scheduling a reminder the user
# explicitly asked for is core conversational behavior. Both are still
# routed through ToolManager like everything else, so the approval
# policy (AUTO_APPROVED_TOOLS in approval.py) still applies.
RESPONDER_TOOL_NAMES = {
    "list_files",
    "read_file",
    "search_memory",
    "save_memory",
    "delete_memory",
    "set_reminder",
    "list_reminders",
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

        current_time = datetime.now().astimezone().isoformat()

        messages = [
            {
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\n\nCurrent date and time: {current_time}",
            },
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
