import os


# Tools that publish/post content externally are never auto-approved, even
# with AGENT_AUTO_APPROVE=1 -- that flag exists for headless/server contexts
# (no terminal to answer a y/N prompt), and a real external publish action
# shouldn't lose its human-in-the-loop gate just because nothing can render
# the prompt. Server callers should treat a denial here as "needs the user's
# explicit go-ahead through some other channel", not retry it.
NEVER_AUTO_APPROVE = {
    "post_to_youtube",
}


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

        if (
            os.environ.get("AGENT_AUTO_APPROVE") == "1"
            and tool_name not in NEVER_AUTO_APPROVE
        ):
            print("Auto-approved (AGENT_AUTO_APPROVE=1).")
            return True

        if os.environ.get("AGENT_AUTO_APPROVE") == "1":
            print(
                f"NOT auto-approving '{tool_name}' -- publishes external "
                f"content, always needs an explicit answer."
            )

        try:
            answer = input(
                "Allow this tool call? [y/N]: "
            ).strip().lower()
        except EOFError:
            # No interactive terminal attached (e.g. running as a headless
            # server) -- default to denying rather than hanging or crashing.
            print("No terminal attached to answer -- denying by default.")
            return False

        return answer in {"y", "yes"}