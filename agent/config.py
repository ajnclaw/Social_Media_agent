# config.py

import os
from pathlib import Path


def _load_dotenv(path):
    """
    Minimal, dependency-free .env loader: KEY=value per line, tolerant of
    surrounding whitespace around '=', blank lines, and '#' comments.
    Never overwrites a variable already set in the real environment.
    """
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


MEMORY_FILE = "memory.json"

PROJECT_ROOT = Path.cwd()

REMINDERS_DB = PROJECT_ROOT / "reminders.db"

_load_dotenv(PROJECT_ROOT / ".env")

SANDBOX_DIR = PROJECT_ROOT / "sandbox"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

VOICE_REFERENCE_PATH = PROJECT_ROOT / "assets" / "voice_reference.mp3"

# Image generation runs on a separate machine to avoid competing with
# Chatterbox for GPU memory on this one.
#
# QWEN_SERVER_URL (agent/../Qwen_laptop/qwen_server.py, on the same
# machine, different port) is the default: Qwen-Image/Qwen-Image-Edit via
# WeeLLM's layer-streaming, much better subject accuracy, much slower
# (~13min/image). IMAGE_SERVER_URL (agent/image_server.py) is the old
# SD1.5+LCM-LoRA fast path (~2-3s/image), kept as a manual fallback --
# not used by default now.
QWEN_SERVER_URL = os.environ.get("QWEN_SERVER_URL", "")
IMAGE_SERVER_URL = os.environ.get("IMAGE_SERVER_URL", "")

# One-time OAuth setup only the account owner can do (see agent/youtube.py) --
# download the client secret from Google Cloud Console and place it here.
YOUTUBE_CLIENT_SECRET_PATH = PROJECT_ROOT / "assets" / "youtube_client_secret.json"
YOUTUBE_TOKEN_PATH = PROJECT_ROOT / "assets" / "youtube_token.json"

DEFAULT_AGENT_NAME = "main"

# ---------------------------------------------------------------------------
# LLM provider selection
#
# Every provider here exposes an OpenAI-compatible /chat/completions endpoint
# (Ollama's is a compatibility shim in front of its native API; DeepSeek and
# OpenRouter are OpenAI-compatible natively), so llm_client.py needs exactly
# one HTTP implementation -- switching providers is just picking a different
# base_url/api_key/model triple below, never a code change.
#
# Switch providers by setting LLM_PROVIDER in .env (or the real environment)
# to one of the keys in LLM_PROVIDERS. Override the model independently with
# LLM_MODEL -- otherwise each provider's own default below is used.
# ---------------------------------------------------------------------------

LLM_PROVIDERS = {
    "ollama": {
        "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        # Ollama's compat endpoint doesn't check this, but the OpenAI client
        # protocol requires the Authorization header to be present.
        "api_key": os.environ.get("OLLAMA_API_KEY", "ollama"),
        "default_model": "qwen2.5:1.5b",
    },
    "deepseek": {
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "api_key": os.environ.get("DEEPSEEK_API", ""),
        # "deepseek-chat" (DeepSeek-V3) is the plain non-reasoning model --
        # fast tool-calling, no "thinking" tax. "deepseek-reasoner" exists
        # too but has the same extended-reasoning latency problem qwen3:4b
        # did, so it's deliberately not the default.
        "default_model": "deepseek-chat",
    },
    "openrouter": {
        "base_url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "api_key": os.environ.get("OPENROUTER_API", ""),
        "default_model": "openai/gpt-4o-mini",
    },
}

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openrouter")

if LLM_PROVIDER not in LLM_PROVIDERS:
    raise ValueError(
        f"Unknown LLM_PROVIDER {LLM_PROVIDER!r} in .env -- expected one of "
        f"{sorted(LLM_PROVIDERS)}"
    )

_active_provider = LLM_PROVIDERS[LLM_PROVIDER]

LLM_BASE_URL = _active_provider["base_url"]
LLM_API_KEY = _active_provider["api_key"]

DEFAULT_MODEL = os.environ.get("LLM_MODEL", _active_provider["default_model"])

DEFAULT_MAX_ITERATIONS = 10