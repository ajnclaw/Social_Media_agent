from agent.planner import build_prompt_with_history, format_history


def test_format_history_returns_empty_string_for_no_history():
    assert format_history(None) == ""
    assert format_history([]) == ""


def test_format_history_always_includes_summary_regardless_of_turn_cap():
    history = [{"summary": "Earlier: discussed BMI and fitness."}] + [
        {"user_input": f"turn {i}", "status": "completed", "tasks": []}
        for i in range(10)
    ]

    text = format_history(history, max_turns=5)

    assert "Summary of earlier conversation: Earlier: discussed BMI and fitness." in text
    assert "turn 9" in text
    assert "turn 4" not in text


def test_format_history_renders_turns_without_planner_specific_framing():
    history = [
        {
            "user_input": "hi",
            "status": "completed",
            "tasks": [],
        }
    ]

    text = format_history(history)

    assert "User asked: hi" in text
    assert "Only plan for" not in text


def test_format_history_includes_prior_assistant_reply():
    history = [
        {
            "user_input": "am i underweight?",
            "status": "completed",
            "reply": "Your BMI is 31 (weight: 103.5 kg, height: 6 ft), which is obese.",
            "tasks": [],
        }
    ]

    text = format_history(history)

    assert "Assistant replied: Your BMI is 31" in text
    assert "height: 6 ft" in text


def test_format_history_omits_reply_line_when_none():
    history = [
        {
            "user_input": "Create hello.py",
            "status": "completed",
            "reply": None,
            "tasks": ["Task 1: Create hello.py -> success"],
        }
    ]

    text = format_history(history)

    assert "Assistant replied" not in text


def test_no_history_returns_plain_user_input():
    assert build_prompt_with_history("Create hello.py", None) == "Create hello.py"


def test_empty_history_list_returns_plain_user_input():
    assert build_prompt_with_history("Create hello.py", []) == "Create hello.py"


def test_includes_prior_turn_summary():
    history = [
        {
            "user_input": "Create hello.py containing print('hi')",
            "status": "completed",
            "tasks": ["Task 1: Create hello.py -> success"],
        }
    ]

    prompt = build_prompt_with_history("Now run it", history)

    assert "Create hello.py containing print('hi')" in prompt
    assert "Task 1: Create hello.py -> success" in prompt
    assert "New request: Now run it" in prompt


def test_caps_history_to_most_recent_turns():
    history = [
        {"user_input": f"turn {i}", "status": "completed", "tasks": []}
        for i in range(10)
    ]

    prompt = build_prompt_with_history("latest request", history)

    assert "turn 0" not in prompt
    assert "turn 4" not in prompt
    assert "turn 5" in prompt
    assert "turn 9" in prompt
