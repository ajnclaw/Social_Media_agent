class ApprovalPolicy:

    # Tools that can safely execute automatically.
    AUTO_APPROVED_TOOLS = {
        "list_files",
        "read_file",
        "search_memory",
        "run_python_file",
    }

    # Tools that modify state or have potentially
    # destructive effects.
    APPROVAL_REQUIRED_TOOLS = {
        "create_directory",
        "write_file",
        "edit_file",
        "save_memory",
        "run_command",
        "call_api",
    }

    def requires_approval(self, tool_name):
        return (
            tool_name
            in self.APPROVAL_REQUIRED_TOOLS
        )

    def is_allowed(self, tool_name):
        return (
            tool_name in self.AUTO_APPROVED_TOOLS
            or tool_name in self.APPROVAL_REQUIRED_TOOLS
        )

    def check(self, tool_name):
        if not self.is_allowed(tool_name):
            return {
                "allowed": False,
                "requires_approval": False,
                "reason": (
                    f"Unknown or unregistered tool: "
                    f"{tool_name}"
                ),
            }

        if self.requires_approval(tool_name):
            return {
                "allowed": False,
                "requires_approval": True,
                "reason": (
                    f"Tool '{tool_name}' "
                    f"requires approval."
                ),
            }

        return {
            "allowed": True,
            "requires_approval": False,
            "reason": None,
        }