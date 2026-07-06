# MCP Learning Project Notes

## What I Built
A full-stack AI application starting from a CLI script and growing into a
web application with browser chat UI, persistent database, and semantic document search.

---

## Final Architecture

```
Browser (http://localhost:8000)
  │
  ▼
api.py (FastAPI web server)
  │
  ├──► Claude Sonnet 4.6 (Anthropic API)
  │         │ tool calls
  │         ▼
  ├──► mcp_server.py (8 MCP tools)
  │         ├──► database.py   → SQLite (notes + sessions)
  │         ├──► rag.py        → ChromaDB (semantic search)
  │         └──► docs/         → documents (txt, md, PDF)
  │
  └──► agent.py (original CLI — still works)
```

---

## All 8 MCP Tools

| Tool | What it does | Storage |
|---|---|---|
| `get_current_datetime` | Current date and time | — |
| `calculate` | Safe math expression evaluator | — |
| `get_weather` | Mock weather data for cities | — |
| `manage_notes` | CRUD for personal notes | SQLite |
| `list_docs` | Lists files in docs/ folder | Filesystem |
| `read_doc` | Reads a full document | Filesystem |
| `index_docs` | Indexes docs into ChromaDB | ChromaDB |
| `search_docs` | Semantic search across all docs | ChromaDB |

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
12. Sessions stored as JSON in a TEXT column — flexible for conversations

### RAG
13. RAG = chunk documents → embed → store in vector DB → search by meaning
14. Embedding converts text to vectors; similar meaning = similar vectors
15. ChromaDB stores vectors and finds closest matches to a query
16. Chunking splits large files into ~500 char pieces with overlap
17. Much cheaper than reading entire documents — only sends relevant parts to Claude

### Git & GitHub
18. Feature branches keep main always working
19. `git checkout -b feature/name` → code → commit → merge → push
20. `.gitignore` protects sensitive files and local databases from being uploaded

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Claude Sonnet 4.6 |
| AI SDK | anthropic[mcp] |
| Tool Protocol | MCP (Model Context Protocol) |
| Web Framework | FastAPI |
| Web Server | Uvicorn |
| Database | SQLite (built-in Python) |
| Vector Database | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| PDF Text | pypdf |
| PDF OCR | pymupdf + Tesseract |
| Version Control | Git + GitHub |
| Language | Python 3.12 |

---

## Project Files

| File | Purpose |
|---|---|
| `mcp_server.py` | MCP server — defines and runs all 8 tools |
| `agent.py` | CLI agent (original learning version) |
| `api.py` | FastAPI web server with SSE streaming |
| `database.py` | SQLite layer for notes + sessions |
| `rag.py` | ChromaDB indexing + semantic search |
| `convert_pdfs.py` | Tesseract OCR for scanned PDFs |
| `inspect_db.py` | Utility to view SQLite contents |
| `tool_use_demo.py` | Tool Use Fundamentals demo — raw SDK, no `tool_runner` |
| `templates/chat.html` | Browser chat UI |
| `CLAUDE.md` | Guidance for Claude Code |
| `README.md` | Project documentation |
| `LEARNING_JOURNEY.md` | Full phase-by-phase learning record |

---

## How to Run

```powershell
# Set API key (one-time)
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")

# Start the web app
$env:ANTHROPIC_API_KEY = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
cd "c:\Users\vijay\OneDrive\Desktop\Claude Workspace\MCP Project"
python -m uvicorn api:app --reload --port 8000

# Open browser at http://localhost:8000
```

---

## GitHub Repository
`github.com/vijayanan6/mcp-project`

---

## Next Steps to Explore
- Replace mock weather with real OpenWeatherMap API
- Add user authentication (JWT tokens)
- Switch from SQLite to PostgreSQL
- Deploy to cloud (Railway / Render)
- Add React frontend
- Connect GitHub MCP server to manage the repo from chat
