# MCP Learning Project

A hands-on project to learn **Model Context Protocol (MCP)** by building a custom MCP server,
an AI agent, and a full-stack web application with semantic document search, model routing,
prompt evaluation, and a live AI cost observability dashboard.

---

## What is MCP?

**Model Context Protocol (MCP)** is an open standard that lets AI models (like Claude) call external
tools and services in a structured, language-agnostic way. Think of it like USB — any tool built
to the MCP standard works with any MCP-compatible AI.

---

## Project Structure

```
MCP Project/
├── api.py                  — FastAPI web server (primary entry point)
├── agent.py                — CLI agent (original learning version)
├── mcp_server.py            — MCP server with 8 tools
├── text_editor_tool.py      — Client-side text editor tool, locked to docs/project_notes.md
├── database.py              — SQLite layer (notes, sessions, usage_logs, credit_config)
├── rag.py                   — ChromaDB semantic search
├── convert_pdfs.py          — Tesseract OCR for scanned PDFs
├── inspect_db.py            — Utility to view SQLite contents
├── tool_use_demo.py         — Tool Use Fundamentals demo (WARNING: consumes API credits)
├── templates/
│   ├── chat.html            — Browser chat UI (SSE streaming, credit alert badge)
│   └── usage.html           — AI Cost Dashboard (tokens, cost, forecast, multi-project)
├── docs/                    — Drop your documents here
├── evals/
│   ├── dataset.json         — 12 test cases for tool selection + model routing
│   └── run_evals.py         — Eval runner (WARNING: consumes API credits)
├── .mcp.json                — Project-scoped MCP servers (Playwright, for UI testing)
├── LEARNING_JOURNEY.md      — Full phase-by-phase learning record
├── LEARNING_PLAN.md         — Roadmap to expert AI engineer
├── ARCHITECTURE.md          — System design in plain English
├── INSIGHTS.md              — Key lessons and principles
├── AI_ENGINEERING_PORTFOLIO.md — Skills portfolio (LinkedIn/GitHub facing)
├── GIT_COMMANDS.md          — Git reference used throughout the project
└── requirements.txt
```

---

## Architecture

```
Browser (http://localhost:8000)
  │
  │ HTTP / Server-Sent Events
  ▼
api.py (FastAPI)
  │
  ├──► Claude Sonnet 4.6 / Haiku 4.5 (Anthropic API — routed by query complexity)
  │         │ tool calls
  │         ▼
  ├──► mcp_server.py (8 MCP Tools)
  │         ├──► database.py  → SQLite (notes, sessions, usage_logs, credit_config)
  │         ├──► rag.py       → ChromaDB (semantic document search)
  │         └──► docs/        → your documents (txt, md, PDF)
  │
  ├──► text_editor_tool.py (client-side tool, in-process — locked to docs/project_notes.md)
  │
  └──► web_search (server-side tool — runs on Anthropic's infrastructure, no local code)
```

Three processes run together: the browser, `api.py`, and `mcp_server.py` (spawned as a subprocess
and kept alive for the life of the app). See `ARCHITECTURE.md` for the full request lifecycle.

---

## All 10 Tools

Three different execution models, one `tools` list:

| Tool | Execution | Description |
|---|---|---|
| `get_current_datetime` | MCP | Current date and time |
| `calculate` | MCP | Safe math expression evaluator |
| `get_weather` | MCP | Mock weather data by city |
| `manage_notes` | MCP | Persistent CRUD notes (SQLite) |
| `list_docs` | MCP | Lists files in docs/ folder |
| `read_doc` | MCP | Reads full content of a document |
| `index_docs` | MCP | Indexes docs into ChromaDB for semantic search |
| `search_docs` | MCP | Semantic search — finds relevant chunks for any query |
| `web_search` | Server-side (Anthropic) | Live web search for anything time-sensitive or beyond training data. $10/1,000 searches + token cost. |
| `str_replace_based_edit_tool` | Client-side (local) | Lets Claude view/edit exactly one file — `docs/project_notes.md` — nothing else |

---

## Setup

### Prerequisites
- Python 3.10+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Tesseract OCR (for scanned PDFs): `github.com/UB-Mannheim/tesseract/wiki`

### Install dependencies
```powershell
pip install -r requirements.txt
```

### Set your API key
Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=sk-ant-...
```

> **Windows tip:** save `.env` as plain **UTF-8 (no BOM)**. Notepad and some PowerShell
> commands default to "UTF-8 with BOM," which silently breaks `python-dotenv` and produces a
> `"Could not resolve authentication method"` error even though the key is correct.

### Run the web app
```powershell
python -m uvicorn api:app --reload --port 8000
```

Open **`http://localhost:8000`** for the chat UI, or **`http://localhost:8000/usage`** for the
AI Cost Dashboard.

### Or run the CLI agent
```powershell
python agent.py
```

---

## AI Cost Dashboard

Full observability into what your Claude API usage actually costs — token-level, session-level,
tool-level, and multi-project.

| Endpoint | Purpose |
|---|---|
| `GET /usage` | Visual HTML dashboard |
| `GET /usage/data` | JSON: totals, by_model, by_day, by_session, by_tool, by_project, credit config |
| `GET /usage/data?project=name` | Same, filtered to one project |
| `POST /usage/credit` | Save starting balance + alert threshold |

Features: 4-way token breakdown (input / cache write / cache read / output), cost by model
(Haiku vs Sonnet), 14-day daily usage chart, **30/60/90-day cost forecast**, cost by tool
(MCP and non-MCP — see below), cost by project, per-session cost ranking, a "Web Searches"
stat card, credit balance tracker with burn rate and days remaining, and a low-credit alert
badge that pulses in the chat header.

`web_search`'s flat $10/1,000-searches fee (separate from token costs) is folded into
`estimated_cost_usd` automatically, so it flows into every chart above with no special
handling — see `CLAUDE.md` for how.

**Mobile alerts:** set `DISCORD_WEBHOOK_URL` in `.env` to get real-time Discord push
notifications (via Discord's mobile app) instead of only the passive in-browser badge —
covers low-balance warnings (2 tiers), a spend-spike alert, a per-tool budget alert for
`web_search`, and a daily usage digest. Fully optional; every check no-ops if unset. See
`CLAUDE.md` § Discord Mobile Alerts for the full trigger/cooldown design.

This dashboard tracks **Anthropic API usage only** — not your Claude Pro subscription (a separate,
flat-fee product). See `CLAUDE.md` for the full feature list and multi-project setup instructions.

---

## Model Routing & Prompt Caching

Not every message needs the same model. `_pick_model()` routes short/simple queries to
**Haiku** (10–20× cheaper) and long or document-related queries to **Sonnet**. The system
prompt is marked `cache_control: ephemeral`, saving ~90% of its token cost after the first
call in a 5-minute window. See `LEARNING_JOURNEY.md` Phase 8–9 for the full breakdown.

---

## Eval Pipeline

12 test cases verify Claude follows system prompt rules — correct tool selection and correct
model routing — scored automatically.

```powershell
# Start the app first, then in a second terminal:
python evals/run_evals.py
```

> **Cost warning:** each eval case makes a real Claude API call. 12 cases = 12 API calls.

Currently passing: **12/12 (100%)**. Run after every system prompt or routing change.

---

## UI Testing with Playwright MCP

A Playwright MCP server (Microsoft's official `@playwright/mcp`) is configured at project scope
in `.mcp.json`, letting Claude Code drive `chat.html` and `usage.html` in a real browser —
navigate, click, type, screenshot — instead of only reading source code to guess whether a UI
change works.

```powershell
claude mcp add playwright --scope project -- npx -y @playwright/mcp
```

Restart Claude Code (or reconnect MCP servers) after adding it, then verify with `/mcp`.

No secrets are needed for this server — safe to commit `.mcp.json` and share across a team.
Screenshots and page snapshots it produces land in `.playwright-mcp/`, which is gitignored
since they can capture session IDs and cost data from local testing.

This is more than a nice-to-have: a live end-to-end test of the chat UI is what caught the
`.env` UTF-8 BOM bug documented above — a bug that pure code review would have missed entirely,
since the API key was correct and the failure only appeared once a real request was made.

---

## How to Add a New Tool

**MCP tool** (needs local execution logic — most tools):

**Step 1 — Declare the tool** in `list_tools()` inside `mcp_server.py`:
```python
types.Tool(
    name="my_tool",
    description="What it does and WHEN Claude should use it.",
    inputSchema={"type": "object", "properties": {"param": {"type": "string"}}, "required": ["param"]},
),
```

**Step 2 — Handle it** in `call_tool()` inside `mcp_server.py`:
```python
if name == "my_tool":
    result = do_something(arguments["param"])
    return [types.TextContent(type="text", text=result)]
```

Restart the server — Claude discovers the new tool automatically.

**Anthropic-native tool** (server-side like `web_search`, or client-side like the text editor):
these bypass MCP entirely and are declared directly in `app.state.tools` inside `api.py`'s
lifespan — see `CLAUDE.md` § Adding a New Tool for the server-side vs. client-side pattern
and the `allowed_callers`/model-capability gotcha that broke Haiku-routed requests during
this project's `web_search` rollout.

---

## How to Add Documents

1. Drop `.txt`, `.md`, or `.pdf` files into the `docs/` folder
2. For scanned PDFs: run `python convert_pdfs.py` first
3. Restart the server (auto-indexes on startup) or say *"Re-index my documents"* in chat

---

## RAG — How Semantic Search Works

```
Indexing (once):
  docs/*.txt → split into ~500 char chunks → embed with all-MiniLM-L6-v2 → store in ChromaDB

Querying (every question):
  question → embed → ChromaDB similarity search → top 4 relevant chunks → Claude
```

This handles documents of any size — only the relevant parts are sent to Claude.

---

## Key Concepts

| Concept | File | Purpose |
|---|---|---|
| `@app.list_tools()` | `mcp_server.py` | Declares tools to any MCP client |
| `@app.call_tool()` | `mcp_server.py` | Executes tools and returns results |
| `lifespan` | `api.py` | Keeps MCP server alive across all HTTP requests |
| `StreamingResponse` | `api.py` | SSE streaming to the browser |
| `_pick_model()` | `api.py` | Routes each message to Haiku or Sonnet |
| `usage_log()` | `database.py` | Records tokens, cost, tools called, project per request |
| `init_db()` | `database.py` | Creates SQLite tables on startup |
| `index_all()` | `rag.py` | Chunks + embeds all docs into ChromaDB |
| `search()` | `rag.py` | Semantic similarity search |
| `async_mcp_tool()` | `agent.py` / `api.py` | Bridges MCP tools to Anthropic SDK |
| `BetaAsyncBuiltinFunctionTool` | `text_editor_tool.py` | SDK interface for client-side Anthropic tools — `to_dict()` + `call()` |

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic[mcp]` | Anthropic SDK + MCP integration |
| `mcp` | MCP protocol implementation |
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI web server |
| `pypdf` | Text-based PDF extraction |
| `pymupdf` | PDF → image rendering for OCR |
| `pytesseract` | Tesseract OCR wrapper |
| `chromadb` | Vector database |
| `sentence-transformers` | Local embedding model |
| `python-dotenv` | Loads `.env` into environment variables |
| `httpx` | HTTP client (Anthropic SDK + eval runner) |

---

## Windows SSL Note

Two SSL patches are applied for Windows machines with corporate certificate chains or network
monitoring drivers: `rag.py` defaults `httpx` client `verify=False` for the embedding model
download, and `api.py`'s lifespan clears `SSLKEYLOGFILE` and passes an explicit `httpx.AsyncClient
(verify=False)` to `AsyncAnthropic()`. See `CLAUDE.md` for details.

---

## Documentation

| File | Purpose |
|---|---|
| `CLAUDE.md` | Instructions for Claude Code — commands, architecture, standards |
| `ARCHITECTURE.md` | System design in plain English |
| `LEARNING_JOURNEY.md` | Phase-by-phase build record |
| `LEARNING_PLAN.md` | Roadmap to expert AI engineer |
| `INSIGHTS.md` | Key lessons and principles |
| `TUTORIAL.md` | Beginner teaching guide with exercises |
| `GIT_COMMANDS.md` | All Git commands used, with explanations |
| `AI_ENGINEERING_PORTFOLIO.md` | Skills portfolio for hiring managers |

---

## GitHub

`github.com/vijayanan6/mcp-project`

---

## What's Next

See `LEARNING_PLAN.md` for the full roadmap. Near-term:
- pytest — unit + integration tests for MCP tools and API routes
- Docker + GCP Cloud Run deployment
- PostgreSQL (replacing SQLite) + pgvector (replacing ChromaDB)
- React frontend with authentication (JWT)
- Multi-model support — Gemini, OpenAI, and free local models via Ollama/Groq
- Multi-agent systems and a second project in a different domain
