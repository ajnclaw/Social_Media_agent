class ApprovalManager:

    def request_approval(
        self,
        tool_name,
        arguments,
    ):
        print("\n" + "=" * 60)
        print("APPROVAL REQUIRED")
        print("=" * 60)

        print(f"Tool: {tool_name}")
        print("Arguments:")

        for key, value in arguments.items():
            print(f"  {key}: {value}")

        print("=" * 60)

        answer = input(
            "Allow this tool call? [y/N]: "
        ).strip().lower()

        return answer in {"y", "yes"}