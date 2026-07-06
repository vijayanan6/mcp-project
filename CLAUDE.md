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
`GET  /usage/data`    — JSON: totals, by_model, by_day, by_session, by_tool, by_project, credit config
`GET  /usage/data?project=name` — same but filtered to one project
`POST /usage/credit`  — save starting balance and alert threshold `{ starting_balance: 5.00, alert_threshold: 1.00, reset: false }`

Features: credit balance tracker, burn rate ($/day), estimated runway (labeled "Est. Runway" — a burn-rate forecast, not an actual credit expiration; API credits don't expire on a day count), 30/60/90-day cost forecast, per-session cost table, cost by tool, cost by project, low-credit alert badge in chat header (pulses red when remaining < threshold).

### Resetting Spend Tracking (Balance Top-Ups)

A real Anthropic account top-up doesn't mean past spend should keep counting against the new balance. The "Reset spend tracking" checkbox in the credit banner (with a confirm prompt, since it overwrites the single archived snapshot below) sets `reset: true` on `POST /usage/credit`, which:

- Starts a new tracking period from now (`credit_config.period_start`) — remaining balance, burn rate, and forecasts recalculate from that point forward.
- Archives the outgoing period's totals into `prev_period_cost_usd` / `prev_period_days` / `prev_period_end` — a **single slot**, overwritten on every reset. There's a confirm dialog specifically because this data isn't recoverable if you reset twice in a row.
- **Never touches `usage_logs`.** All historical charts (daily chart, per-model, per-session, per-project tables) always show full lifetime data regardless of resets — only the credit banner's live remaining/burn-rate math is period-scoped.

`database.py`'s `credit_status(project=None)` computes the live period's spend/active-days (falling back to all-time totals if never reset, so existing installs behave unchanged). The dashboard JS falls back to the *previous* period's burn rate — marked `(est.)` with a tooltip — for forecasting in the gap right after a reset, before any usage has landed in the new period; it switches to real numbers once a request is logged.

## Multi-Project Support — How to Wire Up a New Project

This dashboard supports multiple projects reporting to a single SQLite database. All data is tagged by `project` column in `usage_logs`.

**To add a second project:**

1. Copy `database.py` into the new project (or import it as a shared module)
2. Point `DB_PATH` to the same `data.db` file used by this project:
   ```python
   DB_PATH = Path("c:/Users/vijay/OneDrive/Desktop/Claude Workspace/MCP Project/data.db")
   ```
3. In the new project's streaming endpoint, pass the project name to `usage_log()`:
   ```python
   usage_log(session_id, model, input, cache_write, cache_read, output,
             tools=tools_called, project="my-new-project")
   ```
4. That's it — the new project appears in the dashboard dropdown automatically.

**Filter in dashboard:** Use the Project dropdown in the header to view one project at a time. All cards, charts, and tables filter to the selected project.

**Future upgrade path:** When deployed to GCP, replace the shared file path with a `POST /usage/log` endpoint so any project anywhere can report usage over HTTP — this is Option A (centralised dashboard). Option C (shared file) works locally; Option A works in production.

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

## .env Encoding Note (Windows)

`.env` must be saved as plain **UTF-8 (no BOM)**. Windows tools (Notepad, some PowerShell
`Set-Content`/`Out-File` defaults) commonly save "UTF-8 with BOM" instead. The BOM character
silently merges with the first line, turning `ANTHROPIC_API_KEY` into an unrecognized variable
name — `python-dotenv` never loads it, and the SDK fails with a generic
`"Could not resolve authentication method"` error even though the key itself is correct.

Verify without exposing the key: `grep -c "^ANTHROPIC_API_KEY=" .env` should return `1`. If it
returns `0`, strip the BOM:
```powershell
$content = Get-Content -Raw -Path .env
[System.IO.File]::WriteAllText(".env", $content, (New-Object System.Text.UTF8Encoding $false))
```
Note `uvicorn --reload` does not watch `.env` for changes — a full process restart is required
after fixing it.

## Playwright MCP (UI Testing)

A Playwright MCP server is configured at project scope in `.mcp.json` (Microsoft's official
`@playwright/mcp` package, no secrets in config, safe to share). It lets Claude Code drive
`chat.html` and `usage.html` in a real browser — navigate, click, type, screenshot — to verify
UI changes actually work, per the testing standard in this file, instead of only reading source.

Screenshots and page snapshots land in `.playwright-mcp/` — gitignored, since they can contain
session IDs and cost data from local testing.

## Security Standard — After Every Change

After any file edit, new dependency, new MCP server, or config change: check `git status` for
new untracked files, confirm nothing secret is in what's about to be committed, and confirm
`.gitignore` covers any new artifact-producing tool (test output, logs, generated screenshots).
Never print a secret value to diagnose it — use structural checks (`grep -c`, redacted `sed`)
instead. This applies to every change in this repo, not just app code.

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
