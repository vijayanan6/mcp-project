"""
rag.py — Retrieval Augmented Generation core

How it works:
  1. INDEX  : Read docs → split into chunks → embed each chunk → store in ChromaDB
  2. SEARCH : Embed the user's question → find the most similar chunks → return them

Why chunks instead of full files?
  - A 10-page document has thousands of sentences.
  - Only 2-3 sentences are usually relevant to any given question.
  - Chunking + similarity search finds those 2-3 sentences efficiently.

Embedding = converting text into a list of numbers (a vector) that captures meaning.
Two sentences with similar meaning will have vectors that are "close" in space.
ChromaDB stores these vectors and finds the closest ones to a query.
"""
import os
import ssl
from pathlib import Path

# ── SSL fix for Windows corporate machines ────────────────────────────────────
# HuggingFace Hub uses httpx which has its own SSL layer.
# We patch both Python's ssl module and httpx directly before any imports.
ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
os.environ["HF_HUB_DISABLE_SSL_VERIFICATION"] = "1"

import httpx  # must import after os.environ is set

_orig_client = httpx.Client.__init__
_orig_async  = httpx.AsyncClient.__init__

def _patched_client(self, *a, **kw):
    kw.setdefault("verify", False)
    _orig_client(self, *a, **kw)

def _patched_async(self, *a, **kw):
    kw.setdefault("verify", False)
    _orig_async(self, *a, **kw)

httpx.Client.__init__      = _patched_client  # type: ignore[method-assign]
httpx.AsyncClient.__init__ = _patched_async   # type: ignore[method-assign]
# ─────────────────────────────────────────────────────────────────────────────

import chromadb
from chromadb.utils import embedding_functions

DOCS_DIR   = Path(__file__).parent.parent.parent / "knowledge_base"
CHROMA_DIR = Path(__file__).parent.parent.parent / "data" / "chroma_db"

CHUNK_SIZE    = 500   # characters per chunk
CHUNK_OVERLAP = 100   # overlap between chunks (preserves context at boundaries)


def _get_collection() -> chromadb.Collection:
    """
    Get or create the ChromaDB collection.
    Embedding model is loaded here (lazy) so SSL patch is applied first.
    First call downloads ~80MB model from HuggingFace — cached after that.
    """
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name="docs",
        embedding_function=embedding_fn,
    )


def _chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks.
    Tries to break at sentence/paragraph boundaries for cleaner chunks.
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE

        if end < len(text):
            # Try to break at a natural boundary
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("\n", start, end),
            )
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1

        chunk = text[start:end].strip()
        if len(chunk) > 50:   # skip tiny fragments
            chunks.append(chunk)

        start = end - CHUNK_OVERLAP

    return chunks


def index_document(filename: str) -> int:
    """
    Index a single document into ChromaDB.
    Returns the number of chunks stored.
    Re-indexing the same file replaces the old chunks.
    """
    file_path = DOCS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"'{filename}' not found in knowledge_base/")

    text = file_path.read_text(encoding="utf-8")
    chunks = _chunk_text(text)

    collection = _get_collection()

    # Remove old chunks for this file before re-indexing
    try:
        collection.delete(where={"source": filename})
    except Exception:
        pass

    collection.add(
        documents=chunks,
        metadatas=[{"source": filename, "chunk_index": i} for i in range(len(chunks))],
        ids=[f"{filename}::chunk::{i}" for i in range(len(chunks))],
    )

    return len(chunks)


def index_all() -> dict[str, int]:
    """
    Index every supported file in knowledge_base/.
    Returns { filename: chunk_count } for each file processed.
    """
    DOCS_DIR.mkdir(exist_ok=True)
    supported = {".txt", ".md", ".csv"}
    results = {}

    for path in sorted(DOCS_DIR.iterdir()):
        if path.is_file() and path.suffix in supported:
            try:
                count = index_document(path.name)
                results[path.name] = count
            except Exception as err:
                results[path.name] = f"error: {err}"

    return results


def search(query: str, n_results: int = 4) -> list[dict]:
    """
    Semantic search: find the top N chunks most relevant to the query.
    Returns list of { content, source, score } dicts.

    Distance = 0 means identical. Distance > 1 means very different.
    We treat distance < 0.8 as "relevant".
    """
    collection = _get_collection()
    total = collection.count()

    if total == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, total),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for i, doc in enumerate(results["documents"][0]):
        distance = results["distances"][0][i]
        chunks.append({
            "content": doc,
            "source":  results["metadatas"][0][i]["source"],
            "score":   round(1 - distance, 3),   # convert distance → similarity score
        })

    return chunks


def get_stats() -> dict:
    """Return stats about what's indexed in ChromaDB."""
    collection = _get_collection()
    count = collection.count()

    sources = []
    if count > 0:
        all_meta = collection.get(include=["metadatas"])["metadatas"]
        sources = sorted(set(m["source"] for m in all_meta))

    return {"total_chunks": count, "indexed_files": sources}
