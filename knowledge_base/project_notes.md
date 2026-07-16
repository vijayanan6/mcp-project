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
  ├──► mcp_server.py (8 MCP tools, 2 resource kinds, 1 prompt)
  │         ├──► database.py     → SQLite (notes, sessions, usage_logs, credit_config, pricing_warnings)
  │         ├──► rag.py          → ChromaDB (semantic search)
  │         └──► knowledge_base/ → documents (txt, md, PDF)
  │
  ├──► text_editor_tool.py (client-side tool — locked to knowledge_base/project_notes.md)
  │
  ├──► web_search (server-side tool — runs on Anthropic's infrastructure)
  │
  ├──► image/PDF attachments (Messages API content blocks — ephemeral, one per turn, PDF citations)
  │
  ├──► /resources, /prompts (GET/POST routes — MCP resources/prompts, reachable from the running app, not just a standalone script)
  │
  ├──► Discord webhook (mobile alerts — low balance ×2, spend spike, tool budget, daily digest, missing pricing data)
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
29. A `Closes #N` trailer in a commit message auto-closes the issue the moment it reaches `main`
    — before any follow-up command you queue up (like posting a review summary) gets to run
    against the issue's still-open state

### Reliability & Verification
30. A well-known problem ("handle rate limits") doesn't mean it's unsolved in your stack —
    `AsyncAnthropic` already retries 429/5xx/timeouts internally with backoff; verified by
    reading the SDK's actual source before building a second, redundant retry loop on top of it
31. A feature can be "verified" via a standalone test script and still be completely unreachable
    in the real running app — MCP resources/prompts worked perfectly in isolated testing while
    `api.py` never actually called `list_resources()`/`list_prompts()` at all
32. Deduplication bugs come from parallel evolution: `/chat` and `/stream` each grew their own
    copy of the same guard/formatting logic. Fix is structural (hoist to one shared function),
    not cosmetic (keep two copies "in sync" by hand)

### Multi-Agent Orchestration
33. A subagent shares zero context with the conversation that spawned it — the whole quality of
    what it returns depends on how self-contained the brief you give it is
34. Tool access is a real architectural control, not just an instruction — a review agent given
    no Edit/Write tools is *structurally* unable to fix instead of critique, not just told not to
35. Trust but verify applies to agent output too — independently re-checked a drafter's diff via
    `git diff` rather than its self-report, and had the reviewer re-read the live file itself
    rather than trust the diff it was handed

### Async & Concurrency
36. `anyio` cancel scopes (and the TaskGroups built on them) are bound to the asyncio Task that
    opened them — trying to close/exit one from a *different* Task raises "cancel scope in a
    different task than it was entered in" and can cancel unrelated in-flight work, not just the
    resource you meant to close. Found by actually killing a live subprocess mid-session, not
    simulating it, across three different mitigation attempts before landing on the honest fix
37. Not every checklist item should be fully implemented — a correct architectural fix (a
    dedicated task owning a resource for the app's whole lifetime) can still be the wrong call for
    an app whose actual failure rate and uptime requirements don't justify the complexity

### Security & Validation
38. A tool's declared JSON Schema is a description for Claude, not an enforcement mechanism —
    a schema saying `n_results: integer` doesn't stop a malformed or unexpected value from
    reaching the code; 4 of 5 tested invalid values genuinely crashed a tool before validation
    was added
39. Exceptions can't cross a process boundary by reference, only by reconstruction from a
    protocol response — a `ValueError` raised inside `mcp_server.py` arrives client-side as
    `mcp.shared.exceptions.McpError`, a completely different type, because the two processes
    only share a JSON-RPC pipe, not memory
40. Structural separation beats a policy you have to remember — "never mix dev and prod data"
    went from a rule to hold onto, to something physically impossible once dev and any other
    environment resolve to genuinely different files by construction

### Measurement & Aggregation
41. Measure before optimizing — the instinct was "add database indexes," but timing the actual
    queries first (2.89ms total) showed they weren't the bottleneck; the real, measurable waste
    was a dashboard polling every 30s with no check for tab visibility
42. Summing a shared cost across a flattened one-to-many relationship (a JSON array exploded via
    `json_each`, one row fanned into many) multiplies that cost by however many child rows came
    from the same parent, if you don't deduplicate before summing — a real bug, caught only
    because a human looked closely at one specific dashboard number and asked "why is this exactly
    3x a plausible amount"

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
- Remaining Observability & Logging items: structured Python `logging` (replacing ad-hoc
  `print()`/`_log()`), full tracebacks logged to a file, request latency tracking, Langfuse
  free-tier tracing
- Testing with pytest — currently 0/8, fully unstarted
- Replace mock weather with real OpenWeatherMap API
- Add user authentication (JWT tokens)
- Switch from SQLite to PostgreSQL
- Deploy to cloud (Railway / Render / GCP Cloud Run)
- Add React frontend
- Connect GitHub MCP server to manage the repo from chat
