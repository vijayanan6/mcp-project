# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
# Install all dependencies
pip install anthropic[mcp] mcp pymupdf pytesseract pypdf fastapi "uvicorn[standard]" chromadb sentence-transformers python-dotenv httpx

# Run the web app (primary entry point)
python -m uvicorn api:app --reload --port 8000
# Open: http://localhost:8000

# Run the CLI agent (original learning version)
python agent.py

# Run eval pipeline (WARNING: consumes API credits — 1 Claude API call per test case)
# Start the app first, then in a second terminal:
python evals/run_evals.py

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

## Cost Dashboard & Credit Tracking

`GET  /usage`         — visual HTML dashboard (token usage, cost, daily chart, per-session table)
`GET  /usage/data`    — JSON: totals, by_model, by_day, by_session, credit config
`POST /usage/credit`  — save starting balance and alert threshold `{ starting_balance: 5.00, alert_threshold: 1.00 }`

Features: credit balance tracker, burn rate ($/day), days remaining, per-session cost table, low-credit alert badge in chat header (pulses red when remaining < threshold).

## Persistence

- **SQLite** (`data.db`) — notes, sessions, usage_logs, credit_config tables. Managed by `database.py`. Auto-created on startup.
- **ChromaDB** (`chroma_db/`) — vector embeddings for semantic doc search. Managed by `rag.py`. Auto-indexed on `api.py` startup.
- Both `data.db` and `chroma_db/` are in `.gitignore` — local only.

## docs/ Folder

Place `.txt`, `.md`, or `.pdf` files here. Scanned PDFs must be pre-converted via `convert_pdfs.py` (Tesseract OCR). Text-based PDFs are read directly via `pypdf`. All docs are auto-indexed into ChromaDB on `api.py` startup. Re-index after adding new files by saying "Re-index my documents" in chat or restarting the server.

## System Prompt Behaviour

`api.py` uses a smart system prompt that tells Claude to call `search_docs` first for topic-specific questions (people, projects, subjects) but skip it for clearly general questions (math, weather, time). This avoids unnecessary tool calls while still prioritising document content.

The prompt is defined as `SYSTEM_PROMPT` with `cache_control: ephemeral` so Anthropic caches it across turns — saving ~90% of those input tokens after the first call.

Conversation history is capped at the last **10 messages** (`HISTORY_LIMIT`) to keep context size bounded. Full history is still persisted to SQLite; only the window sent to Claude is trimmed.

## SSL Note (Windows)

Two SSL patches are applied on Windows machines with corporate certificate chains or network monitoring drivers:

1. **`rag.py`** — patches `httpx.Client.__init__` and `httpx.AsyncClient.__init__` to default `verify=False` before the HuggingFace model download. The model (~80MB) is cached after first download.
2. **`api.py` lifespan** — clears the `SSLKEYLOGFILE` environment variable (set by monitoring drivers like `nllMonFltProxy`) and passes `httpx.AsyncClient(verify=False)` explicitly to `AsyncAnthropic()` to prevent SSL context creation failures.

## Git Workflow

See `GIT_COMMANDS.md` for the full reference. Standard workflow:

```powershell
git checkout -b feature/name     # new feature branch
git add .
git commit -m "feat: description"
git checkout main
git merge feature/name
git push origin main
```

Commit prefix conventions: `feat:` new feature — `docs:` documentation — `fix:` bug fix

## Eval Pipeline

`evals/dataset.json` — 12 test cases covering tool selection and model routing
`evals/run_evals.py` — runner that calls `/chat`, scores results, exits 1 on failure

Currently passing: **12/12 (100%)**

Run after every system prompt change or model routing change to catch regressions.

## Documentation Files

| File | Purpose |
|---|---|
| `README.md` | Project overview and setup |
| `ARCHITECTURE.md` | System design in plain English |
| `LEARNING_JOURNEY.md` | Phase-by-phase build record |
| `INSIGHTS.md` | Key lessons and principles |
| `TUTORIAL.md` | Beginner teaching guide with exercises |
| `GIT_COMMANDS.md` | All Git commands used with explanations |
| `AI_ENGINEERING_PORTFOLIO.md` | LinkedIn/GitHub portfolio of skills |

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
| `python-dotenv` | Loads `.env` file into environment variables |
| `httpx` | HTTP client used by eval runner and Anthropic SDK |
