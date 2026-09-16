# tools.py

import os
import subprocess
from pathlib import Path

from config import PROJECT_ROOT, SANDBOX_DIR
from memory import search_memory, save_memory
from approval import ApprovalPolicy
from approval_manager import ApprovalManager


ALLOWED_COMMANDS = {
    "pwd",
    "ls",
    "whoami",
}

def run_command(command):

    try:

        if command not in ALLOWED_COMMANDS:

            return tool_result(
                success=False,
                error=(
                    f"Command not allowed: {command}"
                )
            )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=SANDBOX_DIR,
            timeout=30
        )

        return tool_result(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr
        )

    except subprocess.TimeoutExpired:

        return tool_result(
            success=False,
            error="Command timed out."
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def tool_result(
    success,
    output=None,
    error=None,
    denied=False,
):
    return {
        "success": success,
        "output": output,
        "error": error,
        "denied": denied,
    }

def safe_path(path):

    target = (SANDBOX_DIR / path).resolve()

    sandbox_root = SANDBOX_DIR.resolve()

    if not target.is_relative_to(sandbox_root):

        raise PermissionError(
            "Access outside sandbox directory denied."
        )

    return target

def list_files():

    try:

        files = []

        for path in SANDBOX_DIR.rglob("*"):

            if path.is_file():

                files.append(
                    str(
                        path.relative_to(SANDBOX_DIR)
                    )
                )

        return tool_result(
            success=True,
            output=files
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def create_directory(path):

    try:

        target = safe_path(path)

        target.mkdir(
            parents=True,
            exist_ok=True
        )

        return tool_result(
            success=True,
            output=f"Directory created: {path}"
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def read_file(path):

    try:

        target = safe_path(path)

        if not target.exists():

            return tool_result(
                success=False,
                error=f"File does not exist: {path}"
            )

        if not target.is_file():

            return tool_result(
                success=False,
                error=f"Not a file: {path}"
            )

        content = target.read_text(
            encoding="utf-8"
        )

        return tool_result(
            success=True,
            output=content
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def write_file(path, content):

    try:

        target = safe_path(path)

        target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        target.write_text(
            content,
            encoding="utf-8"
        )

        return tool_result(
            success=True,
            output=f"File written: {path}"
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def edit_file(path, old_text, new_text):

    try:

        target = safe_path(path)

        if not target.exists():

            return tool_result(
                success=False,
                error=f"File does not exist: {path}"
            )

        content = target.read_text(
            encoding="utf-8"
        )

        if old_text not in content:

            return tool_result(
                success=False,
                error="Text to replace was not found."
            )

        updated = content.replace(
            old_text,
            new_text,
            1
        )

        target.write_text(
            updated,
            encoding="utf-8"
        )

        return tool_result(
            success=True,
            output=f"File edited: {path}"
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def get_venv_python():

    if os.name == "nt":

        return PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

    return PROJECT_ROOT / ".venv" / "bin" / "python"

def run_python_file(path):

    try:

        target = safe_path(path)

        if not target.exists():

            return tool_result(
                success=False,
                error=f"File does not exist: {path}"
            )

        python = get_venv_python()

        if not python.exists():

            return tool_result(
                success=False,
                error=(
                    f"Virtual environment Python "
                    f"not found: {python}"
                )
            )

        result = subprocess.run(
            [
                str(python),
                str(target)
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=SANDBOX_DIR
        )

        return tool_result(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr
        )

    except subprocess.TimeoutExpired:

        return tool_result(
            success=False,
            error="Python execution timed out."
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def search_memory_tool(query):

    try:

        result = search_memory(query)

        return tool_result(
            success=True,
            output=result
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

def save_memory_tool(content):

    try:

        result = save_memory(content)

        return tool_result(
            success=True,
            output=result
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e)
        )

TOOL_FUNCTIONS = {

    "list_files": list_files,

    "create_directory": create_directory,

    "read_file": read_file,

    "write_file": write_file,

    "edit_file": edit_file,

    "run_python_file": run_python_file,

    "search_memory": search_memory_tool,

    "save_memory": save_memory_tool,

    "run_command": run_command,
}


class ToolManager:

    def __init__(self):

        self.approval_policy = ApprovalPolicy()
        self.approval_manager = ApprovalManager()

        self.functions = TOOL_FUNCTIONS

    def execute(self, tool_name, arguments):

        policy = self.approval_policy.check(tool_name)

        # -----------------------------
        # Unknown / denied tool
        # -----------------------------

        if not policy["allowed"] and not policy["requires_approval"]:
            return tool_result(
                success=False,
                error=policy["reason"],
            )

        # -----------------------------
        # Approval required
        # -----------------------------

        if policy["requires_approval"]:

            approved = self.approval_manager.request_approval(
                tool_name,
                arguments,
            )

            if not approved:
                return tool_result(
                    success=False,
                    error=(
                        f"Tool '{tool_name}' "
                        f"was denied by the user."
                    ),
                    denied=True,
                )

        # -----------------------------
        # Execute approved tool
        # -----------------------------

        function = TOOL_FUNCTIONS.get(tool_name)

        if function is None:
            return tool_result(
                success=False,
                error=f"Tool not found: {tool_name}",
            )

        try:
            result = function(**arguments)

            # Tools already return structured results.
            if isinstance(result, dict):
                return result

            return tool_result(
                success=True,
                output=result,
            )

        except Exception as exc:
            return tool_result(
                success=False,
                error=str(exc),
            )


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the project.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory inside the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file inside the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file inside the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file contents.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace existing text in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Text to replace.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text.",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_file",
            "description": "Execute a Python file inside the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Python file path.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search persistent agent memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save information to persistent agent memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Information to remember.",
                    }
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run an allowed shell command inside the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Allowed shell command.",
                    }
                },
                "required": ["command"],
            },
        },
    },
]