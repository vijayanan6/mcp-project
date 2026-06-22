# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
# Install all dependencies
pip install anthropic[mcp] mcp pymupdf pytesseract pypdf fastapi "uvicorn[standard]" chromadb sentence-transformers

# Run the web app (primary entry point)
$env:ANTHROPIC_API_KEY = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
python -m uvicorn api:app --reload --port 8000
# Open: http://localhost:8000

# Run the CLI agent (original learning version)
python agent.py

# Convert scanned PDFs in docs/ to .txt using Tesseract OCR
python convert_pdfs.py

# Inspect SQLite database contents
python inspect_db.py
```

Tesseract must be installed at `C:\Program Files\Tesseract-OCR\` for `convert_pdfs.py` to work.

## Architecture

Three processes when the web app runs:

**`api.py`** — FastAPI web server. Spawns `mcp_server.py` on startup via lifespan, keeps it alive across all requests. Handles HTTP routes, SSE streaming, session management. Auto-indexes docs into ChromaDB on startup. Stores sessions in SQLite.

**`mcp_server.py`** — MCP server with 8 tools. No knowledge of Claude or HTTP. Notes stored in SQLite via `database.py`. Document search via `rag.py` + ChromaDB.

**`agent.py`** — Original CLI version. Same MCP connection logic as `api.py` but uses `input()` instead of HTTP.

```
Browser ──HTTP/SSE──► api.py ──stdio/JSON-RPC──► mcp_server.py
                        │
                        └──► Anthropic API (Claude claude-sonnet-4-6)
```

## Tools (8 total)

| Tool | Notes |
|---|---|
| `get_current_datetime` | No params |
| `calculate` | `eval()` with restricted namespace — only math functions allowed |
| `get_weather` | Mock data dict — replace with real API for production |
| `manage_notes` | SQLite-backed — persists across restarts via `database.py` |
| `list_docs` | Reads `docs/` folder; supports `.txt .md .csv .json .py .html .xml .pdf` |
| `read_doc` | Path traversal blocked; 8000-char cap; PDF via `pypdf` or `pymupdf+Tesseract` |
| `index_docs` | Chunks all docs → embeds with `all-MiniLM-L6-v2` → stores in ChromaDB |
| `search_docs` | Semantic search via ChromaDB; returns top N chunks with relevance scores |

## Adding a New Tool

1. Add a `types.Tool(...)` entry in `list_tools()` in `mcp_server.py`
2. Add an `if name == "tool_name":` handler in `call_tool()` returning `list[types.TextContent]`
3. Restart `api.py` — tool discovery is automatic on each session start

## Persistence

- **SQLite** (`data.db`) — notes table + sessions table. Managed by `database.py`. Auto-created on startup.
- **ChromaDB** (`chroma_db/`) — vector embeddings for semantic doc search. Managed by `rag.py`. Auto-indexed on `api.py` startup.
- Both `data.db` and `chroma_db/` are in `.gitignore` — local only.

## docs/ Folder

Place `.txt`, `.md`, or `.pdf` files here. Scanned PDFs must be pre-converted via `convert_pdfs.py` (Tesseract OCR). Text-based PDFs are read directly via `pypdf`. All docs are auto-indexed into ChromaDB on `api.py` startup. Re-index after adding new files by saying "Re-index my documents" in chat or restarting the server.

## System Prompt Behaviour

Both `api.py` and `agent.py` instruct Claude to call `search_docs` first on every question before falling back to general knowledge or other tools. This ensures document content always takes priority.

## SSL Note (Windows)

`rag.py` patches `httpx.Client.__init__` to disable SSL verification before the HuggingFace model download. This is required on Windows machines with corporate certificate chains. The model (~80MB) is cached after first download.

## Key Dependencies

| Package | Purpose |
|---|---|
| `anthropic[mcp]` | Anthropic SDK + `async_mcp_tool` bridge |
| `mcp` | MCP server/client protocol implementation |
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI web server |
| `pypdf` | Text extraction from text-based PDFs |
| `pymupdf` | Renders PDF pages to images for OCR |
| `pytesseract` | Python wrapper for Tesseract OCR |
| `chromadb` | Vector database for semantic search |
| `sentence-transformers` | Local embedding model (all-MiniLM-L6-v2) |
