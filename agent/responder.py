from .config import DEFAULT_MODEL
from .llm_client import chat
from .planner import format_history


SYSTEM_PROMPT = """
You are a helpful AI assistant having a conversation with the user.

Respond naturally and conversationally, in plain text -- not JSON.
Keep your response concise and directly relevant to what the user said.

Recent conversation history may be included for context; use it only
to understand what was discussed, not as something to repeat back.
"""


class Responder:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def respond(self, user_input, history=None):
        history_text = format_history(history)

        if history_text:
            prompt = f"{history_text}\n\nNew message: {user_input}"
        else:
            prompt = user_input

        response = chat(
            "responder",
            self.model,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            logger=self.logger,
        )

        return response["message"]["content"]
