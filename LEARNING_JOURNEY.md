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
- Windows SSL issue with `httpx` — fixed by monkey-patching `httpx.Client.__init__`

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
28b7a69  feat: add RAG with ChromaDB for semantic document search
f45961b  feat: prioritise docs + inspect_db utility
798a14c  feat: replace in-memory storage with SQLite database
d9346db  Initial commit - MCP learning project
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
| AI Model | Claude Sonnet 4.6 | Language model |
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
