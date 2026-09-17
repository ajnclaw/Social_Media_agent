from agent.planner import build_prompt_with_history


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
