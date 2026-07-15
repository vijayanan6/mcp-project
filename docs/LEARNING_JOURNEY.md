# MCP Learning Project — Full Journey

A complete record of building an AI-powered application from scratch,
starting with a Python script and growing into a full-stack web application.

---

## Phase 1 — MCP Fundamentals

### What We Built
A custom MCP server with 4 tools and a CLI agent that used Claude to answer questions.

### Key Concepts Learned
- **MCP** (Model Context Protocol) is an open standard for connecting AI to external tools
- Every MCP setup has two sides: a **server** (defines/runs tools) and a **client** (connects and calls them)
- **stdio transport** — server runs as a local subprocess, communicates via stdin/stdout using JSON-RPC
- **Tool descriptions** are what Claude reads to decide *when* to use a tool — not just what it does
- Claude never runs your code directly — it returns a JSON blob saying "call this tool with these inputs"
- `tool_runner` in the Anthropic SDK automates the full tool-call loop automatically

### Tools Built
| Tool | Description |
|---|---|
| `get_current_datetime` | Returns current date and time |
| `calculate` | Safe `eval()` with restricted namespace |
| `get_weather` | Mock weather data by city |
| `manage_notes` | In-memory CRUD for text notes |

### Architecture
```
You → agent.py → Claude API → (tool call) → mcp_server.py → result → Claude → You
```

### Files Created
- `mcp_server.py` — MCP server with 4 tools
- `agent.py` — CLI agent
- `requirements.txt` — dependencies

### Key Code Patterns
```python
# Declaring a tool (mcp_server.py)
@app.list_tools()
async def list_tools():
    return [types.Tool(name="...", description="...", inputSchema={...})]

# Executing a tool (mcp_server.py)
@app.call_tool()
async def call_tool(name, arguments):
    return [types.TextContent(type="text", text="result")]

# Connecting and using tools (agent.py)
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        tools = [async_mcp_tool(t, session) for t in (await session.list_tools()).tools]
        runner = client.beta.messages.tool_runner(model="claude-sonnet-4-6", tools=tools, ...)
        async for msg in runner: ...
```

### Commands
```bash
pip install anthropic[mcp] mcp
python agent.py
```

---

## Phase 2 — Document Reading

### What We Built
Two new MCP tools that let Claude read files from a local `docs/` folder.

### Key Concepts Learned
- MCP tools can access the filesystem — Claude can "browse" your files
- Path traversal attacks — always validate file paths stay within the allowed folder
- Truncation is important — large files need to be capped to fit Claude's context window
- **Tool descriptions** drive behaviour — adding "Call list_docs first" changed how Claude behaved

### Tools Added
| Tool | Description |
|---|---|
| `list_docs` | Lists all readable files in docs/ folder |
| `read_doc` | Reads full content of a specific file |

### Supported File Types
`.txt`, `.md`, `.csv`, `.json`, `.py`, `.html`, `.xml`, `.pdf`

### Key Code Pattern
```python
# Security: block path traversal
target = (docs_dir / filename).resolve()
if not str(target).startswith(str(docs_dir.resolve())):
    return [types.TextContent(type="text", text="Access denied")]
```

### System Prompt Change
```python
# Instructed Claude to always check docs first
system = "ALWAYS call list_docs first to check if relevant documents exist..."
```

---

## Phase 3 — PDF OCR

### What We Built
A standalone script `convert_pdfs.py` that converts scanned PDFs into readable `.txt` files using Tesseract OCR.

### Key Concepts Learned
- PDFs come in two types: **text-based** (pypdf can read) and **scanned** (images, need OCR)
- **OCR** (Optical Character Recognition) converts images of text into actual text
- `pymupdf` renders PDF pages into images at high DPI (300 DPI for best accuracy)
- `pytesseract` runs Tesseract on those images and extracts text
- Tesseract must be installed as a system executable, not just a Python package

### Tools & Libraries
| Library | Purpose |
|---|---|
| `pypdf` | Extract text from text-based PDFs |
| `pymupdf` | Render PDF pages to images |
| `pytesseract` | Python wrapper for Tesseract OCR |
| Tesseract exe | The actual OCR engine (installed separately) |

### Flow
```
Scanned PDF → pymupdf renders pages → images → pytesseract OCR → .txt file
```

### Commands
```bash
# Install Tesseract from: github.com/UB-Mannheim/tesseract/wiki
pip install pymupdf pytesseract
python convert_pdfs.py
```

---

## Phase 4 — FastAPI Web Layer

### What We Built
Replaced the CLI (`agent.py`) with a web server (`api.py`) + browser chat UI (`templates/chat.html`).

### Key Concepts Learned
- **FastAPI** is a modern Python web framework — fast, async, with automatic validation
- **Lifespan** — startup/shutdown hooks that keep the MCP server alive across all requests
- **Pydantic models** — automatic request body validation with type hints
- **Server-Sent Events (SSE)** — streams responses in real time from server to browser
- **`app.state`** — shares objects (tools, client) across all request handlers
- **Session management** — tracking conversation history per user via session IDs
- `agent.py` vs `api.py` — same Claude logic, different interface (terminal vs web)

### API Endpoints
| Endpoint | Method | What it does |
|---|---|---|
| `/` | GET | Serves the chat UI |
| `/tools` | GET | Lists available MCP tools |
| `/chat` | POST | Full response (non-streaming) |
| `/stream` | POST | Real-time streaming via SSE |
| `/sessions` | GET | Lists all sessions |
| `/session/{id}` | DELETE | Clears a session |

### Key Code Patterns
```python
# Lifespan — keep MCP server alive for all requests
@asynccontextmanager
async def lifespan(app):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            app.state.tools = [async_mcp_tool(t, session) for t in ...]
            yield   # app runs here; cleanup on exit

# SSE Streaming
async def generate():
    async for msg in runner:
        yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

return StreamingResponse(generate(), media_type="text/event-stream")
```

### Commands
```bash
pip install fastapi "uvicorn[standard]"
python -m uvicorn api:app --reload --port 8000
# Open: http://localhost:8000
```

---

## Phase 5 — SQLite Persistence

### What We Built
Replaced in-memory Python dicts with a real SQLite database so notes and chat sessions survive restarts.

### Key Concepts Learned
- **In-memory storage** is lost every time the app restarts — not suitable for production
- **SQLite** is a file-based database built into Python (`import sqlite3`) — no server needed
- `CREATE TABLE IF NOT EXISTS` — safe to call on every startup
- `INSERT OR REPLACE` — upsert pattern (insert if new, replace if exists)
- Sessions stored as **JSON** in a TEXT column — flexible for variable-length conversations
- `row_factory = sqlite3.Row` — makes rows behave like dictionaries
- **Feature branches** in Git — work on a feature without breaking the working app

### Database Schema
```sql
CREATE TABLE notes (
    title      TEXT PRIMARY KEY,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    messages   TEXT NOT NULL,   -- JSON array of {role, content} objects
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Before vs After
| | Before | After |
|---|---|---|
| Notes | `notes: dict = {}` — lost on restart | SQLite table — permanent |
| Sessions | `sessions: dict = {}` — lost on restart | SQLite table — permanent |

### Git Workflow Used
```bash
git checkout -b feature/sqlite-database   # create branch
# ... write code ...
git add .
git commit -m "feat: replace in-memory storage with SQLite"
git checkout main
git merge feature/sqlite-database
git push origin main
```

---

## Phase 6 — RAG with ChromaDB

### What We Built
Semantic document search — instead of reading entire files, Claude now finds only the relevant chunks.

### Key Concepts Learned
- **RAG** (Retrieval Augmented Generation) = chunk → embed → store → search → answer
- **Embedding** = converting text into a vector (list of numbers) that captures meaning
- Similar sentences produce similar vectors — this is how semantic search works
- **Chunking** = splitting large documents into smaller pieces (~500 chars) with overlap
- **ChromaDB** = vector database that stores embeddings and finds the closest ones to a query
- **sentence-transformers** = local ML model (`all-MiniLM-L6-v2`, ~80MB) that creates embeddings
- **Relevance score** — distance from 0 (identical) to 1+ (very different); lower = more relevant
- Windows SSL issue with `httpx` — fixed by monkey-patching `httpx.Client.__init__` and `httpx.AsyncClient.__init__` in `rag.py`
- `SSLKEYLOGFILE` env var set by network monitoring drivers (e.g. `nllMonFltProxy`) crashes Python SSL — fixed by popping it before `AsyncAnthropic()` and passing `httpx.AsyncClient(verify=False)` explicitly

### RAG vs Old Approach
```
Old:  Question → read entire file → Claude (expensive, 8000 char limit)
RAG:  Question → embed → ChromaDB → top 4 chunks → Claude (fast, scalable)
```

### Tools Added
| Tool | Description |
|---|---|
| `index_docs` | Chunks all docs, embeds them, stores in ChromaDB |
| `search_docs` | Semantic search — finds most relevant chunks for any query |

### How Chunking Works
```
Large document (10,000 chars)
  ↓ split into ~500 char chunks with 100 char overlap
[chunk 1][chunk 2][chunk 3]...[chunk 20]
  ↓ each chunk embedded into a vector
  ↓ stored in ChromaDB with metadata {source, chunk_index}

User asks: "What is my H1B validity?"
  ↓ question embedded into a vector
  ↓ ChromaDB finds 4 closest vectors
  ↓ returns those 4 chunks to Claude
  ↓ Claude answers from just those chunks
```

### Commands
```bash
pip install chromadb sentence-transformers
# In the chat: "Index my documents"
# Then ask any question about your docs
```

---

## Phase 7 — Git & GitHub

### What We Learned
- **Git** tracks changes locally; **GitHub** stores code online
- `git init` — start tracking a folder
- `git add .` — stage all changes
- `git commit -m "message"` — save a snapshot with a label
- `git push` — upload to GitHub
- `git pull` — download from GitHub
- **Branches** — parallel versions of code so main always stays working
- **Feature branches** — create for each new feature, merge when done
- **Pull Requests** — GitHub's way to review before merging

### Workflow Used Every Time
```bash
git checkout -b feature/name    # create branch
# ... write code ...
git add .
git commit -m "feat: description"
git push -u origin feature/name
# (optionally: open PR on GitHub)
git checkout main
git merge feature/name
git push origin main
```

### Commit History
```
701e66f  feat: add model routing — Haiku for simple queries, Sonnet for complex
a78d36a  fix: harden session history, usage tracking, and UI token display
932c9f4  feat: reduce token usage and fix Windows SSL issues
28b7a69  feat: add RAG with ChromaDB for semantic document search
f45961b  feat: prioritise docs + inspect_db utility
798a14c  feat: replace in-memory storage with SQLite database
d9346db  Initial commit - MCP learning project
```

---

## Phase 8 — Token Optimisation

### What We Built
Two techniques to reduce the number of tokens sent to Claude on every request:
prompt caching via `cache_control` and a sliding history window.

### Key Concepts Learned
- **Prompt caching** — Anthropic can cache a fixed prefix of your input across API calls.
  Marking the system prompt with `cache_control: {"type": "ephemeral"}` means the prompt
  tokens are only billed once every ~5 minutes instead of on every turn
- **Cache read vs cache write** — The first call in a 5-minute window *writes* the cache
  (billed at 1.25× normal rate). Subsequent calls *read* from it (billed at 0.1× normal rate).
  That saves ~90% of system-prompt tokens after the first message
- **History window** — Keeping the full conversation in SQLite but only sending the last
  N messages to Claude caps the context size so costs don't grow unboundedly
- **`INSERT OR REPLACE`** — upsert pattern lets us overwrite the session row on every save
  without checking whether it already exists

### Changes Made
```python
# api.py — system prompt with cache_control
SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": "You are a helpful assistant...",
        "cache_control": {"type": "ephemeral"},   # Anthropic caches this prefix
    }
]

HISTORY_LIMIT = 10  # only last 10 messages sent to Claude; full history stays in SQLite
```

### Before vs After
| | Before | After |
|---|---|---|
| System prompt tokens | Billed every turn | Billed once per 5-min window |
| History sent to Claude | Full conversation | Last 10 messages |
| Context cost growth | Unbounded | Capped |

---

## Phase 9 — Model Routing

### What We Built
A routing function that sends simple queries to Claude Haiku (faster, cheaper)
and complex or document-related queries to Claude Sonnet (smarter, more capable).

### Key Concepts Learned
- **Not all queries need the same model** — "What time is it?" costs the same whether
  you use Haiku or Sonnet, but Haiku is 10–20× cheaper for simple questions
- **Signal-based routing** — Rather than asking Claude to classify itself, route on
  simple heuristics: message length and keyword presence
- **Keyword signals** — Words like "doc", "search", "summarize", "analyze", "file",
  "project" reliably indicate the user wants Claude to reason over documents
- **Length heuristic** — Messages over ~120 characters are almost always substantive
  questions that benefit from the stronger model
- The chosen model is passed back to the browser in the `done` SSE event so you can
  see which model answered each question

### Code Added
```python
# api.py
_COMPLEX_SIGNALS = {
    "doc", "file", "note", "search", "find", "summarize", "summary",
    "read", "index", "analyze", "analysis", "report", "content", "folder",
}

def _pick_model(message: str) -> str:
    msg = message.lower()
    if len(message) > 120:
        return "claude-sonnet-4-6"
    if any(signal in msg for signal in _COMPLEX_SIGNALS):
        return "claude-sonnet-4-6"
    return "claude-haiku-4-5"
```

### Routing Logic
```
Message arrives
  ↓
len > 120 chars?  →  Sonnet
  ↓
any keyword match?  →  Sonnet
  ↓
else  →  Haiku
```

---

## Phase 10 — Usage Tracking & Session Hardening

### What We Built
End-to-end token usage visibility in the chat UI, plus two fixes that prevented
history corruption in edge cases.

### Key Concepts Learned
- **Multi-turn accumulation** — `tool_runner` makes multiple API calls (one per tool
  round-trip). Each call has its own `usage` object. You must sum across all of them
  to get the true cost of a single user message
- **Token breakdown** — The usage object has four fields:
  - `input_tokens` — regular input tokens billed this turn
  - `cache_creation_input_tokens` — tokens written to prompt cache (1.25× rate)
  - `cache_read_input_tokens` — tokens read from prompt cache (0.1× rate)
  - `output_tokens` — tokens Claude generated
- **Orphaned tool results** — When the history window is trimmed, the first message in
  the window may be a `tool_result` with no matching `tool_use` — this causes an API
  error. The `_safe_window()` function drops leading orphaned tool results before
  sending history to Claude
- **Empty assistant turns** — If an error occurs mid-stream and Claude produces no text,
  saving an empty assistant turn corrupts history. Guard with `if response_text:` before
  appending to history

### Code Added
```python
# api.py — accumulate usage across all tool_runner turns
total_input = total_cache_write = total_cache_read = total_output = 0
async for msg in runner:
    if hasattr(msg, "usage") and msg.usage:
        u = msg.usage
        total_input       += u.input_tokens
        total_cache_write += getattr(u, "cache_creation_input_tokens", 0)
        total_cache_read  += getattr(u, "cache_read_input_tokens", 0)
        total_output      += u.output_tokens

# Sent in the `done` SSE event so the browser can display it
done_data["usage"] = {
    "input": total_input,
    "cache_write": total_cache_write,
    "cache_read": total_cache_read,
    "output": total_output,
}

# Guard: never save an empty assistant turn
if response_text:
    history.append({"role": "assistant", "content": response_text})
    session_save(session_id, history)
```

```python
# _safe_window: drop orphaned tool_result turns at the start of the history slice
def _safe_window(hist, limit):
    window = hist[-limit:]
    while window and window[0].get("role") == "user":
        content = window[0].get("content", "")
        if isinstance(content, list) and content and \
                isinstance(content[0], dict) and content[0].get("type") == "tool_result":
            window = window[1:]
        else:
            break
    return window
```

### SSE Event Updated
```json
// done event now includes model and token breakdown
{ "type": "done", "session_id": "...", "model": "claude-haiku-4-5",
  "usage": { "input": 312, "cache_write": 0, "cache_read": 890, "output": 47 } }
```

---

## Phase 11 — Configuration, Sampling & Scale Thinking

### What We Built
- Switched API key management from Windows environment variable to `.env` file using `python-dotenv`
- Added `temperature=0.3` sampling parameter to both `/chat` and `/stream` endpoints

### Key Concepts Learned

**Environment variable management**
- Windows user env vars are machine-wide and persist across reboots — fine for personal use but not portable
- `.env` + `python-dotenv` is the industry standard for Python projects — project-scoped, portable, git-ignored
- `load_dotenv()` must be called explicitly in each entry point before any `os.getenv()` calls
- `.env` does not overwrite already-set env vars by default — safe to migrate gradually

**Sampling parameters**
- `temperature` controls randomness: 0 = deterministic, 1.0 = default (creative), lower = more consistent
- For tool-using assistants, `temperature=0.3` is the right choice — focused and predictable
- `top_p` and `top_k` are redundant when temperature is set — Anthropic recommends only tuning one
- MCP sampling (server-initiated Claude calls) is a separate concept — not needed for single-agent apps

**Database scale decisions**
- SQLite — single user, local, zero setup, built into Python. Right for this project
- PostgreSQL — multi-user, concurrent, ACID-compliant. Right for production
- Redis — in-memory cache on top of PostgreSQL for high-traffic apps (10,000+ concurrent users)
- The architecture pattern stays the same (`session_get`, `session_save`) — only the storage layer swaps

**Why persistent conversation history matters**
- Without it, every message is a fresh conversation — Claude has no memory of prior turns
- With SQLite, history is loaded and sent to Claude with each request, enabling true multi-turn dialogue
- `HISTORY_LIMIT = 10` caps what's sent to Claude (controls cost) while SQLite stores everything (continuity)
- This is the same pattern used in enterprise apps — just swap SQLite for PostgreSQL + Redis at scale

**Industry standard Claude Code extensions (surveyed)**
- MCP servers: GitHub, Playwright, Sentry, Linear, Notion, Slack, Figma
- Hooks: PreToolUse, PostToolUse, SessionStart, PermissionRequest — automate lifecycle actions
- Skills: bundled (`/code-review`, `/verify`, `/simplify`) + custom project-specific commands
- Typical starter stack: GitHub MCP + Playwright + VS Code extension + hooks + 1-2 custom skills

### Changes Made
```python
# agent.py and api.py — load .env file at startup
from dotenv import load_dotenv
load_dotenv()

# api.py — both /chat and /stream endpoints
runner = app.state.client.beta.messages.tool_runner(
    model=model,
    max_tokens=1024,
    temperature=0.3,   # added — consistent, focused responses
    system=SYSTEM_PROMPT,
    tools=app.state.tools,
    messages=...,
)
```

### Before vs After
| | Before | After |
|---|---|---|
| API key storage | Windows user env var (machine-wide) | `.env` file (project-scoped, portable) |
| Temperature | 1.0 (Anthropic default) | 0.3 (consistent for tool-using assistant) |
| Scale knowledge | Knew SQLite | Understands SQLite → PostgreSQL → Redis progression |

---

## Phase 12 — Eval Pipeline

### What We Built
A complete prompt evaluation pipeline — `evals/dataset.json` (12 test cases) and `evals/run_evals.py` (runner script) that tests whether Claude follows system prompt rules and model routing logic.

### Key Concepts Learned

**What evals test vs what unit tests test**
- Unit tests catch bugs in *your code* (does `_pick_model()` return the right string?)
- Evals catch failures in *Claude's behaviour* (does Claude actually use Haiku for simple queries?)
- Both are necessary — they test different failure modes

**Eval-driven development loop**
- Write test cases with expected behaviour
- Run evals → see failures
- Diagnose: is it a bug in code, a wrong expectation, or a prompt issue?
- Fix the right thing → rerun → repeat
- This is how enterprise teams maintain LLM behaviour after every change

**Dataset quality matters**
- Wrong test expectations are as harmful as wrong code
- "What documents do I have?" correctly calls `list_docs`, not `search_docs`
- "Square root of 144" — Claude answers directly without `calculate` tool (correct)
- Evals revealed these misunderstandings and forced clearer thinking about tool boundaries

**Real bugs found by evals**
- `/chat` endpoint was not returning `model` in the response — discovered by evals, not manual testing
- System prompt was not explicit enough about when to use `search_docs` vs `list_docs`
- Both were fixed because evals gave objective pass/fail evidence

**Cost awareness**
- Each eval case makes a real Claude API call — 12 cases = 12 API calls
- In CI/CD, evals run on every push — cost must be considered when sizing the dataset
- Use mock responses for fast/cheap unit tests; save real API calls for evals that test behaviour

### Files Created
- `evals/dataset.json` — 12 test cases covering tool selection and model routing
- `evals/run_evals.py` — runner that calls `/chat`, scores results, reports pass/fail

### Eval Run Results
```
Score: 12/12 (100%) — All evals passed!
Average latency: 6368ms per request

Cases covered:
  doc questions    → search_docs called (Sonnet)
  file listing     → list_docs called
  math/greetings   → no doc tool (Haiku)
  notes            → manage_notes called
  weather          → get_weather called (Haiku)
  long messages    → Sonnet model selected
```

### How to Run
```powershell
# Start the app first
python -m uvicorn api:app --port 8000

# Run evals (WARNING: consumes API credits — 1 credit per test case)
python evals/run_evals.py
```

---

## Phase 13 — AI Cost Dashboard & Token Economics

### What We Built
A full observability layer for LLM API spend — token tracking, cost estimation, credit management, tool cost breakdown, and a live alert badge in the chat UI.

### Key Concepts Learned

**Token economics — how Claude billing actually works**
- Every API call returns 4 token counts, each priced differently:
  - `input_tokens` — fresh tokens sent this turn (history + message) → full input price
  - `cache_write_tokens` — system prompt saved to Anthropic's cache → slightly above input price (one-time)
  - `cache_read_tokens` — system prompt served from cache → ~10× cheaper than input
  - `output_tokens` — what Claude wrote back → most expensive per token (3–5× input price)
- Input tokens will always exceed output tokens in a chat assistant — you send history + message, Claude sends just the answer
- Output costs more per token even though there are fewer of them — long Claude responses are expensive
- Cache read is nearly free — 37× cheaper than input on Sonnet. Longer sessions = more savings

**Why output is the most expensive token type**
```
Sonnet pricing per 1K tokens:
  Output:     $0.015  ← most expensive
  Input:      $0.003
  Cache Write: $0.00375
  Cache Read: $0.0003 ← nearly free
```

**Prompt caching in practice**
```
Message 1:  system prompt WRITE (one-time cost) + fresh input
Message 2+: system prompt READ  (near-free)     + fresh input
```
Cache hit rate = `cache_read / (input + cache_read)`. Above 60% means caching is working well.

**Client-side cost estimation**
- Cost estimated from token counts × pricing table in `database.py` — no extra API call
- `_estimate_cost(model, input, cache_write, cache_read, output)` runs after every response
- Result stored in `usage_logs.estimated_cost_usd` — accumulated across all sessions

**SQLite schema migration**
- `ALTER TABLE ... ADD COLUMN` with try/except — safe way to add columns to existing databases without data loss
- Used for `tools_used TEXT DEFAULT '[]'` column added to `usage_logs`

**SQLite `json_each()` for array aggregation**
- Tools stored as JSON array per row: `["search_docs", "manage_notes"]`
- `json_each()` unpacks arrays into rows so you can GROUP BY individual tool names
- No Python-side parsing needed — the database handles it
```sql
SELECT json_each.value AS tool_name, COUNT(*) AS calls
FROM usage_logs, json_each(usage_logs.tools_used)
GROUP BY json_each.value
```

**SVG charts in pure HTML**
- Replaced div-based bars with an SVG chart rendered entirely in JavaScript
- Advantages: precise text positioning, Y-axis labels, grid lines, hover tooltips, dot+line overlay
- `getBoundingClientRect().width` for responsive width; `viewBox` for scaling
- No chart library needed — just SVG primitives (`rect`, `text`, `line`, `polyline`, `circle`)

### What Was Built

**SQLite tables added:**
- `usage_logs` — token counts, model, cost, tools_used (JSON array) per request
- `credit_config` — singleton row (id=1) storing starting balance and alert threshold

**API endpoints added:**
| Endpoint | Purpose |
|---|---|
| `GET /usage` | Visual HTML dashboard |
| `GET /usage/data` | JSON: totals, by_model, by_day, by_session, by_tool, credit |
| `POST /usage/credit` | Save starting balance and alert threshold |

**Dashboard features:**
- 6 summary cards — requests, cost, cache savings, cache hit rate, input tokens, output tokens
- Token breakdown bar chart — Input / Cache Write / Cache Read / Output with colour coding
- Haiku vs Sonnet donut chart with cost split
- Daily SVG bar chart — Y-axis scale, dollar labels, grid lines, dots, trend line, intensity shading
- Per-session cost table — top 10 sessions ranked by spend
- **Cost by Tool** table — calls, total cost, avg cost/call, frequency bar per MCP tool
- **Claude API Credit Tracker** — starting balance, progress bar, burn rate ($/day), days remaining
- **Cost Forecast** — 30/60/90 day projected spend based on burn rate; pure frontend math (`burnPerDay × days`), no backend or schema changes
- Low-credit alert badge in chat header — pulses red when remaining < threshold

### Key Code Patterns
```python
# database.py — cost estimation
_PRICING = {
    "claude-haiku-4-5":  { "input": 0.0008, "cache_read": 0.00008, "output": 0.004 },
    "claude-sonnet-4-6": { "input": 0.003,  "cache_read": 0.0003,  "output": 0.015 },
}

# database.py — tool aggregation via json_each
SELECT json_each.value AS tool_name, COUNT(*) AS calls, SUM(estimated_cost_usd) AS cost_usd
FROM usage_logs, json_each(usage_logs.tools_used)
GROUP BY json_each.value ORDER BY calls DESC

# api.py — capture tools called during stream
tools_called: list[str] = []
for block in msg.content:
    if block.type == "tool_use":
        tools_called.append(block.name)

usage_log(session_id, model, ..., tools=tools_called)
```

### Before vs After
| | Before | After |
|---|---|---|
| Token visibility | None | 4-way breakdown per message in chat UI |
| Cost tracking | None | Estimated to 4 decimal places per request |
| Tool insight | None | Calls + cost + avg cost per MCP tool |
| Credit management | None | Balance tracker, burn rate, days remaining, alert |
| Daily chart | None | SVG chart with Y-axis, labels, trend line |
| Multi-project | None | project column + filter dropdown + Cost by Project table |

### Multi-Project Support (Option C — shared DB)

Added `project` column to `usage_logs` so multiple projects can report to the same dashboard.

**Architecture decision — 3 options considered:**
- **Option A** — centralised HTTP endpoint (enterprise, requires deployment)
- **Option B** — shared Python package (each project has its own dashboard)
- **Option C** — shared SQLite file, project column tag ← built this (simplest, works locally)

Option C grows into Option A naturally: deploy the dashboard to GCP Cloud Run → expose `POST /usage/log` → any project anywhere can report over HTTP.

**To wire up a second project:**
```python
# In any new project — just change the project name
usage_log(session_id, model, ..., project="my-new-project")
# Point DB_PATH to the same data.db file
```

**Key pattern learned — multi-tenancy at the data layer:**
One database, multiple tenants isolated by a tag column. Same pattern used by Salesforce (`org_id`), Stripe (`account_id`), and every enterprise SaaS product.

---

## Phase 14 — Playwright MCP & Security-First Tooling

### What We Built
Added Playwright MCP as a project-scoped MCP server so Claude Code can drive the running app in a real browser — navigate, click, type, screenshot — instead of only reading source code. Used it immediately to test the chat UI and cost dashboard end to end, which surfaced a real bug.

### Key Concepts Learned

**Evaluating a new MCP server before installing it**
- Check the publisher first — `@playwright/mcp` is published by Microsoft under the official Playwright org, not a random third party
- Understand the access boundary — it only grants browser automation, no filesystem or shell access to the host machine
- Identify where the actual risk lives — prompt injection from *untrusted external content* (a malicious webpage's text instructing the agent). Testing against `localhost` (content you wrote yourself) sidesteps that risk entirely
- Supply chain risk (`npx -y` pulling from npm at run time) is the same category as any npm install — mitigated by using a well-known, widely-adopted package

**Project scope vs user scope for MCP servers**
- `claude mcp add <name> --scope project -- <command>` writes to `.mcp.json` in the repo root — shared with anyone who clones the project
- No secrets belong in `.mcp.json` — verified before committing
- Personal-only servers belong in user/global scope instead

**A real bug Playwright testing caught immediately**
- First live test of the chat UI returned: `"Could not resolve authentication method"` — even though `.env` had a correct API key
- Root cause: `.env` was saved as **UTF-8 with BOM** (byte-order-mark), a common default when Windows tools (Notepad, some PowerShell commands) save text files
- The BOM character silently merges with the first line, turning `ANTHROPIC_API_KEY` into an unrecognized variable name — `python-dotenv` never sees it, and the SDK falls back to no credentials with a generic auth error
- Diagnosed *without ever printing the actual key* — used `grep -c "^ANTHROPIC_API_KEY="` (a structural check, zero secret exposure) to prove the line didn't match, then confirmed the BOM was the cause
- Fixed by rewriting the file as plain UTF-8 (no BOM) via `[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $false))`
- `uvicorn --reload` does **not** watch `.env` for changes — fixing the file requires a full process restart, not just a reload

**Security discipline applied to new tooling, not just app code**
- After adding Playwright MCP, checked `git status` and found a new untracked `.playwright-mcp/` directory containing screenshots and page snapshots — not yet covered by `.gitignore`
- This is a real, general pattern: **every new tool integration can create new artifacts that need a `.gitignore` entry** — it's not enough to secure the app; the tooling around it needs the same discipline
- Fixed by adding `.playwright-mcp/` and the specific test screenshot filename to `.gitignore` (deliberately *not* a blanket `*.png`, since that would silently block a legitimate future README screenshot)

**Diagnosing secrets without exposing them**
- Never `cat` or `Read` a file suspected of containing a secret to "see what's wrong" — use structural checks instead (`grep -c`, line-count, redacted `sed` substitution) that prove or disprove a hypothesis without the secret ever appearing in a transcript or log

### Before vs After
| | Before | After |
|---|---|---|
| UI verification | Read code, trust it | Drive it in a real browser via Playwright MCP |
| `.env` encoding | Unverified — silent BOM bug live for some time | Verified plain UTF-8, documented as a standard in README |
| New-tool security check | Not a formal step | Standing rule: after any new file/tool/dependency, check for untracked artifacts and gitignore gaps before considering the task done |
| Secret diagnosis | N/A | Structural checks only (grep -c, redacted sed) — secret value never printed |

---

## Phase 15 — Prompt Engineering Fundamentals Applied to `SYSTEM_PROMPT`

### What We Built
Rewrote `api.py`'s `SYSTEM_PROMPT` using three Anthropic-documented prompt engineering techniques — role prompting, XML tag structuring, and few-shot examples — then ran the eval suite to measure the real effect, per the Learning Plan's success check. Also fixed a bug the eval run itself exposed.

### Key Concepts Learned

**Role prompting** — a scoped persona ("You are a document-retrieval assistant...") biases borderline decisions in a consistent direction, unlike a generic "helpful assistant" role which gives Claude no default lean when a question is ambiguous. Critical caveat discovered: a role must not *contradict* an explicit rule elsewhere in the prompt (e.g. a "refuses to answer anything not in the docs" persona directly fighting a "fall back to general knowledge" rule) — a role is a bias, not an override, and conflicting instructions produce unpredictable behavior rather than a clean resolution.

**XML tag structuring** — Claude was trained to treat tags like `<role>`, `<tool_routing_rules>`, `<examples>` as reliable structural boundaries. The tag *name* itself is content Claude reads before parsing what's inside — `<tool_routing_rules>` vs `<section1>` primes interpretation and gives Claude a category to reason about precedence with, the same way a well-named function primes a human reader before they see the body.

**Few-shot prompting — and its real failure mode.** Added 5 input→action example pairs to `SYSTEM_PROMPT`. First iteration caused a **measured regression**: eval score dropped from 12/12 to 10/12. Root cause: the `list_docs` example ("What documents do I have?") shared surface-level wording ("documents", "all... in my system") with a `search_docs` test case ("summarize all the documents in my system"), and Claude pattern-matched on the lexical overlap instead of the intended semantic distinction (enumerate filenames vs. synthesize content). **Generalizable lesson: few-shot examples anchor on surface features present in the example text, not necessarily the deeper rule intended — the closer an example's wording sits to a real case, the more it can pull that case toward the wrong answer.** Fixed by rewording the `list_docs` example to unambiguous "enumerate filenames" language and adding an explicit example matching the exact failing pattern.

**A latent bug the eval regression exposed** — `evals/run_evals.py`'s printer used `result.get("tool_pass", True)` to render pass/fail icons. On an exception (timeout, connection error), `run_case` returns a dict with no `tool_pass`/`model_pass` keys at all — so the default silently rendered `OK OK` icons even though the case genuinely failed, hiding the real cause. **Generalizable lesson: a test/eval harness that defaults missing fields to "pass" hides its own failure mode — the same class of bug as a monitor that only greps for a success marker and stays silent on a crash.** Fixed by detecting the `error` key explicitly and printing the actual exception message instead of defaulting the icons.

**Message Batches API is not a fit for interactive eval loops** — Batches offer a real 50% token discount, but (1) latency is "usually within an hour, up to 24 hours" — incompatible with an iterate-and-measure workflow, and (2) they don't support the interactive tool-call loop `tool_runner` provides (call tool → execute → continue) within one submission; continuing a tool-using conversation via batches means a second full batch submission and another multi-hour wait. Batching is the right lever for high-volume, non-interactive, single-turn workloads — not for a 12-case suite you re-run while tuning a prompt. Prompt caching and model routing (both already in this project) are the correct cost levers for this shape of workload.

### Before vs After
| | Before | After |
|---|---|---|
| `SYSTEM_PROMPT` structure | One undifferentiated prose block | `<role>` / `<tool_routing_rules>` / `<examples>` tagged sections |
| Few-shot examples | None | 5 input→action pairs, tuned to avoid lexical-overlap misrouting |
| Eval score | 12/12 (no few-shot) | 10/12 → regression diagnosed → fix applied (re-verification pending, deferred to save API credits) |
| Eval harness failure reporting | Timeouts silently rendered as "OK OK" | Exceptions print the real error message |

---

## Phase 16 — Non-Destructive Credit Reset & the Cost of Testing Destructive Actions

### What We Built
Added a "reset spend tracking" option to the cost dashboard's credit banner, so a real Anthropic balance top-up doesn't get blended with lifetime spend when computing remaining balance, burn rate, and forecasts. Also re-ran the eval suite to try to verify the Phase 15 prompt fix, which surfaced a genuinely new finding instead of a confirmation.

### Key Concepts Learned

**Filter, don't delete, when "resetting" a metric.** The naive fix would have been to zero out or archive `usage_logs`. Instead, `credit_config` got a `period_start` column: `credit_status()` sums spend/active-days only `WHERE created_at >= period_start` (falling back to all-time when never reset, so existing installs are unaffected). Every historical chart (`by_day`, `by_model`, `by_session`, `by_project`) keeps querying the full table regardless. **Generalizable principle: when a metric needs to "start over," add a timestamp filter to the read path — never delete or mutate the underlying event log.** The log is the source of truth; the metric is a view over it.

**A single-slot cache of "the last thing" is a real hazard, proven by causing it.** The first version stored one `prev_period_*` snapshot with no protection. While testing the feature, a retried tool call fired `saveCredit()` twice in ~44 seconds — the second reset silently overwrote the first (real, useful) snapshot with an empty one. **Generalizable principle: any time a design holds "the most recent X" in a single slot instead of a list, a second write before you've consumed the first will destroy data with no warning.** The fix — a `confirm()` dialog before any reset, naming exactly what gets overwritten — doesn't solve the single-slot limitation, but it stops the silent, accidental case. (A more complete fix would be a list of archived periods instead of one slot — noted as a possible future improvement, not built.)

**Testing a "destructive-to-metadata" UI action with a confirm dialog needs the dialog-handling API, not an inline `page.on('dialog')` listener.** Registering a listener inside the same `evaluate`-style code block as the triggering click raced against Playwright MCP's own dialog watcher — the confirm sometimes appeared to be "already handled" with unclear state. Switching to the dedicated dialog tool (accept/dismiss as a separate, explicit step) resolved it. **Generalizable principle: browser automation tools that expose a first-class API for a browser feature (dialogs, downloads, permissions) should be driven through that API, not replicated via a generic script-injection escape hatch — the two can conflict over who owns the event.**

**Re-running an eval to confirm a fix can surface a *different* problem than the one you were checking.** The eval re-run (to confirm the Phase 15 few-shot fix) instead hit the 30-second client timeout on the two previously-failing cases — meaning the fix's actual effect on tool routing is still unverified, but the *eval harness's* honest-error-reporting fix from Phase 15 proved itself immediately, correctly showing `ERROR: timed out` instead of a false pass. The likely cause: cold-start latency on the first `search_docs` call after each server reload (the sentence-transformers embedding model reloads from disk), not the prompt content itself. **Generalizable principle: don't assume a re-run that "still fails" is the same failure as before — re-read the actual error, because the fix you're testing can succeed while an unrelated adjacent problem (here, a timeout budget that was already too tight for a Sonnet + RAG round-trip) is what shows up instead.**

**A correct calculation with a misleading label is still a bug.** "Days Left" computed exactly what it was supposed to (`remaining ÷ burn rate`) — the math was never wrong. But the *label* implied something false: that API credits expire on a day count, which they don't. Anthropic credits don't have a calendar-based cutoff; the number is a runway forecast, not a limit. **Generalizable principle: a metric's name is part of its correctness.** A perfectly accurate number attached to a name that implies the wrong kind of guarantee is a UX bug, not a nitpick — fixed here by renaming to "Est. Runway," formatting the value as `~Nd` instead of a bare integer, and adding a tooltip on both the label and the value stating explicitly that it's a forecast, not an expiration.

### Before vs After
| | Before | After |
|---|---|---|
| Balance top-up tracking | `remaining = starting_balance − lifetime spend` (blends old + new) | `remaining = starting_balance − spend since last reset` (period-scoped, opt-in) |
| Reset safety | N/A | Confirm dialog naming exactly what gets overwritten, before any reset |
| Previous-period visibility | N/A | Single archived snapshot (cost, days, end date) shown in the banner |
| Burn rate right after a reset | N/A | Falls back to previous period's rate, marked `(est.)`, until new data lands |
| Eval verification of Phase 15 fix | N/A | Inconclusive — surfaced a timeout issue instead; genuine re-verification still pending |
| "Days Left" label | Bare integer, implied a hard expiration | "Est. Runway", `~Nd` format, tooltip on label + value clarifying it's a forecast |

---

## Phase 17 — Prompt Injection Defense, Cosine Similarity, and an API-Drift Catch

### What We Built
Closed out the remaining Prompt Engineering Fundamentals items: added an indirect-prompt-injection defense and input sanitization to `api.py`, verified (rather than assumed) how `search_docs` actually ranks results, mapped context engineering onto real code, and caught that the learning plan's own "response prefilling" item described a technique that no longer works on this project's models.

### Key Concepts Learned

**Indirect prompt injection is the real risk in a RAG pipeline, not direct injection.** A user typing "ignore your instructions" only hijacks their own chat. The dangerous case is a `docs/` file containing text that *looks* like an instruction — since `search_docs`/`read_doc` results flow back into Claude's context as `tool_result` blocks, indistinguishable from a real instruction unless told otherwise. Added a `<security>` tag to `SYSTEM_PROMPT` stating tool results are data, not commands — verified via eval run (11/12, the one miss a timeout on an already-slow case, not a routing regression) that this didn't change tool-selection behavior.

**Sanitization is the cheap layer, not the real defense.** `_sanitize_input()` (strip non-printable chars, cap at 4000 chars) stops noise and context-window abuse, but doesn't address indirect injection at all — that's the system-prompt tag's job. Conflating the two would have meant shipping only the weak half.

**Verify a "why does this work" claim against the actual installed library, not the docstring's assertion.** `rag.py`'s docstring says distance `< 0.8` is "relevant" without stating *which* distance metric. Checked the installed `chromadb` (v1.5.9) source directly: `SentenceTransformerEmbeddingFunction.default_space()` returns `"cosine"`, confirming `rag.py`'s `score = round(1 - distance, 3)` is literally the cosine-similarity formula, not an arbitrary scoring convention. Then demoed it live with the project's own embedding model: two paraphrased sentences sharing zero words scored 0.556, versus 0.09–0.065 for unrelated pairs — proof the ranking is genuinely meaning-based, not keyword overlap dressed up as semantic search.

**Context engineering is a synthesis label for decisions this project already made, not a new technique to bolt on.** `SYSTEM_PROMPT`, `HISTORY_LIMIT`, `search_docs`'s chunk size, `read_doc`'s 8000-char cap, and `_safe_window()`'s tool_use/tool_result pairing are all context-window budget decisions. Recognizing them as one discipline (not five unrelated caps) is the actual learning outcome — there was no code left to write for this item.

**A skill's own API-drift warning caught a stale plan item before it caused a runtime error.** The learning plan described response prefilling (seeding an assistant turn with `{` to force JSON) as a prerequisite for Phase 5. Checking current Anthropic docs: assistant-turn prefill returns a hard `400` on the entire current model generation (Opus 4.6+, Sonnet 4.6+, Fable 5) — and `claude-sonnet-4-6`, one of this project's own two routed models, is on that blocked list. Confirmed live via `client.models.retrieve()` (a free metadata call, no completion cost) that both routed models (`claude-sonnet-4-6`, `claude-haiku-4-5`) support `structured_outputs` instead — the correct current replacement, and a better fit for Phase 5's planned `{title, content, tags}` note-extraction than prefilling would have been anyway. **Generalizable principle: for a fast-moving API, a documented "next step" in a personal learning plan can go stale between when it was written and when you act on it — check the current API surface before building on a remembered technique, especially one a model's own training data might misremember as still current.**

### Before vs After
| | Before | After |
|---|---|---|
| Indirect prompt injection | Undefended — doc/note content could be read as instructions | `<security>` tag in `SYSTEM_PROMPT`; `search_docs`/`read_doc`/`list_docs`/`manage_notes` results explicitly marked as data |
| User input | Passed to history/model unmodified | `_sanitize_input()` strips control chars, caps at 4000 chars |
| Cosine-similarity claim in `rag.py` | Asserted in a comment, unverified | Confirmed against installed `chromadb` source + live demo with the project's own model |
| "Response prefilling" plan item | Described a technique that 400s on this project's own routed model | Corrected to `output_config.format` / `client.messages.parse()`, verified supported on both models via Models API |

---

## Phase 18 — Tool Use Fundamentals: The API Primitives Beneath `tool_runner`

### What We Built
Closed the "Tool Use Fundamentals" gap in `LEARNING_PLAN.md` — a category the plan's own "MCP (Model Context Protocol)" checkbox had silently masked. Built `tool_use_demo.py`, a standalone script using the raw Anthropic SDK (no MCP, no `tool_runner`) against this project's own `get_weather` and `manage_notes` tool schemas, to see the mechanics `tool_runner` normally hides.

### Key Concepts Learned

**A completed high-level checkbox can hide an unlearned primitive underneath it.** "MCP (Model Context Protocol) — server, tools, stdio transport" was checked off at the top of `LEARNING_PLAN.md` from Phase 1 onward, and that checkmark got treated as covering tool use in general. It didn't: building MCP tools and looping them through `tool_runner` never required touching `tool_choice`, `disable_parallel_tool_use`, or raw `input_json_delta` streaming — `tool_runner` abstracts all of it away. The gap only surfaced because it was asked about directly, not because anyone was auditing the "Completed" list for what a checkmark actually covers. **Generalizable principle: the same failure pattern applies to any completed checkbox that names a broad topic — check what's *underneath* the abstraction it references, not just whether the abstraction itself works.**

**Forcing a tool constrains the action, not the model's judgment about arguments.** Live test: an ambiguous prompt ("Tell me an interesting fact about deserts") answered directly under `tool_choice: {"type": "auto"}` — no tool called. The *identical* prompt under `tool_choice: {"type": "tool", "name": "get_weather"}` was forced into calling the tool, but Claude didn't refuse or error — it inferred a best-guess argument (`city: "Sahara"`) from context. The API-level guarantee is "a tool_use block for this tool will exist in the response," not "Claude will make sense of being forced."

**`disable_parallel_tool_use` is provably binary, not just documented behavior.** With two tools available and a prompt inviting both ("What's the weather in Tokyo, and also list my saved notes?"), `tool_choice: {"type": "any"}` produced two `tool_use` blocks in one response. Adding `disable_parallel_tool_use: True` to the same `tool_choice` collapsed it to exactly one. Confirmed by counting blocks, not by trusting the parameter's description.

**Streaming tool arguments arrive as unparseable fragments until the block closes — and `tool_runner` doesn't expose this at all.** Watched raw `input_json_delta` events accumulate: `''` → `'{"cit'` → `'{"city": "'` → `'{"city": "Seattle"}'` — only the last fragment is valid JSON. The Python `tool_runner` returns complete messages per iteration, not token-level deltas, so this layer is invisible unless you drop to a manual `client.messages.stream()` call, which is exactly why `api.py`'s `/stream` endpoint streams whole messages to the browser rather than live tool-argument deltas.

**A manual multi-turn loop is the same three steps every time, and skipping any one of them breaks it.** Built the `tool_use` → execute → `tool_result` → loop cycle from scratch against `manage_notes` (save a note, then read it back — 3 turns). The three things that bite on a first attempt: (1) the full `response.content` — including `tool_use` blocks — must be appended as the assistant turn before the `tool_result` follow-up, or Claude has no record of its own call; (2) multiple `tool_result` blocks from one parallel response must batch into a single `user` message, not split across several; (3) `tool_use_id` must match exactly. Verified the loop actually worked by checking `inspect_db.py` for the real SQLite write afterward — not by trusting the model's own summary of what it did.

**A stale documentation contradiction is easy to introduce and easy to miss.** After checking off the new Tool Use Fundamentals section in the detailed body of `LEARNING_PLAN.md`, the top-level summary list under "Not Yet Started" still carried the old unchecked line — caught only because it was pointed out directly, not by re-reading the file end-to-end after editing it. **Generalizable principle: a document with the same fact stated in two places (a detailed section and a rolled-up summary) needs both edited together, or it silently self-contradicts.**

### Before vs After
| | Before | After |
|---|---|---|
| Tool use knowledge | Used `tool_runner` successfully, never saw what it does internally | Can explain `tool_choice` modes, force a specific tool, toggle parallel calls, read raw streaming deltas, and rebuild the loop by hand |
| `LEARNING_PLAN.md` | "Tool Use Fundamentals" wasn't a tracked item at all | New section added, all 6 items demoed and checked off; top-level summary list corrected to match |
| Verification method | N/A | `tool_use_demo.py` — 6 real API calls, results checked against actual behavior (block counts, streamed fragments, a genuine SQLite row via `inspect_db.py`) instead of assumed from documentation |
| Portfolio | No coverage of tool-use internals | New §12 in `AI_ENGINEERING_PORTFOLIO.md` — framed as understanding the primitives every tool-calling framework (`tool_runner`, LangChain, LlamaIndex) wraps |

---

## Phase 19 — Anthropic-Native Tools: web_search and a Sandboxed Text Editor

### What We Built
Added the first two tools that **aren't** MCP tools: `web_search` (server-side, Anthropic-hosted) and `str_replace_based_edit_tool` (client-side, executed in-process). This forced a real distinction that Phases 1–18 never needed: not everything in a Claude `tools` array is an MCP tool, and the two non-MCP flavors — server-side and client-side — have different execution models, different response content-block types, and different failure modes.

### Key Concepts Learned

**Server-side and client-side "Anthropic-native" tools are architecturally distinct from MCP, and from each other.** `web_search` needed nothing but a plain dict declaration — Anthropic runs it entirely on their infrastructure, and the result comes back already resolved. The text editor tool needed real handler code (`text_editor_tool.py`, implementing the SDK's `BetaAsyncBuiltinFunctionTool` interface: `to_dict()` for the declaration, `call()` to execute it) because Claude only *requests* the edit — the client has to perform it. Declaring a client-side tool as a raw dict (the way that works for `web_search`) doesn't work: `tool_runner`'s `tools` parameter only executes objects implementing the runnable-tool protocol, so a client-side tool needs the class, not a dict.

**Server-side tool calls are a different content-block type, and generic tracking code silently drops them.** `tools_used.append(block.name)` only fired on `block.type == "tool_use"` — which covers MCP and client-side tools, but web_search (and the `code_execution` it runs under the hood for dynamic filtering) arrive as `server_tool_use` blocks instead. The bug was invisible in the chat UI (the tool call indicator showed correctly) and only surfaced by directly querying `/usage/data` and noticing `by_tool` had zero entries for `web_search` despite `total_web_searches` correctly showing 2. Fixed by handling `server_tool_use` alongside `tool_use` everywhere tool calls get counted.

**Declaring a tool can break a model that never intended to call it.** The real production bug this phase: `_pick_model()` can route *any* short/simple message to Haiku, and `web_search_20260209`'s default config requires programmatic tool calling, which Haiku doesn't support. The API validates every *declared* tool against the model's capabilities at request time — not just tools the model actually decides to use — so a completely unrelated message ("add a comment to api.py") 400'd purely because `web_search` was sitting in the tools array. The fix (`allowed_callers: ["direct"]`) was a one-line change, but finding it required noticing the error message named the *tool*, not the *user's message*, as the cause.

**A hard-coded single-file restriction is a legitimate security boundary, and it's cheap to verify.** Rather than confining the text editor tool to the whole `docs/` folder (the "obvious" boundary, matching `read_doc`'s existing pattern), it was scoped to exactly one file — `docs/project_notes.md` — because that was the only concrete use case (keeping a living doc in sync). Verified three ways before trusting it: a direct Python test (bypassing the API) confirming traversal (`../api.py`) and sibling files in the same folder both raise `ToolError`; then a real end-to-end browser test explicitly asking Claude to edit `api.py`, which was refused at the *prompt* level (Claude cited the restriction) before the hard filesystem check would even have needed to fire.

**A quantified trade-off beats a reflexive "more correct" fix.** The `allowed_callers: ["direct"]` fix disables dynamic filtering (server-side result pre-filtering that reduces tokens on noisy searches) even for Sonnet-routed requests that could support it. A model-aware fix — different tool config depending on which model `_pick_model()` selected — would recover that efficiency, but the actual token savings from dynamic filtering weren't quantifiable from available documentation, and the blanket fix was already tested and safe. Decision: keep the simpler, verified fix; revisit only if the cost dashboard later shows `web_search` turns burning noticeably more tokens than expected. Not every theoretically-more-correct fix is worth the added complexity.

### Before vs After
| | Before | After |
|---|---|---|
| Tool count | 8 (all MCP) | 10 — 8 MCP + 1 server-side (`web_search`) + 1 client-side (`str_replace_based_edit_tool`) |
| Tool execution models understood | 1 (MCP over stdio/JSON-RPC) | 3 (MCP, Anthropic server-side, local client-side via `BetaAsyncBuiltinFunctionTool`) |
| Cost dashboard `by_tool` | Silently dropped every server-side tool call | Correctly attributes `web_search`, `code_execution`, and `str_replace_based_edit_tool` |
| Cost tracking | Token costs only | Token costs + web_search's flat $10/1,000-searches fee, folded into `estimated_cost_usd` automatically |
| Model routing robustness | Untested against tool/model capability mismatches | Found and fixed a real 400 affecting every Haiku-routed request once `web_search` was added |
| File-mutation capability | None — all 8 original tools are read-only or SQLite-backed | Claude can edit exactly one real file (`docs/project_notes.md`), verified against traversal and sibling-file escape attempts |

---

## Phase 20 — Discord Mobile Alerts: Designing for a Server That Isn't Always Running

### What We Built
The cost dashboard's low-credit badge only helped if the browser tab was open. Added four Discord-webhook-based mobile alerts — two-tier low-balance (warning $5 / critical $1), a spend-spike alert (today vs. trailing 7-day average), a per-tool budget alert (`web_search`, $1/day), and a daily digest sent on the first request of each new day — so alerts reach a phone instead of requiring the dashboard to be open.

### Key Concepts Learned

**The "textbook" solution assumes guarantees your app doesn't actually have.** The obvious way to build "a daily digest sent every morning" is a background scheduler (APScheduler, cron) firing at a fixed wall-clock time. That's wrong for this app: `uvicorn --reload` only runs when manually started, so a scheduler firing at 8am would silently miss every day the server wasn't running at that exact moment — a failure mode invisible until you go looking for a digest that never arrived. The actual design question wasn't "how do I schedule this," it was "does my runtime environment even support scheduling." Once framed that way, the fix was simpler than the textbook answer: piggyback on real traffic — check on every request whether today's date differs from the last-sent date, and send yesterday's digest if so. No new dependency, no missed days as long as the app gets used at some point each day.

**A live-pasted secret needs handling decisions made *before* touching it, not after.** When a real Discord webhook URL landed directly in chat, the response wasn't "store it" — it was: never echo it back in any tool output, verify `.gitignore` covers `.env` structurally (`git check-ignore`) before writing to it, and use `grep -c` to confirm the write succeeded without ever printing the value. This is the same discipline as the project's documented `.env` BOM-check convention, applied to a fresh secret instead of an existing one — the habit generalizes, the specific secret doesn't.

**Multi-tier alerts need explicit handling for jumps between non-adjacent tiers, not just the tiers themselves.** Building a two-tier alert (warning → critical) and testing only "does warning fire" and "does critical fire" would have shipped a real bug: dropping straight from warning into critical (skipping past the warning zone in one big cost spike) left the *warning* tier's cooldown stale. Later, if balance partially recovered back into the warning band, the alert would have silently stayed suppressed — appearing to still be in a cooldown window from an alert sent before the situation got worse. Caught only by testing the actual transition sequence (warning → critical → partial recovery), not each tier in isolation. **Generalizable principle: whenever a system has more than two states with independent cooldowns/timers, test the *transitions* between every pair of states, not just each state reached directly from "normal."**

**Testing stateful, side-effecting features against production data requires capture-perturb-restore discipline, not a staging copy.** This project has no separate test database — every alert test ran against the real `credit_config` row and real `usage_logs`. The pattern used throughout: read and record the exact current values first, temporarily perturb only what's needed to force the condition (e.g., `starting_balance` to land `remaining` in a specific band), verify the effect via a direct query (not by trusting Discord delivery alone), then restore the exact original values and re-verify the restoration. Four alert types tested this way, zero corruption to real credit tracking.

### Before vs After
| | Before | After |
|---|---|---|
| Low-credit visibility | Passive badge, only visible with the dashboard tab open | Real-time Discord push to phone, two severity tiers |
| Alert types | 1 (low balance only) | 4 (low-balance ×2 tiers, spend spike, per-tool budget, daily digest) |
| Scheduled-feature design | Not yet attempted in this project | Learned to design around actual runtime guarantees (traffic-triggered) instead of defaulting to a background scheduler |
| Multi-tier alert correctness | N/A | Found and fixed a real cooldown bug via explicit transition testing (warning → critical → partial recovery), not just per-tier testing |
| Secret handling | `.env` conventions existed for the initial API key | Extended to a live-pasted secret mid-conversation — structural verification (`grep -c`, `git check-ignore`) instead of ever printing the value |

---

## Phase 21 — Security Tooling: Secret Scanning, Commit Signing, and Dependency Auditing

### What We Built
Three layers of dev-workflow security, added after a full OS-level security/performance pass on the machine itself: a `gitleaks` pre-commit hook (blocks any commit containing a likely secret, redacts the value in its own output, and was verified against the full 74-commit project history with zero findings); SSH-based commit signing (a dedicated signing key, configured globally via `gpg.format=ssh`, with the result verified independently through GitHub's own API rather than trusted on faith); and a `pip-audit` dependency scan (which required first fixing a corporate-network SSL interception issue via `pip_system_certs`, then found and fixed 5 real CVEs in `pip` itself, and surfaced one alarming-looking CVE in `chromadb` that turned out not to apply to this project at all).

### Key Concepts Learned

**A CVE's severity is about the vulnerable code path, not the package name — check whether your code ever reaches it.** `pip-audit` flagged `chromadb` for `PYSEC-2026-311`, described as an unauthenticated remote-code-execution vulnerability — the kind of finding that looks urgent on sight. But the vulnerable surface was specifically ChromaDB's standalone HTTP server API (`/api/v2/tenants/.../collections`), and a one-line grep of `rag.py` confirmed this project only ever uses `chromadb.PersistentClient` — an embedded, in-process client with no network listener at all. The fix wasn't a version bump; it was reading the advisory closely enough to know none was needed. **Generalizable principle: a dependency scanner tells you a vulnerability exists in a package you depend on — it does not tell you whether your specific usage exercises the vulnerable code path. That second check is on you, and skipping it means either false alarm fatigue (if you patch everything reflexively) or missed real risk (if you start ignoring the scanner because "it's always a false alarm").**

**A tool's own verification output can be wrong about success — trust the authoritative source, not the convenience check.** After signing the first commit, `git log --show-signature` reported `No signature`, which looked like the whole signing setup had silently failed. It hadn't: the raw commit object (`git cat-file -p HEAD`) showed a complete `gpgsig` block with a valid SSH signature — `git log`'s local verification simply requires an `allowedSignersFile` to be configured before it will *display* a verified status, a separate, optional feature we hadn't set up. The real answer came from asking GitHub's API directly (`gh api repos/.../commits/<sha> --jq '.commit.verification'`), which returned `"verified": true`. **Generalizable principle: when a verification step reports failure, check whether it's reporting on the thing you actually care about, or on a secondary convenience feature with its own separate prerequisites. The authoritative check is whichever system will actually consume the result in production (here: GitHub, not the local git CLI's optional display feature).**

**A permission system scoping consent to literal words, not implied intent, is a feature — not friction to route around.** Asked to "execute do now part" covering four listed items, one of which was generating a new SSH signing keypair, the key-generation step was blocked: the classifier's reasoning was that a "yes" to a five-item summary wasn't the same as explicit approval to create a new persistent credential, since the credential itself was never named in what was agreed to. The correct response wasn't to find a workaround — it was to surface the block, explain the side effect it had already caused (git now pointed at a signing key that didn't exist yet, so the *next* real commit would fail), and ask explicitly. Re-asked directly, the user approved it in one word. **Generalizable principle: when an agent's own guardrails stop an action mid-task, that's a signal to stop and hand the decision back, not an obstacle to engineer around — especially when the blocked action creates a new standing credential rather than just reading state or modifying a file.**

**Corporate SSL interception breaks Python's HTTPS tooling selectively, not uniformly — different libraries trust different certificate stores.** `pip install` worked fine throughout this entire project, but `pip-audit`'s own HTTPS calls to PyPI failed with `CERTIFICATE_VERIFY_FAILED`. The cause: `pip` and the `requests`/`urllib3` stack (which `pip-audit` uses internally) validate certificates against different trust stores — `requests` bundles its own CA list via `certifi`, which has no way to know about a corporate network's intercepting root CA even though Windows' own trust store does. The fix, `pip_system_certs`, patches Python's SSL layer to defer to the Windows certificate store instead of `certifi`'s bundled list — a five-minute install that resolved something that looked, at first, like a code or network-access problem. **Generalizable principle: "it works for tool A but fails identically-shaped tool B on the same network" is a strong signal the two tools don't share a trust-store implementation, not that the network is inconsistently broken.**

### Before vs After
| | Before | After |
|---|---|---|
| Secret leak prevention | Manual `.gitignore` discipline only, no enforcement at commit time | Automated `gitleaks` pre-commit hook + full 74-commit history verified clean |
| Commit provenance | Unsigned commits — no cryptographic proof of authorship | SSH-signed commits, independently verified via GitHub's API (`"verified": true`) |
| Dependency vulnerabilities | Unknown — never scanned | Scanned via `pip-audit`; 5 real `pip` CVEs found and fixed; 1 alarming-looking `chromadb` CVE correctly ruled out after checking actual usage |
| Corporate-network Python tooling | SSL interception silently broke some HTTPS-calling tools while others worked fine | Root cause identified (differing trust stores) and fixed via `pip_system_certs`, documented for reuse |

---

## Phase 23 — Image + PDF Attachments: Ephemeral Multimodal Input, Citations, and a Citation-Shape Bug

### What We Built
A 📎 file-attach feature for the chat UI — users can send one image or PDF alongside a message, and Claude reads it directly via native vision/document understanding (no OCR pipeline). Designed and shipped through a full plan-review-approval cycle: scope questions (upload method, persistence) up front, an Explore pass over the existing request-building code, a Plan agent producing a concrete file-by-file design, then implementation and real end-to-end testing — not just UI clicks, but actual "does Claude understand the image/PDF correctly" checks. Also added an "Available credit" line to the existing Discord daily digest.

### Key Concepts Learned

**"Ephemeral" is a design decision that has to be enforced at the data-flow level, not just intended.** The requirement was: send the file to Claude for this turn's analysis, but never persist it to SQLite session history. The mechanism that makes this actually true: `history` (the list that gets `session_save()`'d) only ever receives plain text from a small `_history_text_for()` helper — the message plus a `[User attached a file: name]` marker. The multimodal content block (image/document + base64) is built separately, in a throwaway `api_messages` list via `_build_api_messages()`, used for exactly one `tool_runner` call and discarded. Verified this actually held by inspecting the raw SQLite row after a real attachment turn — every stored `content` field was a plain string, no base64 anywhere — rather than trusting that the code "should" behave that way.

**A citation field-path bug that only a raw API test call caught.** Citation objects were assumed to nest their location fields under a `.page_location` sub-attribute (a reasonable-looking guess from the field name), so the extraction code did `getattr(getattr(c, "page_location", None), "start_page_number", None)` — which silently always returned `None`, since the attribute simply doesn't exist. The real shape: `start_page_number` sits **flat** on the citation object itself, alongside a `type: "page_location"` discriminator string. This never surfaced as an error — it just quietly produced no citation markers, ever. Caught only by writing a standalone script that called the raw Anthropic API directly with citations enabled and printing the actual response object, rather than debugging through the full app stack. **Generalizable principle: when a library's response shape is even slightly ambiguous from documentation prose, print the actual object once before writing extraction code against an assumed shape — a silent `None` from a wrong `getattr` chain produces no traceback to guide you back to the bug.**

**Citations require a real text layer — a rasterized PDF has nothing to cite against.** The first test PDF was built by saving a Pillow-drawn image as a PDF (`img.save("test.pdf", "PDF")`) — visually a normal-looking PDF, but with no embedded text, just a picture of text on each page. Claude read it fine via vision and even quoted the content accurately, but produced zero citations, which looked like the same bug above until a second PDF built with `fpdf2` (real embedded text) immediately produced correct `(p.1)` citations. The lesson generalizes past this feature: a file's apparent format doesn't guarantee the structure a downstream feature depends on — "it's a PDF" and "it has a text layer a citation engine can address" are different claims.

**Planning up front caught a UX gap the plan itself later exposed as necessary, not optional.** The approved plan called for the frontend to check `!res.ok` on the fetch response before parsing SSE — because a validation `400` returns a plain JSON error, not an SSE stream, and the existing SSE parser would have silently swallowed it (no `data:` prefix to match). This was flagged as a required fix *before* any code was written, not discovered after users hit a silent failure in production.

### Before vs After
| | Before | After |
|---|---|---|
| Chat input | Text only | Text + optional image or PDF attachment (file picker) |
| Document understanding | Only pre-indexed `knowledge_base/` files via `search_docs` | Ad-hoc, one-off files analyzed directly in a conversation, no indexing step |
| PDF citations | N/A | PDF attachments cite the exact page Claude drew from, shown inline as `(p.N)` |
| Session history | Always plain text | Still always plain text — attachments are explicitly ephemeral, verified via direct SQLite inspection |
| Cost tracking | Token-based, `web_search` needed a special flat-fee exception | Token-based only — confirmed image/PDF tokens need no special handling, unlike `web_search` |
| Daily Discord digest | Spend/tokens/top-tools recap | Same recap + "Available credit" remaining balance line |

---

## Final Architecture

```
Browser (http://localhost:8000)
  │
  │ HTTP / Server-Sent Events
  ▼
api.py (FastAPI)
  │
  ├──► Claude Sonnet 4.6 / Haiku 4.5 (Anthropic API)
  │         │
  │         │ tool calls
  │         ▼
  ├──► mcp_server.py (8 MCP Tools)
  │         │
  │         ├──► database.py (SQLite)
  │         │       ├── notes table
  │         │       └── sessions table
  │         │
  │         ├──► rag.py (ChromaDB)
  │         │       ├── index_docs
  │         │       └── search_docs
  │         │
  │         └──► docs/ folder
  │                 ├── .txt files
  │                 ├── .md files
  │                 └── .pdf → convert_pdfs.py → .txt
  │
  ├──► text_editor_tool.py (client-side tool — locked to docs/project_notes.md)
  │
  ├──► web_search (server-side tool — runs on Anthropic's infrastructure)
  │
  ├──► Discord webhook (mobile alerts — low balance, spend spike, tool budget, digest)
  │
  └──► agent.py (CLI — original learning version, still works)
```

---

## Full Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| AI Model | Claude Sonnet 4.6 / Haiku 4.5 | Language model (routed by query complexity) |
| AI SDK | Anthropic Python SDK | API client + tool runner + `BetaAsyncBuiltinFunctionTool` |
| Tool Protocol | MCP (Model Context Protocol) | Standard for AI tools |
| Native Tools | web_search (server-side), text editor (client-side) | Non-MCP Anthropic tools, declared directly in `api.py` |
| Mobile Alerts | Discord webhooks | 4 alert types (low-balance ×2 tiers, spend spike, per-tool budget, daily digest), traffic-triggered, no scheduler dependency |
| Web Framework | FastAPI | REST API + SSE streaming |
| Web Server | Uvicorn | ASGI server |
| Database | SQLite | Persistent notes + sessions |
| Vector Database | ChromaDB | Semantic search embeddings |
| Embeddings | sentence-transformers | Local ML embedding model |
| PDF Text | pypdf | Text-based PDF extraction |
| PDF OCR | pymupdf + Tesseract | Scanned PDF extraction |
| Version Control | Git + GitHub | Code history + backup |
| UI Testing | Playwright MCP | Drives chat.html/usage.html in a real browser via Claude Code |
| Language | Python 3.12 | Everything |

---

## What You Can Build Next

| Feature | Complexity | Teaches |
|---|---|---|
| Real weather API (OpenWeatherMap) | Low | External API calls from MCP tools |
| PostgreSQL instead of SQLite | Medium | Production databases |
| User authentication (JWT) | Medium | Security, multi-user apps |
| Docker containerisation | Medium | Deployment, portability |
| Deploy to cloud (Railway/Render) | Medium | Production hosting |
| GitHub MCP integration | Low | Using 3rd party MCP servers |
| React frontend | High | Modern web development |
