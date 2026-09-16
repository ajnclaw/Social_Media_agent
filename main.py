import argparse
import sys

from agent import Agent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the AI agent on a single request.",
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="The task to give the agent. If omitted, you'll be prompted.",
    )
    return parser.parse_args()


def print_summary(state):
    print("\n=== SUMMARY ===")
    print(f"Status: {state.status}")

    for task in state.tasks:
        line = f"  Task {task.step} [{task.status}] {task.objective}"

        if task.retries:
            line += f" (retries: {task.retries})"

        if task.failure_type:
            line += f" (failure_type: {task.failure_type})"

        print(line)


def main():
    args = parse_args()

    user_input = args.request or input("What should the agent do? ")

    if not user_input.strip():
        print("No request given.")
        sys.exit(1)

    agent = Agent()
    state = agent.run(user_input)

    print_summary(state)

    sys.exit(0 if state.status == "completed" else 1)


if __name__ == "__main__":
    main()