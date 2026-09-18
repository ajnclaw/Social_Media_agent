# memory.py

import json
import re
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

    result = f"Saved: {key} = {value}"

    other_keys = sorted(k for k in data if k != key)

    if other_keys:
        # Surface what else is already saved so the model can notice
        # on its own if a new key fragments a fact an existing key
        # already covers (e.g. saving "current_city" when "location"
        # already exists) -- string-matching can't reliably tell that
        # apart from coincidental overlap, but the model's own
        # judgment can, given visibility into what's already there.
        result += f"\nOther saved keys: {', '.join(other_keys)}"

    return result


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _format_entries(entries):
    return "\n".join(f"{key}: {value}" for key, value in entries)


def search_memory(query):
    data = _load()

    if not data:
        return ""

    query_lower = query.lower()
    query_tokens = _tokenize(query)

    scored = []

    for key, value in data.items():
        haystack = f"{key} {value}".lower()
        entry_tokens = _tokenize(key) | _tokenize(str(value))

        substring_hit = bool(query_lower) and query_lower in haystack
        token_overlap = query_tokens & entry_tokens

        if substring_hit or token_overlap:
            score = len(token_overlap) + (1 if substring_hit else 0)
            scored.append((score, key, value))

    if not scored:
        # No match at all -- fall back to returning everything so the
        # model can still reason over what's available instead of
        # drawing a blank. Reasonable at this store's realistic scale
        # (a personal fact list); would need a real ranked/limited
        # fallback (or actual semantic search) if it grows large.
        return _format_entries(data.items())

    scored.sort(key=lambda item: item[0], reverse=True)

    return _format_entries((key, value) for _, key, value in scored)
