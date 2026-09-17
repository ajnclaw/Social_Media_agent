# config.py

from pathlib import Path


MEMORY_FILE = "memory.json"

PROJECT_ROOT = Path.cwd()

SANDBOX_DIR = PROJECT_ROOT / "sandbox"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_AGENT_NAME = "main"

DEFAULT_MODEL = "qwen3:4b"

DEFAULT_MAX_ITERATIONS = 10