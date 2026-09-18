from agent.approval import ApprovalPolicy


def test_memory_tools_are_auto_approved():
    policy = ApprovalPolicy()

    for tool_name in ("save_memory", "search_memory"):
        result = policy.check(tool_name)

        assert result["allowed"] is True
        assert result["requires_approval"] is False


def test_call_api_still_requires_approval():
    policy = ApprovalPolicy()

    result = policy.check("call_api")

    assert result["allowed"] is False
    assert result["requires_approval"] is True


def test_file_and_shell_mutation_tools_still_require_approval():
    policy = ApprovalPolicy()

    for tool_name in ("write_file", "edit_file", "create_directory", "run_command"):
        result = policy.check(tool_name)

        assert result["requires_approval"] is True


def test_unknown_tool_is_not_allowed():
    policy = ApprovalPolicy()

    result = policy.check("delete_everything")

    assert result["allowed"] is False
    assert result["requires_approval"] is False
