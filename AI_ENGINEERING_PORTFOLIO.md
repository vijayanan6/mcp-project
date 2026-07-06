# Applied AI Engineer — LLM Systems, MCP & RAG | Vijay Anantaneni

> Built a production-grade AI assistant from scratch — no tutorials, no boilerplate.
> Every concept below was learned by implementing it in running code.

---

## What I Built

A full-stack AI application where Claude (Anthropic's LLM) uses custom tools to answer questions, search documents semantically, and maintain persistent multi-turn conversations across browser sessions.

```
Browser ──HTTP/SSE──► FastAPI (api.py) ──stdio/JSON-RPC──► MCP Server (mcp_server.py)
                           │                                        │
                           └──► Anthropic API (Claude)      SQLite + ChromaDB
```

**Portfolio:** [github.com/vijayanan6/mcp-project/blob/main/AI_ENGINEERING_PORTFOLIO.md](https://github.com/vijayanan6/mcp-project/blob/main/AI_ENGINEERING_PORTFOLIO.md)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Claude Sonnet 4.6 / Haiku 4.5 (Anthropic) |
| AI Protocol | MCP (Model Context Protocol) |
| Web Framework | FastAPI + Uvicorn |
| Vector Database | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Relational Database | SQLite |
| PDF Processing | pypdf, pymupdf, Tesseract OCR |
| Language | Python 3.12 |
| Version Control | Git + GitHub |
| UI Testing | Playwright MCP (browser automation via Claude Code) |

---

## Skills & Concepts — Implemented, Not Just Studied

### 1. MCP — Model Context Protocol

Anthropic's open standard for connecting LLMs to external tools. Built a custom MCP server exposing 8 tools over stdio/JSON-RPC — not using a pre-built connector, implementing the protocol directly.

**Tools built:** `get_current_datetime`, `calculate`, `get_weather`, `manage_notes`, `list_docs`, `read_doc`, `index_docs`, `search_docs`

```python
@app.list_tools()
async def list_tools():
    return [types.Tool(name="search_docs", description="...", inputSchema={...})]

@app.call_tool()
async def call_tool(name, arguments):
    return [types.TextContent(type="text", text=result)]
```

---

### 2. RAG — Retrieval Augmented Generation

Built the full pipeline from scratch: chunk → embed → store → search → retrieve. No LangChain wrapper.

```
User question → embed → ChromaDB similarity search → top 4 chunks → Claude → answer
```

- Chunking with overlap (500 char chunks, 100 char overlap at natural boundaries)
- Local embedding model: `all-MiniLM-L6-v2` via `sentence-transformers`
- Auto-indexes on server startup; re-index by chat command
- Supports `.txt`, `.md`, `.csv`, scanned PDFs (via OCR)

---

### 3. Streaming — Server-Sent Events

Real-time response streaming from Claude to the browser as text is generated — the same pattern used by ChatGPT and Claude.ai.

```python
async def generate():
    async for msg in runner:
        if block.type == "text":
            yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"

return StreamingResponse(generate(), media_type="text/event-stream")
```

Event types: `tool` (tool being called), `text` (chunk), `done` (model + token breakdown), `error`

---

### 4. Prompt Caching

System prompt marked with `cache_control: ephemeral` — saves ~90% of system prompt token costs after the first API call in a 5-minute window.

```python
SYSTEM_PROMPT = [{
    "type": "text",
    "text": "You are a helpful assistant...",
    "cache_control": {"type": "ephemeral"}
}]
```

Token breakdown tracked per response: `input`, `cache_write`, `cache_read`, `output` — displayed live in the UI.

---

### 5. Model Routing

Automatically routes each query to the cheapest model that can handle it — Haiku (10–20× cheaper) for simple queries, Sonnet for complex/document queries.

```python
def _pick_model(message: str) -> str:
    if len(message) > 120 or any(signal in message.lower() for signal in _COMPLEX_SIGNALS):
        return "claude-sonnet-4-6"
    return "claude-haiku-4-5"
```

---

### 6. Persistent Conversation History

Multi-turn sessions stored in SQLite. Full history saved to DB; only the last 10 messages sent to Claude (caps token cost without losing continuity).

- `_safe_window()` — guards against orphaned `tool_result` turns at the history boundary
- Empty assistant turn guard — never corrupts history on partial responses
- Sessions survive server restarts and browser refreshes

---

### 7. FastAPI + Async Python

- Lifespan hooks keep the MCP server alive across all requests (not spawned per request)
- Pydantic request validation, async route handlers
- `app.state` shares tools and API client across all requests
- REST endpoints: `GET /`, `GET /tools`, `POST /chat`, `POST /stream`, `GET /sessions`, `DELETE /session/{id}`

---

### 8. PDF OCR Pipeline

- Text-based PDFs: extracted directly via `pypdf`
- Scanned PDFs: `pymupdf` renders pages to images at 300 DPI → `pytesseract` extracts text
- Path traversal protection on all file access

---

### 9. Configuration & Security

- `.env` + `python-dotenv` for API key management (industry standard)
- `temperature=0.3` — tuned for a tool-using assistant (consistent, not creative)
- SSL workaround for Windows corporate certificate chains
- Diagnosed a silent auth failure caused by a UTF-8 byte-order-mark in `.env` — root-caused via structural checks (`grep -c "^ANTHROPIC_API_KEY="`) rather than ever printing the key itself
- Evaluated a third-party MCP server (Playwright, Microsoft's official package) before installing — checked publisher trust, exact access boundary (browser automation only, no filesystem/shell reach), and where prompt-injection risk actually lives (untrusted external content, not applicable when testing `localhost`)
- Standing discipline: after every new file, dependency, or MCP server, check `git status` for untracked artifacts and confirm `.gitignore` covers them before considering a change complete — caught a real gap where Playwright's screenshot/snapshot output wasn't ignored and could have leaked session data into the public repo

---

### 10. AI Cost Dashboard & Credit Tracking

Built a full observability layer for LLM API spend — the same class of tooling used in enterprise AI platforms to control costs.

**What it tracks:**
- Token usage per turn: `input`, `cache_write`, `cache_read`, `output` — broken out per model
- Estimated USD cost per message, accumulated in SQLite (`usage_logs` table)
- Per-session cost breakdown — top 10 sessions ranked by spend
- Daily usage bar chart (14-day rolling window, hover tooltips)
- Cost forecast — 30/60/90 day projected spend based on burn rate (pure frontend math, no backend changes)

**Credit tracker (with alerting):**
```
Starting balance: $5.00 | Alert threshold: $1.00
───────────────────────────────────────
Remaining: $4.72   Burn rate: $0.14/day   Est. Runway: ~33d
Progress:  ████████░░░░░░░░░░░░  5.6% used
```

- `POST /usage/credit` — saves balance + alert threshold to `credit_config` SQLite table (singleton row, upserted); optional `reset: true` starts a fresh spend-tracking period (see below)
- Progress bar changes colour: green → yellow (< 2× threshold) → red (below threshold)
- **Low-credit alert badge** in the chat UI header pulses red when remaining balance falls below the threshold — checked every 60 seconds live
- **"Est. Runway" is a forecast, not a limit** — labeled explicitly (with a tooltip) as `remaining ÷ burn rate`, not an actual credit expiration, after the plain "Days Left" label was found to imply a hard, calendar-based cutoff that doesn't exist for API credits

**Non-destructive spend-period reset (for real balance top-ups):**

A real Anthropic account top-up shouldn't blend with lifetime spend when computing what's "remaining." A confirm-gated checkbox in the credit banner sets `reset: true`, which:
- Starts a new tracking period (`credit_config.period_start`) — remaining/burn-rate/forecast recalculate from that point forward
- Archives the outgoing period's cost + active-days into a single `prev_period_*` snapshot, shown in the banner
- Never touches `usage_logs` — every historical chart and table always reflects full lifetime data regardless of resets

```python
# database.py
def credit_status(project=None) -> dict:
    """Credit config + spend/active-days scoped to the current period
    (since last reset, or all-time if the feature has never been used)."""
```

**Endpoints:**
| Route | Purpose |
|-------|---------|
| `GET /usage` | Visual HTML dashboard |
| `GET /usage/data` | JSON: totals, by_model, by_day, by_session, by_tool, by_project, period-scoped credit status |
| `GET /usage/data?project=name` | Same but filtered to one project |
| `POST /usage/credit` | Save starting balance and alert threshold; `reset: true` archives the current period and starts fresh |

**Multi-project support (Option C — multi-tenancy at the data layer):**

Added `project` column to `usage_logs` so multiple AI projects can report to the same dashboard. Dashboard shows a project filter dropdown — switch between projects and all cards, charts, and tables update.

```python
# Any new project reports with one line
usage_log(session_id, model, ..., project="my-new-project")
```

This is the same multi-tenancy pattern used in enterprise SaaS — one database, multiple tenants isolated by a tag column (`org_id` in Salesforce, `account_id` in Stripe, `project` here).

**Upgrade path to Option A (centralised HTTP endpoint):** Deploy dashboard to GCP Cloud Run → expose `POST /usage/log` → any project anywhere reports over HTTP. Option C works locally; Option A works in production.

**Cost by Tool breakdown:**

Every MCP tool call is now tracked — stored as a JSON array in `tools_used` column of `usage_logs`, aggregated via SQLite's `json_each()`:

```sql
SELECT json_each.value AS tool_name, COUNT(*) AS calls,
       SUM(estimated_cost_usd) AS cost_usd, AVG(estimated_cost_usd) AS avg_cost_usd
FROM usage_logs, json_each(usage_logs.tools_used)
GROUP BY json_each.value ORDER BY calls DESC
```

The dashboard shows which tools are called most and what they cost — `search_docs` dominates because it routes to Sonnet with document context; `get_weather` is nearly free.

**Token economics understood:**
```
Claude reads  → INPUT  tokens  → you pay input price
Claude writes → OUTPUT tokens  → most expensive per token (3–5×)
Cache hit     → READ   tokens  → 10× cheaper than input
System prompt cached after message 1 → near-free on every subsequent turn
```

**Key engineering decision:** cost is estimated from token counts × pricing table — no extra API call. Schema migration handled safely with `ALTER TABLE ... ADD COLUMN` + try/except.

---

### 11. Prompt Evaluation Pipeline

Built an eval pipeline to verify Claude follows system prompt rules — not manually, but automatically with a scored pass/fail report.

```
evals/dataset.json   → 12 test cases (expected tool + expected model per input)
evals/run_evals.py   → calls /chat, scores tool selection + model routing, reports %
```

**Result: 12/12 (100%) passing**

```
doc-001   List files → list_docs       OK  OK   PASS
doc-002   Summarize  → search_docs     OK  OK   PASS
math-001  Math       → no tool, Haiku  OK  OK   PASS
notes-001 Save note  → manage_notes    OK  OK   PASS
...
Score: 12/12 (100%) — All evals passed!
```

Evals caught two real bugs that manual testing missed:
- `/chat` endpoint was not returning the `model` field in its response
- System prompt was ambiguous about `search_docs` vs `list_docs`

---

## Key Engineering Decisions

| Decision | Why |
|----------|-----|
| MCP over direct tool calls | Standard protocol — portable across any MCP-compatible client |
| ChromaDB over in-memory search | Persists embeddings across restarts |
| SQLite for sessions | Production pattern — survives restarts, zero setup |
| Prompt caching | ~90% token savings on system prompt at scale |
| Model routing | 10–20× cost reduction for simple queries |
| SSE over WebSockets | Simpler for one-directional streaming; sufficient for chat |
| `temperature=0.3` | Tool-using assistants need consistency, not creativity |
| `.env` over OS env vars | Portable, project-scoped, git-ignored |
| Client-side cost estimation | Token count × pricing table — no extra API call needed |
| Credit alert in chat header | Surface spend pressure where the user is working, not a separate admin screen |

---

## AI-Powered Engineering — Claude Code

This entire project was built using **Claude Code** as an AI-powered development environment — not just as a chatbot, but as an integrated engineering tool.

### How I use Claude Code professionally

| Capability | How I use it |
|------------|-------------|
| **AI pair programming** | Build features, debug issues, and refactor code through natural language in the terminal |
| **`/code-review`** | Run structured code reviews at configurable depth before every commit |
| **`/verify`** | Confirm a change works in the running app, not just in tests |
| **`/simplify`** | Audit changed code for reuse, efficiency, and unnecessary complexity |
| **`/security-review`** | Review pending changes for OWASP-level vulnerabilities |
| **MCP servers** | Evaluated and wired up Playwright MCP (Microsoft's official browser-automation server) at project scope — assessed publisher trust, access boundary, and prompt-injection risk before installing, then used it to drive the chat UI and cost dashboard end-to-end, which caught a real `.env` encoding bug (UTF-8 BOM silently breaking API auth) that code review alone had missed |
| **Hooks** | Automate lifecycle actions (PreToolUse, PostToolUse, SessionStart) |
| **Skills** | Custom slash commands for project-specific workflows |
| **Memory system** | Persistent context across sessions — project state, preferences, learning path |
| **Subagents** | Spawn parallel agents for independent research or code tasks |

### Why this matters for engineering teams

Claude Code changes how engineering work gets done — not by replacing engineers, but by eliminating the friction between intent and implementation. An engineer who knows how to use AI tooling effectively ships faster, catches more bugs, and spends more time on architecture decisions than boilerplate.

Using Claude Code throughout this project means every decision — from database choice to token optimization to security — was made with AI-assisted reasoning, then verified against the running code.

---
                                                                                                                                                                                                                                          
## What's Next

| Phase | Concept |
|-------|---------|                                                                                                   
| Testing (pytest) | Unit + integration tests for MCP tools and API endpoints |
| Docker | Containerisation and portability |
| PostgreSQL | Production database (replacing SQLite) |
| GCP Cloud Run | Cloud deployment |
| React Frontend | Replace chat.html with a proper React UI |
| Authentication (JWT) | Multi-user, secure sessions |

---

*Full learning journey documented in [LEARNING_JOURNEY.md](LEARNING_JOURNEY.md)*
