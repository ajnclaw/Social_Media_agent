from evaluator import Evaluator
from task import Task


def make_verification_task(depends_on, expected_output):
    return Task(
        step=99,
        objective="Verify result",
        depends_on=depends_on,
        expected_output=expected_output,
        task_type="verification",
    )


def test_verify_fails_when_task_is_not_a_verification_task():
    task = Task(
        step=1,
        objective="Do something",
        task_type="execution",
    )

    result = Evaluator().verify(task, context={})

    assert result["success"] is False
    assert result["error"] == "Task is not a verification task."


def test_verify_fails_when_verification_task_has_no_dependency():
    task = make_verification_task(depends_on=[], expected_output="hello")

    result = Evaluator().verify(task, context={})

    assert result["success"] is False
    assert "no dependency" in result["error"]


def test_verify_fails_when_context_is_missing():
    task = make_verification_task(depends_on=[1], expected_output="hello")

    result = Evaluator().verify(task, context=None)

    assert result["success"] is False
    assert "No result available for Task 1" in result["error"]


def test_verify_fails_when_dependency_result_not_in_context():
    task = make_verification_task(depends_on=[1], expected_output="hello")

    result = Evaluator().verify(task, context={2: "something else"})

    assert result["success"] is False
    assert "No result available for Task 1" in result["error"]


def test_verify_uses_the_last_dependency_when_multiple_are_listed():
    task = make_verification_task(depends_on=[1, 2], expected_output="hello")

    result = Evaluator().verify(task, context={1: "wrong task", 2: "hello"})

    assert result["success"] is True


def test_verify_succeeds_on_exact_match():
    task = make_verification_task(depends_on=[1], expected_output="hello world")

    result = Evaluator().verify(task, context={1: "hello world"})

    assert result["success"] is True
    assert result["output"] == "hello world"
    assert result["error"] is None


def test_verify_strips_whitespace_before_comparing():
    task = make_verification_task(depends_on=[1], expected_output="hello world")

    result = Evaluator().verify(task, context={1: "  hello world  \n"})

    assert result["success"] is True


def test_verify_fails_on_mismatch_with_descriptive_error():
    task = make_verification_task(depends_on=[1], expected_output="hello world")

    result = Evaluator().verify(task, context={1: "goodbye world"})

    assert result["success"] is False
    assert result["output"] == "goodbye world"
    assert "hello world" in result["error"]
    assert "goodbye world" in result["error"]


def test_verify_treats_missing_expected_output_and_empty_result_as_equal():
    task = make_verification_task(depends_on=[1], expected_output=None)

    result = Evaluator().verify(task, context={1: None})

    assert result["success"] is True
    assert result["output"] == ""


def evaluate_success_result(output="ok"):
    return {"success": True, "output": output}


def evaluate_failure_result(error="boom", denied=False):
    return {"success": False, "error": error, "denied": denied}


def test_evaluate_passes_through_failure_error_and_denied_flag():
    task = Task(step=1, objective="Do something")

    result = Evaluator().evaluate(
        task, evaluate_failure_result(error="tool broke", denied=True)
    )

    assert result["success"] is False
    assert result["error"] == "tool broke"
    assert result["denied"] is True


def test_evaluate_defaults_denied_to_false_when_absent():
    task = Task(step=1, objective="Do something")

    result = Evaluator().evaluate(task, {"success": False})

    assert result["denied"] is False
    assert result["error"] == "Task execution failed."


def test_evaluate_succeeds_and_strips_output_whitespace():
    task = Task(step=1, objective="Do something")

    result = Evaluator().evaluate(task, evaluate_success_result(output="  done  \n"))

    assert result["success"] is True
    assert result["output"] == "done"
    assert result["error"] is None


def test_evaluate_treats_missing_output_as_empty_string():
    task = Task(step=1, objective="Do something")

    result = Evaluator().evaluate(task, evaluate_success_result(output=None))

    assert result["success"] is True
    assert result["output"] == ""
