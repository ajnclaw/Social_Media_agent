# ai-agent

A task-executing AI agent built around a **plan → schedule → execute → verify → recover** loop, running entirely on a local model via [Ollama](https://ollama.com) (`qwen3:4b`). Every run produces a full JSON trace of what the model reasoned, what tools it called, and how the agent responded to failure.

This isn't a single ReAct while-loop. It's closer to a small workflow engine: a dependency-aware scheduler decides what's runnable, a separate verification step checks results against expectations, and a dedicated recovery agent repairs the actual broken artifact when something fails — instead of just retrying blindly.

## Why this architecture

Most "AI agent" tutorials are a single loop: prompt the model, let it call tools, stop when it says it's done. That's fine for a demo, but it collapses several genuinely different problems into one:

- **Did the plan make sense?** (planning)
- **What's safe to run next, given what's already finished?** (scheduling)
- **Did the model actually do the work, or just claim it did?** (execution vs. verification — kept as two separate steps on purpose)
- **When something fails, is it worth retrying, worth repairing, or a dead end?** (failure classification)
- **If it's repairable, what's actually broken, and how do we fix it — not just try again?** (recovery)

Splitting these into separate, mostly deterministic components means most of the system is unit-testable without ever calling the LLM (see [Testing](#testing)), and each failure mode has an explicit, inspectable decision path instead of "the model tries again and hopes."

## Architecture

```
                 ┌───────────┐
   user request  │  Planner  │  (LLM) → list of Task objects with
   ───────────►  └─────┬─────┘         dependencies + expected outputs
                        │
                        ▼
                 ┌───────────┐
                 │ Scheduler │  picks tasks whose dependencies
                 └─────┬─────┘  have all SUCCEEDED
                        │
            ┌───────────┴────────────┐
            ▼                        ▼
     ┌─────────────┐          ┌─────────────┐
     │  Executor   │  (LLM +  │  Evaluator  │  verification tasks:
     │             │  tools)  │  (verify)   │  exact-match check
     └──────┬──────┘          └─────────────┘  against expected_output
            │
            ▼
     ┌─────────────┐
     │  Evaluator  │  execution tasks: did the tool
     │  (evaluate) │  call actually succeed?
     └──────┬──────┘
            │
       success? ──yes──► mark SUCCESS, feed result to next task
            │
            no
            ▼
   ┌────────────────────┐
   │ FailureClassifier   │  transient / recoverable / permanent
   └──────────┬──────────┘
              │
    ┌─────────┼──────────┐
    ▼         ▼           ▼
 retry    recover       stop
 (backoff) (LLM repairs  (mark FAILED,
            the actual    no more retries)
            broken file)
```

| Component | File | Role |
|---|---|---|
| `Agent` | [agent/core.py](agent/core.py) | Orchestrator: the plan/execute/verify/recover loop |
| `Planner` | [agent/planner.py](agent/planner.py) | LLM breaks the request into `Task` objects: objective, dependencies, expected output, type |
| `Scheduler` | [agent/scheduler.py](agent/scheduler.py) | Pure dependency-graph logic — decides what's ready to run, tracks status transitions |
| `Executor` | [agent/executor.py](agent/executor.py) | Tool-calling LLM loop that does the actual work |
| `Evaluator` | [agent/evaluator.py](agent/evaluator.py) | Checks execution success; separately, exact-match verification for `verification` tasks |
| `FailureClassifier` | [agent/failure.py](agent/failure.py) | Buckets an error into transient / recoverable / permanent |
| `RetryPolicy` | [agent/retry.py](agent/retry.py) | Exponential backoff for transient failures, triggers recovery for recoverable ones |
| `Recovery` | [agent/recovery.py](agent/recovery.py) | A second LLM agent that reads the broken artifact and repairs it directly |
| `ApprovalPolicy` / `ApprovalManager` | [agent/approval.py](agent/approval.py), [agent/approval_manager.py](agent/approval_manager.py) | Human-in-the-loop gate on any tool that mutates state |
| `ToolManager` | [agent/tools.py](agent/tools.py) | Sandboxed file/shell tools; the single choke point every tool call passes through |
| `RunLogger` | [agent/logger.py](agent/logger.py) | Structured console logs + a full JSON trace per run |

## Key design decisions

- **Execution and verification are separate task types**, not one "did it work" check. The `Executor` never grades its own homework — a dedicated `verification` task compares the actual result to an `expected_output` set at planning time. This exists specifically so the model can't talk itself into believing it succeeded.
- **Failures are classified before deciding what to do about them.** A network timeout, a wrong file content, and a permission error all need different responses — blind retry-on-any-failure either wastes retries on unrecoverable errors or gives up too early on transient ones.
- **Recovery repairs the artifact directly**, rather than just re-running the task that failed. It reads the file responsible for the bad result and edits it — the actual mechanism the "self-healing" behavior depends on (see the example run below).
- **Every tool call is gated by an approval policy.** Read-only tools (`read_file`, `list_files`, `search_memory`, `run_python_file`) run automatically; anything that mutates state (`write_file`, `edit_file`, `create_directory`, `run_command`, `save_memory`) prompts for a `y/N` before executing.
- **All agent-written files live in `sandbox/`, not the source tree.** `write_file`/`edit_file`/`run_command` all resolve inside a dedicated sandbox directory (`config.SANDBOX_DIR`), with a path-traversal check (`safe_path`) blocking any attempt to escape it. The agent's own file tools cannot read or modify this repository's source code.
- **Deterministic orchestration logic is separated from LLM calls specifically so it's testable.** `Scheduler`, `FailureClassifier`, `RetryPolicy`, and `Evaluator` contain zero LLM calls — see [Testing](#testing).

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
ollama pull qwen3:4b

python main.py "Create hello.py containing exactly print('hello world'), then run it and verify the output"
```

Omit the argument to be prompted interactively instead:
```bash
python main.py
```

Exit code reflects the run's outcome (`0` = completed, `1` = failed), so it's scriptable.

## Example run: self-healing recovery

This is the most interesting thing the agent does, so it's worth walking through directly. The request deliberately asks for a file with the *wrong* content, then verifies against the *right* content — guaranteeing a verification failure:

```
python main.py "Create broken.py containing exactly print('goodbye world'), then run it and verify the output is 'hello world'"
```

What happens:

1. **Task 1** writes `broken.py` with `print('goodbye world')` — exactly as instructed.
2. **Task 2** runs it, captures `goodbye world`.
3. **Task 3** (verification) compares `goodbye world` against the expected `hello world` → **fails**.
4. `FailureClassifier` labels this `recoverable` (it matched on `"expected output"` in the error text).
5. `Recovery` — a separate LLM pass with its own system prompt — reads `broken.py`, determines *why* it's wrong, and calls `edit_file` to change it to `print('hello world')`.
6. The scheduler resets **only Task 2** (the stale execution whose output needs refreshing) — not Task 1, since re-running the original creation task would just overwrite Recovery's fix with the original, incorrect instructions again. (This exact bug existed and was fixed during development — see below.)
7. Task 2 re-runs, gets `hello world`. Task 3 re-verifies — **passes**.

Final result: `status: completed`, no human intervention beyond approving the two mutating tool calls (`write_file`, `edit_file`).

## Observability

Every run writes `logs/<run_id>.json` — a complete trace containing:

- the full plan (every task, its dependencies, and expected output)
- an `llm_call` event for **every** model call across `Planner`, `Executor`, and `Recovery`, with the raw response content and any tool calls the model chose to make
- a `tool_call` event for every tool execution, including arguments, success/failure, and output
- task-level events (start, success, failure, retry, recovery) with timestamps
- final per-task status, retry counts, and failure history

Trace files are written on **every** exit path — including failed runs — since a failure trace is usually more interesting to debug than a success one.

```json
{
  "type": "llm_call",
  "elapsed_seconds": 70.929,
  "component": "executor",
  "model": "qwen3:4b",
  "content": "",
  "tool_calls": [
    {"name": "write_file", "arguments": {"path": "hello.py", "content": "print('hello world')"}}
  ]
}
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest -v
```

49 tests, all pure logic — no LLM calls, no mocking required:

| File | Count | Covers |
|---|---|---|
| `tests/test_scheduler.py` | 14 | Dependency resolution, status transitions, chain reset |
| `tests/test_failure.py` | 10 | Error → transient/recoverable/permanent classification |
| `tests/test_retry.py` | 12 | Retry budget, backoff timing, action selection |
| `tests/test_evaluator.py` | 13 | Verification matching, execution result handling |

`Planner`, `Executor`, and `Recovery` aren't unit tested — they call `ollama.chat(...)` directly, which needs either mocking or a real model to exercise properly. That's a deliberate scope line: the deterministic orchestration is tested with unit tests, the LLM-driven behavior is validated by running real scenarios and inspecting the trace (see the example above).

## Bugs found and fixed during development

Kept here because each one taught something worth remembering, not just as a changelog:

1. **Batch-processing bug in `agent.py`** — the success/failure handling block was indented as a *sibling* of the `for task in ready_tasks` loop instead of nested inside it, so only the last task in a batch of simultaneously-ready tasks ever got evaluated; the rest silently stayed `RUNNING` forever. Caught by reasoning about what happens when the scheduler returns more than one ready task at once — a case single-chain test prompts never trigger.
2. **`save_memory_tool` vs `save_memory` name mismatch** — the approval policy referenced the Python function's name instead of the tool's *registered* name, so the `save_memory` tool was always rejected as "unknown" rather than prompting for approval.
3. **Recovery-undo loop in `reset_task_chain`** — after a successful repair, the scheduler reset the *entire* upstream dependency chain (not just the immediate dependency), which meant the original file-creation task re-ran and overwrote Recovery's fix with its original (wrong) instructions — an infinite fix/break oscillation bounded only by the retry limit. Fixed by scoping the reset to the failed task and its immediate dependency only.
4. **`ToolManager.execute`/`_execute` name swap** — when wiring in tool-call logging, the wrapper and the real dispatch logic got their names swapped; the wrapper ended up calling itself (`self._execute(...)` inside a method named `_execute`) instead of the real logic, so it silently never logged anything. No crash, no error — just quietly did nothing, which is why the fix was verified by checking actual JSON output, not just "did it run without an exception."
5. **Eval harness sandbox contamination** — early eval runs didn't reset `sandbox/` between scenarios, so files left behind by one scenario leaked into the next one's context. In one run, Recovery investigating a broken `broken.py` also found a leftover `hello.py` from an unrelated prior scenario, mistook its already-correct content for evidence the problem was solved, and gave up without ever repairing the actual file. Fixed by wiping and recreating `sandbox/` before each scenario.
6. **False-positive task success in `Executor.execute()`** — `last_tool_output` was overwritten by *any* successful tool call, not specifically the one matching the task's actual objective. A task whose real operation (`run_python_file`) failed was still reported as `success: true` because the model made an unrelated follow-up call (`list_files`) that happened to succeed afterward. Caught by the eval set's `run_missing_file` scenario, which expects a clean failure. Fixed by inferring which tool a task's objective actually requires (`expected_tools_for`, keyed off verbs like "create"/"run"/"read") and only counting a matching tool's success as evidence of completion.

## What I'd do next at scale

- **Exploit the scheduler's existing parallelism.** `get_ready_tasks` already returns every task whose dependencies are satisfied, but the executor loop runs them sequentially. Independent tasks could run concurrently.
- **Schema-validate planner output** (e.g. with Pydantic) instead of a bare `json.loads` — a slightly malformed response from a small local model currently crashes the run instead of failing gracefully.
- **Cycle detection** in the planner's dependency graph — a bad plan with a circular dependency currently just stalls (`get_ready_tasks` returns empty, loop exits with "No ready tasks remain") rather than being caught explicitly.
- **A global timeout/iteration cap** on `Agent.run()` as a last-resort circuit breaker, independent of any single task's retry budget.
- **A fixed eval set** (a handful of known prompts run repeatedly, success/retry/recovery rates tracked over time) instead of relying on ad hoc manual runs to judge reliability.
- **Semantic memory search** — `memory.py` is currently a flat-file substring search; fine for a demo, would need embeddings/a vector store to be useful at any real scale.

## Project structure

```
main.py                          CLI entry point
agent/
    __init__.py                    re-exports Agent
    core.py                        orchestrator: the plan/execute/verify/recover loop
    planner.py                     LLM turns a request into Task objects
    scheduler.py                   dependency-graph logic (pure, no LLM)
    executor.py                    tool-calling LLM loop that does the work
    evaluator.py                   execution + verification result checking (pure, no LLM)
    failure.py                     error -> transient/recoverable/permanent (pure, no LLM)
    retry.py                       retry budget, backoff, action selection (pure, no LLM)
    recovery.py                    LLM agent that repairs broken artifacts directly
    tools.py                       sandboxed file/shell tools + approval-gated dispatch
    approval.py                    which tools need human approval
    approval_manager.py            the actual y/N prompt
    memory.py                      flat-file substring-search memory
    state.py                       per-run mutable state (tasks, results, status)
    task.py                        Task model + status/failure-type constants
    logger.py                      structured console logs + JSON trace files
    llm_client.py                  single choke point for every ollama.chat call
    config.py                      model name, sandbox dir, iteration limits
tests/                            pytest suite (49 tests, pure logic only)
sandbox/                          agent-writable workspace (gitignored)
logs/                             per-run JSON traces (gitignored)
```
