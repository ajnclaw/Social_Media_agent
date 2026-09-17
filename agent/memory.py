# memory.py

import json
from pathlib import Path

from .config import MEMORY_FILE


def _load():
    path = Path(MEMORY_FILE)

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}


def _save_all(data):
    path = Path(MEMORY_FILE)

    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def save_memory(key, value):
    data = _load()
    data[key] = value
    _save_all(data)

    return f"Saved: {key} = {value}"


def search_memory(query):
    data = _load()

    if not data:
        return ""

    query = query.lower()

    matches = {
        key: value
        for key, value in data.items()
        if query in key.lower() or query in str(value).lower()
    }

    return "\n".join(f"{key}: {value}" for key, value in matches.items())
