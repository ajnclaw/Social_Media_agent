from agent.responder import RESPONDER_TOOL_NAMES, RESPONDER_TOOL_SCHEMAS


def test_responder_tool_names_are_read_only_plus_call_api():
    assert RESPONDER_TOOL_NAMES == {
        "list_files",
        "read_file",
        "search_memory",
        "call_api",
    }


def test_responder_schemas_match_exactly_the_allowed_tool_names():
    schema_names = {schema["function"]["name"] for schema in RESPONDER_TOOL_SCHEMAS}

    assert schema_names == RESPONDER_TOOL_NAMES


def test_responder_schemas_exclude_mutating_tools():
    schema_names = {schema["function"]["name"] for schema in RESPONDER_TOOL_SCHEMAS}

    for mutating_tool in (
        "write_file",
        "edit_file",
        "create_directory",
        "run_command",
        "run_python_file",
        "save_memory",
    ):
        assert mutating_tool not in schema_names
