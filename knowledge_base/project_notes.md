# MCP Learning Project Notes

## What I Built
A full-stack AI application starting from a CLI script and growing into a
web application with browser chat UI, image/PDF attachments, persistent
database, semantic document search, and a full AI cost observability
dashboard with Discord mobile alerts.

---

## Final Architecture

```
Browser (http://localhost:8000)
  │
  │ HTTP / Server-Sent Events
  ▼
api.py (FastAPI web server)
  │
  ├──► Claude Sonnet 4.6 / Haiku 4.5 (Anthropic API — routed by query complexity)
  │         │ tool calls
  │         ▼
  ├──► mcp_server.py (8 MCP tools)
  │         ├──► database.py     → SQLite (notes, sessions, usage_logs, credit_config)
  │         ├──► rag.py          → ChromaDB (semantic search)
  │         └──► knowledge_base/ → documents (txt, md, PDF)
  │
  ├──► text_editor_tool.py (client-side tool — locked to knowledge_base/project_notes.md)
  │
  ├──► web_search (server-side tool — runs on Anthropic's infrastructure)
  │
  ├──► image/PDF attachments (Messages API content blocks — ephemeral, one per turn, PDF citations)
  │
  ├──► Discord webhook (mobile alerts — low balance, spend spike, tool budget, daily digest)
  │
  └──► agent.py (original CLI — still works)
```

Reorganized in Phase 22 into a standard `src/backend/`, `src/frontend/`, `scripts/`, `docs/`,
`data/` layout — see "Project Files" below for current paths.

---

## All 10 Tools

Three execution models share one `tools` list — not everything is an MCP tool.

| Tool | Execution | What it does | Storage |
|---|---|---|---|
| `get_current_datetime` | MCP | Current date and time | — |
| `calculate` | MCP | Safe math expression evaluator | — |
| `get_weather` | MCP | Mock weather data for cities | — |
| `manage_notes` | MCP | CRUD for personal notes | SQLite |
| `list_docs` | MCP | Lists files in `knowledge_base/` folder | Filesystem |
| `read_doc` | MCP | Reads a full document | Filesystem |
| `index_docs` | MCP | Indexes docs into ChromaDB | ChromaDB |
| `search_docs` | MCP | Semantic search across all docs | ChromaDB |
| `web_search` | Server-side (Anthropic) | Live web search for time-sensitive info | — |
| `str_replace_based_edit_tool` | Client-side (local) | Views/edits exactly this file, nothing else | Filesystem |

Image/PDF attachments (chat 📎 button) are a separate, non-tool capability — a native Anthropic
Messages API content-block feature, not one of the 10 tools above.

---

## Key Learnings

### MCP
1. MCP uses JSON-RPC 2.0 over stdio (local) or HTTP/SSE (network)
2. Claude never runs code directly — it returns a JSON tool_use block
3. Tool descriptions tell Claude WHEN to use each tool — most important part
4. `tool_runner` in Anthropic SDK automates the full tool-call loop
5. `async_mcp_tool()` bridges MCP tools to the Anthropic SDK

### FastAPI
6. `lifespan` keeps the MCP server alive across all HTTP requests
7. Server-Sent Events (SSE) streams Claude's response in real time to the browser
8. `app.state` shares the MCP tools and Claude client across all route handlers
9. Pydantic models auto-validate incoming request bodies

### SQLite
10. In-memory dicts are lost on restart — SQLite persists forever
11. `INSERT OR REPLACE` is the upsert pattern in SQLite
12. Sessions stored as JSON in a TEXT column — flexible for conversations, and just as flexible
    for an ephemeral attachment marker (plain text only, never the binary — see Image/PDF Attachments below)

### RAG
13. RAG = chunk documents → embed → store in vector DB → search by meaning
14. Embedding converts text to vectors; similar meaning = similar vectors
15. ChromaDB stores vectors and finds closest matches to a query
16. Chunking splits large files into ~500 char pieces with overlap
17. Much cheaper than reading entire documents — only sends relevant parts to Claude

### Cost Observability
18. Token counts × a pricing table = estimated cost, no extra API call needed
19. Model routing (Haiku vs Sonnet) is a 10–20x cost lever for simple queries
20. Server-side tool fees (e.g. `web_search`'s $0.01/search) are invisible to token counts —
    they need their own tracked field, unlike image/PDF tokens which bill as ordinary input tokens
21. A background scheduler assumes the process is always running — piggybacking the daily
    digest on real request traffic instead avoids silently missing days

### Image + PDF Attachments
22. Ephemeral by design: the attachment is sent to Claude for one turn only, built in a
    throwaway message list — session history in SQLite only ever stores plain text
23. PDF citations need a real embedded text layer — a rasterized/image-only PDF reads fine via
    vision but has nothing for Claude to cite a page number against
24. Always verify a library's actual response shape with a raw test call before writing
    extraction code against an assumed structure — a wrong `getattr` chain fails silently, with
    no error to point back at the bug

### Git & GitHub
25. Feature branches keep main always working
26. `git checkout -b feature/name` → code → commit → merge → push
27. `.gitignore` protects sensitive files and local databases from being uploaded
28. A pre-commit secret scanner (gitleaks) and SSH commit signing catch what code review can't

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Claude Sonnet 4.6 / Haiku 4.5 (routed by query complexity) |
| AI SDK | `anthropic[mcp]` |
| Tool Protocol | MCP (Model Context Protocol) |
| Native Tools | `web_search` (server-side), text editor (client-side), image/PDF attachments (content blocks) |
| Web Framework | FastAPI |
| Web Server | Uvicorn |
| Database | SQLite (built-in Python) |
| Vector Database | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| PDF Text | pypdf |
| PDF OCR | pymupdf + Tesseract |
| Mobile Alerts | Discord webhooks |
| UI Testing | Playwright MCP |
| Version Control | Git + GitHub (SSH-signed commits, gitleaks pre-commit hook) |
| Language | Python 3.12 |

---

## Project Files

| File | Purpose |
|---|---|
| `src/backend/mcp_server.py` | MCP server — defines and runs all 8 MCP tools |
| `src/backend/agent.py` | CLI agent (original learning version) |
| `src/backend/api.py` | FastAPI web server — SSE streaming, cost dashboard, alerts, attachments |
| `src/backend/database.py` | SQLite layer — notes, sessions, usage_logs, credit_config |
| `src/backend/rag.py` | ChromaDB indexing + semantic search |
| `src/backend/text_editor_tool.py` | Client-side tool, locked to this file only |
| `src/frontend/chat.html` | Browser chat UI (SSE streaming, 📎 attachments, credit alert badge) |
| `src/frontend/usage.html` | AI Cost Dashboard |
| `scripts/convert_pdfs.py` | Tesseract OCR for scanned PDFs |
| `scripts/inspect_db.py` | Utility to view SQLite contents |
| `scripts/tool_use_demo.py` | Tool Use Fundamentals demo — raw SDK, no `tool_runner` |
| `CLAUDE.md` | Guidance for Claude Code |
| `README.md` | Project documentation |
| `docs/LEARNING_JOURNEY.md` | Full phase-by-phase learning record |

---

## How to Run

```powershell
# Set API key (one-time) — in a .env file at the project root, plain UTF-8 no BOM
ANTHROPIC_API_KEY=sk-ant-...

# Start the web app — from the project root
python -m uvicorn api:app --reload --port 8000 --app-dir src/backend

# Open browser at http://localhost:8000 (chat) or http://localhost:8000/usage (cost dashboard)
```

---

## GitHub Repository
`github.com/vijayanan6/mcp-project`

---

## Next Steps to Explore
- Added image/PDF attachment support with PDF citations, and an available-credit line in the
  Discord daily digest, today
- Replace mock weather with real OpenWeatherMap API
- Add user authentication (JWT tokens)
- Switch from SQLite to PostgreSQL
- Deploy to cloud (Railway / Render / GCP Cloud Run)
- Add React frontend
- Connect GitHub MCP server to manage the repo from chat
