import os


class ApprovalManager:

    def request_approval(
        self,
        tool_name,
        arguments,
        preview=None,
    ):
        print("\n" + "=" * 60)
        print("APPROVAL REQUIRED")
        print("=" * 60)

        print(f"Tool: {tool_name}")
        print("Arguments:")

        for key, value in arguments.items():
            print(f"  {key}: {value}")

        if preview:
            print()
            print(preview)

        print("=" * 60)

        if os.environ.get("AGENT_AUTO_APPROVE") == "1":
            print("Auto-approved (AGENT_AUTO_APPROVE=1).")
            return True

        answer = input(
            "Allow this tool call? [y/N]: "
        ).strip().lower()

        return answer in {"y", "yes"}