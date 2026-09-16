# memory.py

from pathlib import Path

from config import MEMORY_FILE


def search_memory(query):

    path = Path(MEMORY_FILE)

    if not path.exists():
        return ""


    query = query.lower()

    matches = []

    with path.open("r", encoding="utf-8") as f:

        for line in f:

            if query in line.lower():
                matches.append(line.rstrip())


    return "\n".join(matches)


def save_memory(content):

    path = Path(MEMORY_FILE)

    with path.open("a", encoding="utf-8") as f:

        f.write(content.strip() + "\n")


    return "Memory saved."