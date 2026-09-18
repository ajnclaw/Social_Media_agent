# tools.py

import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import PROJECT_ROOT, SANDBOX_DIR
from .memory import search_memory, save_memory
from .approval import ApprovalPolicy
from .approval_manager import ApprovalManager


ALLOWED_COMMANDS = {
    "pwd",
    "ls",
    "whoami",
}

# Known external APIs the agent is allowed to call with call_api.
# Each is free and requires no API key -- this is a curated allowlist,
# not open internet access. Adding a new API means adding it here
# deliberately, the same way ALLOWED_COMMANDS works for shell commands.
API_REGISTRY = {
    "api.open-meteo.com": (
        "Free weather forecast API, no key required. "
        "Example: https://api.open-meteo.com/v1/forecast"
        "?latitude=51.5&longitude=-0.12&current_weather=true"
    ),
    "api.frankfurter.app": (
        "Free currency exchange rate API, no key required. "
        "Example: https://api.frankfurter.app/latest?from=USD&to=EUR"
    ),
    "ipapi.co": (
        "Free IP-based geolocation API, no key required. Returns the "
        "approximate location (city, region, country, latitude, "
        "longitude, timezone) of the network making the request. This "
        "is NOT exact GPS location -- it can be inaccurate for VPNs "
        "or mobile networks, and should be presented to the user as "
        "an approximation, not a certainty. Useful ONLY as a fallback "
        "when the user hasn't named a specific place -- if the user "
        "names a city by name, use geocoding-api.open-meteo.com "
        "instead, since it resolves the exact place they meant rather "
        "than guessing from network IP. Example: https://ipapi.co/json/ "
        "(no parameters needed)."
    ),
    "geocoding-api.open-meteo.com": (
        "Free geocoding API, no key required. Converts a place name "
        "into coordinates (latitude/longitude) that can then be passed "
        "to api.open-meteo.com for weather. Always use this when the "
        "user names a specific city, rather than guessing coordinates "
        "from memory or falling back to IP geolocation. "
        "Example: https://geocoding-api.open-meteo.com/v1/search"
        "?name=Hisar&count=1"
    ),
}

ALLOWED_API_DOMAINS = set(API_REGISTRY)


def is_allowed_api_url(url):
    parsed = urllib.parse.urlparse(url)

    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_API_DOMAINS
    )


def build_request_url(url, params=None):
    """
    Merge url and params into the exact URL that will actually be
    requested. Shared by call_api (to build the real request) and the
    approval preview (so what you're shown to approve is guaranteed
    to match what actually gets sent, not a separately-maintained
    copy of the same logic).
    """
    if not params:
        return url

    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.urlencode(params)
    separator = "&" if parsed.query else "?"

    return f"{url}{separator}{query}"


def call_api(url, params=None):

    try:

        if not is_allowed_api_url(url):

            return tool_result(
                success=False,
                error=(
                    f"URL not allowed: {url}. Only https requests to "
                    f"{sorted(ALLOWED_API_DOMAINS)} are permitted."
                ),
            )

        url = build_request_url(url, params)

        request = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "ai-agent/1.0"},
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(1_000_000).decode(
                "utf-8",
                errors="replace",
            )

        return tool_result(
            success=True,
            output=body,
        )

    except urllib.error.URLError as e:

        return tool_result(
            success=False,
            error=f"Request failed: {e}",
        )

    except Exception as e:

        return tool_result(
            success=False,
            error=str(e),
        )

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

def save_memory_tool(key, value):

    try:

        result = save_memory(key, value)

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

    "call_api": call_api,
}


def _call_api_preview(arguments):
    url = build_request_url(
        arguments.get("url", ""),
        arguments.get("params"),
    )

    return f"Full request URL (what will actually be sent):\n  {url}"


# Optional per-tool preview shown in the approval prompt, computed
# from the raw arguments before the tool runs. Only call_api has one
# right now -- its raw arguments (url + optional params) don't show
# the actual outgoing request, so this resolves them into the real
# URL using the exact same logic call_api itself uses to build it.
TOOL_PREVIEW_BUILDERS = {
    "call_api": _call_api_preview,
}


class ToolManager:

    def __init__(self):

        self.approval_policy = ApprovalPolicy()
        self.approval_manager = ApprovalManager()

        self.functions = TOOL_FUNCTIONS
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def execute(self, tool_name, arguments):
        result = self._execute(tool_name, arguments)

        if self.logger:
            self.logger.log_tool_call(tool_name, arguments, result)

        return result

    def _execute(self, tool_name, arguments):

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

            preview = None
            preview_builder = TOOL_PREVIEW_BUILDERS.get(tool_name)

            if preview_builder:
                try:
                    preview = preview_builder(arguments)
                except Exception:
                    preview = None

            approved = self.approval_manager.request_approval(
                tool_name,
                arguments,
                preview=preview,
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


_API_REGISTRY_DESCRIPTION = "\n".join(
    f"- {domain}: {description}"
    for domain, description in API_REGISTRY.items()
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
            "description": (
                "Search persistent agent memory for saved facts. "
                "Returns the best-matching facts ranked by relevance, "
                "or every saved fact if nothing closely matches the "
                "query -- treat weakly-related results accordingly. "
                "When you use a result in your answer, say it came "
                "from saved memory (e.g. 'Based on what you told me "
                "before...') rather than stating it as if you always "
                "knew it."
            ),
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
            "description": (
                "Save a fact to persistent agent memory as a key/value "
                "pair. Saving the same key again overwrites the "
                "previous value instead of creating a duplicate -- use "
                "a short, stable key (e.g. 'location', "
                "'favorite_language') so updates replace old facts "
                "instead of piling up. The result lists other saved "
                "keys -- before inventing a new key, check whether one "
                "of them already covers the same concept (e.g. don't "
                "save 'current_city' if 'location' already exists for "
                "it) and reuse that key instead of fragmenting the "
                "same fact across multiple keys."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short stable identifier for this fact, e.g. 'location'.",
                    },
                    "value": {
                        "type": "string",
                        "description": "The value to remember for this key.",
                    },
                },
                "required": ["key", "value"],
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
    {
        "type": "function",
        "function": {
            "name": "call_api",
            "description": (
                "Make a GET request to a known external API when a task "
                "needs real-world information no local tool can provide "
                "(e.g. current weather, exchange rates). Only the "
                "pre-approved domains below are allowed -- any other URL "
                "is rejected. When you use the result in your answer, "
                "mention which source it came from (e.g. 'According to "
                "the weather API...') rather than stating it as fact "
                "without attribution.\n\n" + _API_REGISTRY_DESCRIPTION
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full HTTPS URL of the API endpoint to call.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional query parameters to append to the URL.",
                    },
                },
                "required": ["url"],
            },
        },
    },
]