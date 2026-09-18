from agent.executor import expected_tools_for


def test_expected_tools_for_create_is_write_file():
    assert expected_tools_for("Create hello.py containing exactly print('hi')") == {"write_file"}


def test_expected_tools_for_run_is_run_python_file():
    assert expected_tools_for("Run a file called does_not_exist.py") == {"run_python_file"}


def test_expected_tools_for_execute_is_run_python_file():
    assert expected_tools_for("Execute hello.py") == {"run_python_file"}


def test_expected_tools_for_read_is_read_file():
    assert expected_tools_for("Read a.txt") == {"read_file"}


def test_expected_tools_for_edit_is_edit_file():
    assert expected_tools_for("Modify hello.py to fix the bug") == {"edit_file"}


def test_expected_tools_for_unmatched_objective_is_empty():
    assert expected_tools_for("Summarize the project") == set()


def test_expected_tools_for_multiple_keywords_returns_multiple_tools():
    assert expected_tools_for("Read a.txt and edit b.txt") == {"read_file", "edit_file"}


def test_expected_tools_for_is_case_insensitive():
    assert expected_tools_for("CREATE hello.py") == {"write_file"}


def test_expected_tools_for_read_memory_json_also_accepts_search_memory():
    # A Planner slip-up (memory.json isn't a real readable file) --
    # search_memory succeeding should still count as valid evidence
    # even though the objective says "Read".
    assert expected_tools_for("Read memory.json") == {"read_file", "search_memory"}
