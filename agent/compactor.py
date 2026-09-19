from .config import DEFAULT_MODEL
from .llm_client import chat


SYSTEM_PROMPT = """
You are summarizing an earlier part of a conversation between a user
and an AI assistant, so it can be condensed and kept in context
without keeping every message in full.

Write a concise summary (a few sentences) that preserves:
- Key facts the user stated (e.g. personal details, preferences)
- Decisions made or conclusions reached
- Anything attempted that succeeded or failed, and why

Do not include pleasantries, filler, or step-by-step narration.
Write it as plain prose, not a transcript.
"""


def build_transcript(turns):
    """
    Render a list of raw history turns as a plain user/assistant
    transcript, suitable for summarizing. Pure function, no LLM call
    -- kept separate so it's directly testable.
    """
    lines = []

    for turn in turns:
        lines.append(f"User: {turn['user_input']}")

        if turn.get("reply"):
            lines.append(f"Assistant: {turn['reply']}")
        elif turn.get("tasks"):
            lines.append("Assistant: " + "; ".join(turn["tasks"]))
        else:
            lines.append(f"Assistant: [{turn.get('status', 'completed')}]")

    return "\n".join(lines)


def summarize_transcript(transcript, model=DEFAULT_MODEL):
    response = chat(
        "compactor",
        model,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )

    return response["message"]["content"]


def compact_history(history, keep_recent=5, trigger_at=10, model=DEFAULT_MODEL):
    """
    Once there are more than trigger_at raw (non-summary) turns,
    summarize everything except the most recent keep_recent into a
    single condensed entry. Only fires once the excess crosses
    trigger_at, then compacts down to keep_recent in one batch --
    avoids re-summarizing on every single turn once the threshold is
    first crossed, which would add an LLM call to every subsequent
    turn instead of periodically batching.

    Any existing summary entry gets folded into the new one along
    with the newly-aging-out turns, so repeated compaction doesn't
    lose what earlier compactions already condensed.
    """
    regular_turns = [turn for turn in history if "summary" not in turn]

    if len(regular_turns) <= trigger_at:
        return history

    summary_entries = [turn for turn in history if "summary" in turn]
    to_compact = regular_turns[:-keep_recent]
    recent = regular_turns[-keep_recent:]

    transcript_parts = [
        f"Earlier summary: {entry['summary']}" for entry in summary_entries
    ]
    transcript_parts += [build_transcript([turn]) for turn in to_compact]

    transcript = "\n".join(transcript_parts)
    summary = summarize_transcript(transcript, model=model)

    return [{"summary": summary}] + recent
