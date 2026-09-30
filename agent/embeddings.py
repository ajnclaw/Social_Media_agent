# embeddings.py
#
# The encoding half of the RAG pipeline: turns text into the vector space
# vector_memory.py's Chroma collection compares against. Talks directly to
# Ollama's /api/embed (not through llm_client.py's OpenAI-compatible chat
# path -- embeddings are a different endpoint shape, and bge-m3 stays a
# local Ollama model regardless of which LLM_PROVIDER is active for chat,
# since switching *chat* providers has no bearing on the embedding model).

import json
import urllib.error
import urllib.request

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "bge-m3"


def embed(texts):
    """
    Embed one string or a list of strings against bge-m3. Always returns
    a list of vectors (list[list[float]]), even for a single input, so
    callers never have to branch on shape -- see embed_one() for the
    single-string convenience wrapper.
    """
    single = isinstance(texts, str)
    input_texts = [texts] if single else texts

    payload = json.dumps(
        {
            "model": EMBEDDING_MODEL,
            "input": input_texts,
            # Same fix as llm_client.py's chat models: this laptop GPU
            # unloads an idle model fast enough that even a second call a
            # minute later pays a ~100s+ reload cost without this.
            "keep_alive": "30m",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama embedding request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unreachable for embeddings: {exc.reason}") from exc

    return data["embeddings"]


def embed_one(text):
    return embed(text)[0]
