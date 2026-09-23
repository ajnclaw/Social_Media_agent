# config.py

import os
from pathlib import Path


MEMORY_FILE = "memory.json"

PROJECT_ROOT = Path.cwd()

SANDBOX_DIR = PROJECT_ROOT / "sandbox"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

VOICE_REFERENCE_PATH = PROJECT_ROOT / "assets" / "voice_reference.mp3"

# Image generation runs on a separate machine (see agent/image_server.py)
# to avoid competing with Chatterbox for GPU memory on this one. Set to
# that machine's address, e.g. "http://192.168.1.42:8420".
IMAGE_SERVER_URL = os.environ.get("IMAGE_SERVER_URL", "")

# One-time OAuth setup only the account owner can do (see agent/youtube.py) --
# download the client secret from Google Cloud Console and place it here.
YOUTUBE_CLIENT_SECRET_PATH = PROJECT_ROOT / "assets" / "youtube_client_secret.json"
YOUTUBE_TOKEN_PATH = PROJECT_ROOT / "assets" / "youtube_token.json"

DEFAULT_AGENT_NAME = "main"

DEFAULT_MODEL = "qwen3:4b"

DEFAULT_MAX_ITERATIONS = 10