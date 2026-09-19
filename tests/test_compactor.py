import agent.compactor as compactor_module
from agent.compactor import build_transcript, compact_history


def make_turn(i):
    return {"user_input": f"turn {i}", "status": "completed", "reply": None, "tasks": []}


def test_build_transcript_includes_reply_when_present():
    turns = [{"user_input": "hi", "reply": "hello!", "tasks": []}]

    transcript = build_transcript(turns)

    assert "User: hi" in transcript
    assert "Assistant: hello!" in transcript


def test_build_transcript_falls_back_to_tasks_when_no_reply():
    turns = [
        {
            "user_input": "create hello.py",
            "reply": None,
            "tasks": ["Task 1: Create hello.py -> success"],
        }
    ]

    transcript = build_transcript(turns)

    assert "Assistant: Task 1: Create hello.py -> success" in transcript


def test_build_transcript_falls_back_to_status_when_nothing_else():
    turns = [{"user_input": "hi", "reply": None, "tasks": [], "status": "failed"}]

    transcript = build_transcript(turns)

    assert "Assistant: [failed]" in transcript


def test_compact_history_no_op_below_trigger(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("summarize_transcript should not have been called")

    monkeypatch.setattr(compactor_module, "summarize_transcript", fail_if_called)

    history = [make_turn(i) for i in range(5)]

    result = compact_history(history, keep_recent=5, trigger_at=10)

    assert result == history


def test_compact_history_compacts_once_trigger_exceeded(monkeypatch):
    monkeypatch.setattr(
        compactor_module, "summarize_transcript", lambda transcript, model=None: "SUMMARY TEXT"
    )

    history = [make_turn(i) for i in range(11)]

    result = compact_history(history, keep_recent=5, trigger_at=10)

    assert result[0] == {"summary": "SUMMARY TEXT"}
    assert len(result) == 6
    assert result[-1]["user_input"] == "turn 10"


def test_compact_history_folds_existing_summary_into_new_one(monkeypatch):
    captured = {}

    def fake_summarize(transcript, model=None):
        captured["transcript"] = transcript
        return "NEW SUMMARY"

    monkeypatch.setattr(compactor_module, "summarize_transcript", fake_summarize)

    history = [{"summary": "OLD SUMMARY"}] + [make_turn(i) for i in range(11)]

    result = compact_history(history, keep_recent=5, trigger_at=10)

    assert result[0] == {"summary": "NEW SUMMARY"}
    assert "OLD SUMMARY" in captured["transcript"]
