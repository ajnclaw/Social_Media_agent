import os
import shutil
import sys
import time

# Auto-approve mutating tool calls so scenarios run unattended.
# Only affects THIS process -- interactive `main.py` runs are
# unaffected and still prompt for every mutating tool call.
os.environ["AGENT_AUTO_APPROVE"] = "1"

from agent import Agent
from agent.config import PROJECT_ROOT, SANDBOX_DIR
import agent.memory as memory_module


def reset_sandbox():
    """
    Wipe the sandbox between scenarios so files left behind by one
    scenario (e.g. hello.py) can't leak into and confuse the next one.
    """
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)

    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)


SCENARIOS = [
    {
        "name": "simple_success",
        "prompt": (
            "Create hello.py containing exactly print('hello world'), "
            "then run it and verify the output"
        ),
        "expected_status": "completed",
    },
    {
        "name": "self_healing_recovery",
        "prompt": (
            "Create broken.py containing exactly print('goodbye world'), "
            "then run it and verify the output is 'hello world'"
        ),
        "expected_status": "completed",
    },
    {
        "name": "list_files",
        "prompt": "List the files currently in the project.",
        "expected_status": "completed",
    },
    {
        "name": "run_missing_file",
        "prompt": "Run a file called does_not_exist_12345.py",
        "expected_status": "failed",
    },
    {
        "name": "two_independent_files",
        "prompt": (
            "Create a.txt containing exactly 'first' and b.txt containing "
            "exactly 'second', then read both files back and verify their "
            "contents match what was written"
        ),
        "expected_status": "completed",
    },
]


def run_memory_scenario():
    """
    Tests that a fact saved in one session is correctly recalled by a
    completely separate Agent instance -- the thing that actually
    matters about persistent memory, not just that the file writes
    correctly (already covered by tests/test_memory.py).

    Uses a scratch memory file for the duration of this scenario only,
    swapped back afterward -- this must NEVER touch the real
    memory.json, since that holds actual saved facts, not test data.
    """
    print("\n" + "#" * 70)
    print("# SCENARIO: memory_recall_across_sessions")
    print("#" * 70)

    original_memory_file = memory_module.MEMORY_FILE
    scratch_memory_file = PROJECT_ROOT / "_eval_memory_scratch.json"
    memory_module.MEMORY_FILE = scratch_memory_file

    started = time.time()
    state2 = None

    try:
        agent1 = Agent()
        state1 = agent1.run("Remember that my favorite color is teal")

        agent2 = Agent()
        state2 = agent2.run("what's my favorite color?")

        status = state2.status
        error = None
        passed = (
            state1.status == "completed"
            and state2.status == "completed"
            and state2.reply is not None
            and "teal" in state2.reply.lower()
        )
    except Exception as exc:
        status = "error"
        error = str(exc)
        passed = False
    finally:
        memory_module.MEMORY_FILE = original_memory_file
        scratch_memory_file.unlink(missing_ok=True)

    duration = round(time.time() - started, 2)

    return {
        "name": "memory_recall_across_sessions",
        "expected_status": "completed (with correct recall)",
        "actual_status": status,
        "passed": passed,
        "duration": duration,
        "total_retries": 0,
        "recoveries": 0,
        "error": error,
        "trace_path": str(state2.trace_path) if state2 and state2.trace_path else None,
    }


def run_scenario(scenario):
    print("\n" + "#" * 70)
    print(f"# SCENARIO: {scenario['name']}")
    print("#" * 70)

    reset_sandbox()

    started = time.time()

    try:
        agent = Agent()
        state = agent.run(scenario["prompt"])
        status = state.status
        error = None
    except Exception as exc:
        status = "error"
        error = str(exc)
        state = None

    duration = round(time.time() - started, 2)
    passed = status == scenario["expected_status"]

    total_retries = 0
    recoveries = 0

    if state:
        for task in state.tasks:
            total_retries += task.retries

            for entry in task.failure_history:
                if entry.get("failure_type") == "recoverable":
                    recoveries += 1

    return {
        "name": scenario["name"],
        "expected_status": scenario["expected_status"],
        "actual_status": status,
        "passed": passed,
        "duration": duration,
        "total_retries": total_retries,
        "recoveries": recoveries,
        "error": error,
        "trace_path": str(state.trace_path) if state and state.trace_path else None,
    }


def main():
    print(
        "Running eval set with AGENT_AUTO_APPROVE=1 -- all mutating tool "
        "calls will be approved automatically, without a human prompt."
    )

    results = [run_scenario(scenario) for scenario in SCENARIOS]
    results.append(run_memory_scenario())

    print("\n" + "=" * 70)
    print("EVAL SUMMARY")
    print("=" * 70)

    for result in results:
        marker = "PASS" if result["passed"] else "FAIL"
        print(
            f"[{marker}] {result['name']:<25} "
            f"expected={result['expected_status']:<10} "
            f"actual={result['actual_status']:<10} "
            f"retries={result['total_retries']} "
            f"recoveries={result['recoveries']} "
            f"duration={result['duration']}s"
        )

        if result["error"]:
            print(f"       error: {result['error']}")

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print(f"\n{passed_count}/{total_count} scenarios passed.")

    sys.exit(0 if passed_count == total_count else 1)


if __name__ == "__main__":
    main()