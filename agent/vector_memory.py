# vector_memory.py
#
# Semantic (vector) memory -- the upgrade path from memory.py's flat
# substring search. Facts are embedded (bge-m3 via Ollama, see
# embeddings.py) and stored in a local Chroma collection, persisted to
# disk under chroma_db/. No separate server process: Chroma runs
# embedded in this process, same "local-first, one process" shape as
# everything else here.
#
# Chroma is doing exactly two things memory.py's plain JSON file
# couldn't: (1) storing the vectors themselves, and (2) the actual
# nearest-neighbor search over them -- search_facts() below just hands
# it a query vector and gets back the closest stored facts, ranked by
# distance, regardless of whether they share any words with the query.

import chromadb

from .config import PROJECT_ROOT
from .embeddings import embed_one

CHROMA_DIR = PROJECT_ROOT / "chroma_db"

_client = None
_collection = None


def _get_collection():
    global _client, _collection

    if _collection is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _client.get_or_create_collection("memory")

    return _collection


def save_fact(key, value):
    """
    Embeds and stores a fact. Using `key` as the Chroma document id means
    saving the same key again overwrites the previous vector + value
    instead of creating a duplicate -- the same semantics memory.py's
    save_memory() already had, just backed by a vector store now instead
    of a dict.
    """
    collection = _get_collection()

    # Embedding "key: value" rather than just value gives the vector a
    # bit more to work with semantically -- "location: Hisar" carries
    # more signal than "Hisar" alone when compared against a query like
    # "where do I live".
    vector = embed_one(f"{key}: {value}")

    collection.upsert(
        ids=[key],
        embeddings=[vector],
        documents=[value],
        metadatas=[{"key": key}],
    )

    other_keys = sorted(k for k in collection.get()["ids"] if k != key)
    result = f"Saved: {key} = {value}"

    if other_keys:
        result += f"\nOther saved keys: {', '.join(other_keys)}"

    return result


def search_facts(query, top_k=5):
    """
    Semantic search: returns the facts whose embeddings are closest to
    the query's, ranked -- not the facts that happen to share words with
    it. Empty collection returns "" rather than erroring (Chroma raises
    if you query a collection with zero documents).
    """
    collection = _get_collection()

    if collection.count() == 0:
        return ""

    query_vector = embed_one(query)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
    )

    keys = [meta["key"] for meta in results["metadatas"][0]]
    values = results["documents"][0]

    return "\n".join(f"{key}: {value}" for key, value in zip(keys, values))


def list_facts():
    collection = _get_collection()
    data = collection.get()

    keys = [meta["key"] for meta in data["metadatas"]]
    values = data["documents"]

    return dict(zip(keys, values))


def delete_fact(key):
    """
    Raises if the key doesn't exist, rather than silently no-op'ing --
    Chroma's own delete() doesn't error on a missing id, which would let
    the model claim "forgotten" when nothing was actually there to
    forget.
    """
    collection = _get_collection()
    existing = collection.get(ids=[key])

    if not existing["ids"]:
        raise KeyError(f"No saved fact with key '{key}'.")

    collection.delete(ids=[key])

    remaining_keys = sorted(k for k in collection.get()["ids"])
    result = f"Deleted: {key}"

    if remaining_keys:
        result += f"\nRemaining saved keys: {', '.join(remaining_keys)}"

    return result
