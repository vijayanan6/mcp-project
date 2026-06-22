# MCP Learning Project

A hands-on project to learn **Model Context Protocol (MCP)** by building a custom MCP server,
an AI agent, and a full-stack web application with semantic document search.

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
├── mcp_server.py           — MCP server with 8 tools
├── database.py             — SQLite layer (notes + sessions)
├── rag.py                  — ChromaDB semantic search
├── convert_pdfs.py         — Tesseract OCR for scanned PDFs
├── inspect_db.py           — Utility to view SQLite contents
├── templates/
│   └── chat.html           — Browser chat UI
├── docs/                   — Drop your documents here
├── LEARNING_JOURNEY.md     — Full phase-by-phase learning record
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
  ├──► Claude Sonnet 4.6 (Anthropic API)
  │         │ tool calls
  │         ▼
  └──► mcp_server.py (8 MCP Tools)
            ├──► database.py  → SQLite (notes + sessions persist across restarts)
            ├──► rag.py       → ChromaDB (semantic document search)
            └──► docs/        → your documents (txt, md, PDF)
```

---

## All 8 Tools

| Tool | Description |
|---|---|
| `get_current_datetime` | Current date and time |
| `calculate` | Safe math expression evaluator |
| `get_weather` | Mock weather data by city |
| `manage_notes` | Persistent CRUD notes (SQLite) |
| `list_docs` | Lists files in docs/ folder |
| `read_doc` | Reads full content of a document |
| `index_docs` | Indexes docs into ChromaDB for semantic search |
| `search_docs` | Semantic search — finds relevant chunks for any query |

---

## Setup

### Prerequisites
- Python 3.10+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Tesseract OCR (for scanned PDFs): `github.com/UB-Mannheim/tesseract/wiki`

### Install dependencies
```powershell
pip install anthropic[mcp] mcp pymupdf pytesseract pypdf fastapi "uvicorn[standard]" chromadb sentence-transformers
```

### Set your API key (one-time, permanent)
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

### Run the web app
```powershell
$env:ANTHROPIC_API_KEY = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
python -m uvicorn api:app --reload --port 8000
```

Open **`http://localhost:8000`** in your browser.

### Or run the CLI agent
```powershell
python agent.py
```

---

## How to Add a New Tool

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
| `init_db()` | `database.py` | Creates SQLite tables on startup |
| `index_all()` | `rag.py` | Chunks + embeds all docs into ChromaDB |
| `search()` | `rag.py` | Semantic similarity search |
| `async_mcp_tool()` | `agent.py` / `api.py` | Bridges MCP tools to Anthropic SDK |

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

---

## GitHub

`github.com/vijayanan6/mcp-project`

---

## Next Steps

- Replace mock weather with real OpenWeatherMap API
- Add user authentication (JWT tokens)
- Switch SQLite → PostgreSQL
- Deploy to cloud (Railway / Render)
- Add React frontend
- Connect GitHub MCP server
