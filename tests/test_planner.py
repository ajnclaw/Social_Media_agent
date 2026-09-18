from agent.planner import build_tasks, find_self_dependent_tasks


def test_build_tasks_from_wrapped_dict():
    data = {
        "tasks": [
            {
                "step": 1,
                "objective": "Do something",
                "depends_on": [],
                "expected_output": None,
                "task_type": "execution",
            }
        ]
    }

    tasks = build_tasks(data)

    assert len(tasks) == 1
    assert tasks[0].step == 1
    assert tasks[0].objective == "Do something"


def test_build_tasks_tolerates_bare_list():
    data = [
        {"objective": "First", "depends_on": [], "expected_output": None, "task_type": "execution"},
        {"objective": "Second", "depends_on": [], "expected_output": None, "task_type": "execution"},
    ]

    tasks = build_tasks(data)

    assert len(tasks) == 2
    assert [t.step for t in tasks] == [1, 2]
    assert [t.objective for t in tasks] == ["First", "Second"]


def test_build_tasks_tolerates_missing_step():
    data = {"tasks": [{"objective": "Only task"}]}

    tasks = build_tasks(data)

    assert tasks[0].step == 1


def test_build_tasks_preserves_explicit_step_over_index():
    data = {"tasks": [{"step": 5, "objective": "Explicit step"}]}

    tasks = build_tasks(data)

    assert tasks[0].step == 5


def test_build_tasks_defaults_task_type_to_execution():
    data = {"tasks": [{"step": 1, "objective": "No type given"}]}

    tasks = build_tasks(data)

    assert tasks[0].task_type == "execution"


def test_build_tasks_empty_tasks_list_returns_empty():
    assert build_tasks({"tasks": []}) == []


def test_find_self_dependent_tasks_detects_self_reference():
    data = {
        "tasks": [
            {
                "step": 1,
                "objective": "Verify something impossible",
                "depends_on": [1],
                "expected_output": "X",
                "task_type": "verification",
            }
        ]
    }

    tasks = build_tasks(data)
    self_dependent = find_self_dependent_tasks(tasks)

    assert len(self_dependent) == 1
    assert self_dependent[0].step == 1


def test_find_self_dependent_tasks_ignores_valid_dependencies():
    data = {
        "tasks": [
            {"step": 1, "objective": "Create hello.py", "depends_on": []},
            {"step": 2, "objective": "Run hello.py", "depends_on": [1]},
        ]
    }

    tasks = build_tasks(data)

    assert find_self_dependent_tasks(tasks) == []


def test_find_self_dependent_tasks_returns_empty_for_no_tasks():
    assert find_self_dependent_tasks([]) == []
