from agent import Agent


def summarize_tasks(state):
    return [
        f"Task {task.step}: {task.objective} -> {task.status}"
        for task in state.tasks
    ]


def print_summary(state):
    if state.reply:
        print(f"\nagent: {state.reply}")
    else:
        print(f"\nStatus: {state.status}")

        for task in state.tasks:
            line = f"  Task {task.step} [{task.status}] {task.objective}"

            if task.retries:
                line += f" (retries: {task.retries})"

            if task.failure_type:
                line += f" (failure_type: {task.failure_type})"

            print(line)

    if state.trace_path:
        print(f"Trace: {state.trace_path}")


def main():
    print("AI Agent chat. Type 'exit' or 'quit' to leave.\n")

    agent = Agent()
    history = []

    while True:
        try:
            user_input = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("Exiting.")
            break

        state = agent.run(user_input, history=history)

        print_summary(state)
        print()

        history.append({
            "user_input": user_input,
            "status": state.status,
            "tasks": summarize_tasks(state),
        })


if __name__ == "__main__":
    main()
