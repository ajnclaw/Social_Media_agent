class Evaluator:

    def verify(self, task, context=None):

        if task.task_type != "verification":
            return {
                "success": False,
                "output": None,
                "error": "Task is not a verification task.",
            }

        if not task.depends_on:
            return {
                "success": False,
                "output": None,
                "error": "Verification task has no dependency.",
            }

        dependency_step = task.depends_on[-1]

        if not context or dependency_step not in context:
            return {
                "success": False,
                "output": None,
                "error": (
                    f"No result available for "
                    f"Task {dependency_step}."
                ),
            }

        actual_output = str(
            context[dependency_step] or ""
        ).strip()

        expected_output = str(
            task.expected_output or ""
        ).strip()

        if actual_output == expected_output:
            return {
                "success": True,
                "output": actual_output,
                "error": None,
            }

        return {
            "success": False,
            "output": actual_output,
            "error": (
                f"Expected output: {expected_output!r}, "
                f"but received: {actual_output!r}"
            ),
        }

    def evaluate(self, task, result, context=None):

        if not result.get("success"):
            return {
                "success": False,
                "output": None,
                "error": result.get(
                    "error",
                    "Task execution failed.",
                ),
                "denied": result.get(
                    "denied",
                    False,
                ),
            }

        actual_output = str(
            result.get("output") or ""
        ).strip()

        # Execution succeeded.
        #
        # Do NOT check expected_output here.
        # Output correctness is handled by a separate
        # verification task.
        return {
            "success": True,
            "output": actual_output,
            "error": None,
        }