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

## Final Architecture

```
Browser (http://localhost:8000)
  │
  │ HTTP / Server-Sent Events
  ▼
api.py (FastAPI)
  │
  ├──► Claude Sonnet 4.6 (Anthropic API)
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
  └──► agent.py (CLI — original learning version, still works)
```

---

## Full Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| AI Model | Claude Sonnet 4.6 / Haiku 4.5 | Language model (routed by query complexity) |
| AI SDK | Anthropic Python SDK | API client + tool runner |
| Tool Protocol | MCP (Model Context Protocol) | Standard for AI tools |
| Web Framework | FastAPI | REST API + SSE streaming |
| Web Server | Uvicorn | ASGI server |
| Database | SQLite | Persistent notes + sessions |
| Vector Database | ChromaDB | Semantic search embeddings |
| Embeddings | sentence-transformers | Local ML embedding model |
| PDF Text | pypdf | Text-based PDF extraction |
| PDF OCR | pymupdf + Tesseract | Scanned PDF extraction |
| Version Control | Git + GitHub | Code history + backup |
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
