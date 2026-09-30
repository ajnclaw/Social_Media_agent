"""
agent_server.py

A minimal local HTTP server exposing the Agent (plan/execute/verify/recover,
with tools + persistent memory) over HTTP, so the JarvisAgent phone app can
talk to it the way it talks to Ollama directly.

Runs with AGENT_AUTO_APPROVE=1 by default: there's no terminal for a phone
call to answer a y/N prompt on, so every mutating tool call is auto-approved
*except* tools that publish externally (see agent/approval_manager.py's
NEVER_AUTO_APPROVE), which are always denied here rather than hanging.

Single-threaded on purpose: Agent.run() mutates shared component state
(loggers) on every call, so concurrent requests against one Agent instance
would race. Requests queue instead -- fine for a single phone talking to it
one turn at a time.

Usage:
    python agent_server.py            # listens on 127.0.0.1:8765, run from
                                       # the project root (cwd determines
                                       # config.SANDBOX_DIR)
"""

import os

os.environ.setdefault("AGENT_AUTO_APPROVE", "1")

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent import Agent
from agent.compactor import compact_history
from agent.config import DEFAULT_MODEL, LLM_PROVIDER
from agent.reminders import list_reminders, mark_delivered

HOST = "127.0.0.1"
PORT = 8765

KEEP_RECENT_TURNS = 5
COMPACT_TRIGGER_TURNS = 10

agent = Agent()
history = []


def summarize_tasks(state):
    return [
        f"Task {task.step}: {task.objective} -> {task.status}"
        for task in state.tasks
    ]


def voice_reply(state):
    """
    Turn an AgentState into a short, speakable reply. state.reply already
    covers the pure-conversational path (planner found nothing actionable);
    this fills the gap for task-based runs, which only leave behind a list
    of Task objects and a final status -- chat.py's print_summary() does
    the terminal equivalent of this.
    """
    if state.reply:
        return state.reply

    if not state.tasks:
        return "Done." if state.status == "completed" else "I couldn't do that."

    if state.status == "completed":
        if len(state.tasks) == 1:
            last = state.tasks[-1]

            if isinstance(last.result, str) and 0 < len(last.result) <= 200:
                return f"Done -- {last.result}"

            return "Done -- completed 1 step."

        # Multiple tasks: summarize every task's own result, not just the
        # last one -- e.g. "delete disliked_jokes and favorite_jokes"
        # plans two separate delete_memory tasks, each with its own
        # result. Reporting only tasks[-1] silently drops every earlier
        # task's outcome from the reply even though it genuinely ran and
        # succeeded (only its first line, to avoid repeating each task's
        # own "Remaining saved keys: ..." trailer four times over).
        summaries = [
            task.result.splitlines()[0]
            for task in state.tasks
            if isinstance(task.result, str) and task.result
        ]

        if summaries:
            return "Done -- " + "; ".join(summaries)

        step_word = "step" if len(state.tasks) == 1 else "steps"
        return f"Done -- completed {len(state.tasks)} {step_word}."

    failed = next((t for t in state.tasks if t.status == "failed"), None)

    if failed and failed.error:
        return f"I ran into a problem: {failed.error}"

    return "I couldn't finish that."


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "turns": len(history)})
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        if self.path == "/reminders/delivered":
            self._handle_reminders_delivered()
            return

        if self.path != "/chat":
            self._send_json({"error": "not found"}, status=404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON body"}, status=400)
            return

        user_input = (body.get("message") or "").strip()

        if not user_input:
            self._send_json({"error": "missing 'message'"}, status=400)
            return

        global history

        # Snapshot pending reminder ids before the run so any that appear
        # after it are ones set_reminder just created this turn -- those
        # are what the phone needs to actually schedule as notifications
        # (nothing else in this codebase has a way to fire a real alert
        # later; that only exists on the phone side).
        ids_before = {r["id"] for r in list_reminders()}

        try:
            state = agent.run(user_input, history=history)
        except Exception as exc:
            self._send_json(
                {"reply": f"Something went wrong: {exc}", "status": "failed"},
                status=500,
            )
            return

        new_reminders = [
            r for r in list_reminders() if r["id"] not in ids_before
        ]

        history.append(
            {
                "user_input": user_input,
                "status": state.status,
                "reply": state.reply,
                "tasks": summarize_tasks(state),
            }
        )
        history = compact_history(
            history,
            keep_recent=KEEP_RECENT_TURNS,
            trigger_at=COMPACT_TRIGGER_TURNS,
        )

        self._send_json(
            {
                "reply": voice_reply(state),
                "status": state.status,
                "trace_path": str(state.trace_path) if state.trace_path else None,
                "reminders": new_reminders,
            }
        )

    def _handle_reminders_delivered(self):
        """
        The phone calls this once a scheduled notification actually fires
        (see hooks/useAssistant.js's notification-received listener) --
        nothing server-side otherwise has any way to know a reminder was
        actually delivered, since the alarm/notification itself lives
        entirely on the phone.
        """
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON body"}, status=400)
            return

        ids = body.get("ids")

        if not isinstance(ids, list) or not ids:
            self._send_json({"error": "missing/empty 'ids' list"}, status=400)
            return

        mark_delivered(ids)
        self._send_json({"status": "ok", "marked": ids})

    def do_DELETE(self):
        if self.path == "/history":
            global history
            history = []
            self._send_json({"status": "cleared"})
        else:
            self._send_json({"error": "not found"}, status=404)

    def log_message(self, format, *args):
        # Quiet by default -- comment out to see request logs.
        pass


def main():
    server = HTTPServer((HOST, PORT), Handler)

    print(f"Agent server listening on http://{HOST}:{PORT}")
    print(f"LLM provider: {LLM_PROVIDER} (model: {DEFAULT_MODEL})")
    print('POST /chat {"message": "..."} -> {"reply": "...", "status": "..."}')
    print('POST /reminders/delivered {"ids": [...]} -> marks reminders delivered')
    print("DELETE /history -> clears conversation history")
    print("AGENT_AUTO_APPROVE=" + os.environ.get("AGENT_AUTO_APPROVE", "0"))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()