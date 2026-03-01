"""
rag/store.py
─────────────
ChromaDB vector store for YAWM AI personal preferences.
Stores and retrieves user preferences to enrich DayPlanner context.
"""
from __future__ import annotations
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ── DB lives in project root/rag_db ──────────────────────────────────────────
DB_PATH = str(Path(__file__).parent.parent / "rag_db")

_client     = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=DB_PATH)
        ef = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = _client.get_or_create_collection(
            name="user_preferences",
            embedding_function=ef,
        )
    return _collection


def store_preference(pref_id: str, text: str, metadata: dict = {}):
    """Store or update a single preference."""
    col = _get_collection()
    col.upsert(
        ids       = [pref_id],
        documents = [text],
        metadatas = [metadata],
    )


def retrieve_preferences(query: str, n_results: int = 5) -> list[str]:
    """Retrieve most relevant preferences for a given query."""
    col = _get_collection()
    if col.count() == 0:
        return []
    results = col.query(
        query_texts = [query],
        n_results   = min(n_results, col.count()),
    )
    return results["documents"][0] if results["documents"] else []


def retrieve_all_preferences() -> list[str]:
    """Return all stored preferences."""
    col = _get_collection()
    if col.count() == 0:
        return []
    results = col.get()
    return results["documents"] if results["documents"] else []