# Architecture Overview

This document describes how the MCP Learning Project is structured,
how its components connect, and how data flows through the system.

---

## System Overview

The application has three layers — a browser frontend, a FastAPI backend,
and a collection of MCP tools. The user talks to the browser, the browser
talks to FastAPI, FastAPI talks to Claude, and Claude calls tools through
the MCP server.

```
Browser
  └── chat.html (chat UI)
        │
        │ HTTP / Server-Sent Events
        ▼
  api.py (FastAPI — port 8000)
        │
        ├── Anthropic API (Claude Sonnet 4.6)
        │         │
        │         │ tool calls
        │         ▼
        └── mcp_server.py (MCP Server — subprocess)
                  │
                  ├── database.py  →  data.db (SQLite)
                  ├── rag.py       →  chroma_db/ (ChromaDB)
                  └── docs/        →  your documents
```

There is also `agent.py` — the original CLI version of the agent. It
connects to the same `mcp_server.py` but uses the terminal instead of
a browser. Both interfaces work.

---

## Components

### api.py — Web Server
The entry point for the web application. Built with FastAPI.

- Starts `mcp_server.py` as a subprocess on startup and keeps it alive
- Receives chat messages from the browser via HTTP POST
- Streams Claude's responses back in real time using Server-Sent Events
- Stores and retrieves conversation history from SQLite
- Auto-indexes documents into ChromaDB on startup
- Exposes endpoints: `/`, `/chat`, `/stream`, `/tools`, `/sessions`

### mcp_server.py — MCP Server
The tool engine. Has no knowledge of Claude, HTTP, or the browser.
It simply defines tools and executes them when called.

- Communicates with api.py over stdin/stdout using JSON-RPC 2.0
- Exposes 8 tools (listed below)
- Notes are stored in SQLite via database.py
- Document search runs through ChromaDB via rag.py

### database.py — SQLite Layer
Handles all database operations. Two tables:

- **notes** — stores user-saved notes permanently (title, content, timestamp)
- **sessions** — stores full chat history per session as a JSON array

Data survives restarts. Before this, everything was stored in Python
dicts and lost when the app stopped.

### rag.py — Semantic Search
Handles document indexing and retrieval using ChromaDB.

- Splits documents into ~500 character chunks with 100 character overlap
- Embeds each chunk using the `all-MiniLM-L6-v2` model (384-dimensional vectors)
- Stores vectors in ChromaDB on disk
- On a search query: embeds the question, finds the 4 most similar chunks,
  returns them with source filename and relevance score

### agent.py — CLI Agent
The original learning version. Same MCP connection logic as api.py
but uses a terminal input loop instead of HTTP. Useful for quick testing.

### chat.html — Browser UI
A single-page chat interface built with vanilla JavaScript.

- Sends messages to `/stream` and reads Server-Sent Events in real time
- Shows tool call indicators (e.g. `→ search_docs`) as Claude uses tools
- Persists session ID in browser localStorage across page reloads

### convert_pdfs.py — PDF Converter
Standalone script for converting scanned PDFs to readable text.

- Uses pymupdf to render each PDF page as a high-resolution image
- Runs Tesseract OCR on each image to extract text
- Saves a `.txt` file alongside the original PDF
- Run manually after adding new scanned PDFs to docs/

### inspect_db.py — Database Viewer
Utility script that prints the contents of SQLite (notes and sessions).
Useful for debugging or verifying what's stored.

---

## The 8 MCP Tools

| Tool | What it does | Where data lives |
|---|---|---|
| `get_current_datetime` | Returns current date and time | — |
| `calculate` | Evaluates a math expression safely | — |
| `get_weather` | Returns mock weather for a city | — |
| `manage_notes` | Save, read, list, delete notes | SQLite |
| `list_docs` | Lists all files in docs/ folder | Filesystem |
| `read_doc` | Reads the full content of a file | Filesystem |
| `index_docs` | Indexes all docs into ChromaDB | ChromaDB |
| `search_docs` | Semantic search across indexed docs | ChromaDB |

---

## How a Question Gets Answered

Here is the step-by-step flow when a user asks a question in the browser:

1. User types a question and presses Send
2. Browser sends `POST /stream` to api.py with the message and session ID
3. api.py loads the conversation history for that session from SQLite
4. `_pick_model()` routes the message: Haiku for short/simple queries, Sonnet for long or doc-related ones
5. `_safe_window()` trims history to the last 10 messages, dropping any orphaned `tool_result` turns
6. api.py sends the window plus all 8 tool schemas to Claude, with the system prompt marked `cache_control: ephemeral`
7. Claude reads the cached system prompt: *"call search_docs for topic-specific questions; skip for clearly general ones"*
8. Claude decides whether to call `search_docs` based on the question type
9. api.py forwards the tool call to mcp_server.py via stdin/stdout
10. mcp_server.py calls rag.py, which searches ChromaDB
11. ChromaDB returns the 4 most relevant document chunks
12. The result is sent back to Claude
13. Claude writes a final answer based on the retrieved chunks
14. api.py streams the response back to the browser in real time as SSE chunks
15. The browser renders each text chunk as it arrives
16. When Claude finishes, api.py sends a `done` event containing the model used and a token usage breakdown
17. api.py saves the updated conversation to SQLite (only if Claude produced a non-empty response)

---

## How RAG Works

RAG (Retrieval Augmented Generation) allows Claude to answer questions
from large documents without reading them entirely.

**Indexing phase** (runs on startup):
```
docs/*.txt and *.md
  → split into ~500 char chunks
  → each chunk embedded into a 384-number vector
  → stored in ChromaDB with {filename, chunk number}
```

**Query phase** (every question):
```
user question
  → embedded into a 384-number vector
  → compared against all stored vectors
  → top 4 closest chunks returned
  → sent to Claude as context
```

This means a 50-page document becomes searchable. Claude only
sees the 4 paragraphs most relevant to the question, not the whole file.

---

## Data Storage

### SQLite (data.db)
Local file database. Created automatically on first run.

```
notes table
  title       — note name (primary key)
  content     — note text
  created_at  — timestamp

sessions table
  session_id  — unique conversation ID (primary key)
  messages    — full chat history stored as JSON
  created_at  — when session started
  updated_at  — last message time
```

### ChromaDB (chroma_db/)
Local vector database folder. Created automatically on first run.

```
docs collection
  id         — "filename::chunk::0", "filename::chunk::1", etc.
  document   — the actual text chunk
  embedding  — 384-dimensional float vector
  metadata   — {source: "filename.txt", chunk_index: 0}
```

Both `data.db` and `chroma_db/` are excluded from Git (in `.gitignore`).
They are local only and rebuilt automatically when the app starts.

---

## PDF Processing Flow

Scanned PDFs (images of pages, no text layer) require a separate
conversion step before the agent can read them.

```
scanned PDF in docs/
  → python convert_pdfs.py
  → pymupdf renders each page at 300 DPI → PNG image
  → pytesseract runs Tesseract OCR on each image
  → extracted text saved as filename.txt in docs/
  → restart app → txt file gets indexed automatically
```

Text-based PDFs (PDFs with an actual text layer) are read directly
by `read_doc` using pypdf — no conversion needed.

---

## Model Routing

Not every question needs the same model. `_pick_model()` in api.py routes each message:

```
Message arrives
  ├── len > 120 chars?          → claude-sonnet-4-6
  ├── contains doc keyword?     → claude-sonnet-4-6
  │   (doc, file, search, note, summarize, analyze, report, …)
  └── else                      → claude-haiku-4-5
```

Haiku is 10–20× cheaper than Sonnet for short conversational questions. Sonnet is
used when the query is complex or involves document reasoning. The chosen model is
included in the `done` SSE event so the UI can display which model answered.

---

## Token Management

Three techniques keep costs low as conversations grow:

**Prompt caching** — The system prompt is marked `cache_control: {"type": "ephemeral"}`.
Anthropic caches this prefix for 5 minutes. After the first call, subsequent turns
pay ~0.1× the normal rate for those tokens instead of the full rate.

**History window** — The full conversation is stored in SQLite but only the last
10 messages are sent to Claude (`HISTORY_LIMIT`). This caps context size so
costs don't grow with conversation length.

**Usage tracking** — Token counts are accumulated across all tool-runner turns
(one turn per tool round-trip) and sent to the browser in the `done` event:

```json
{ "type": "done", "model": "claude-haiku-4-5",
  "usage": { "input": 312, "cache_write": 0, "cache_read": 890, "output": 47 } }
```

`cache_read` tokens cost ~90% less than `input` tokens — a high `cache_read`
relative to `input` means prompt caching is working correctly.

---

## Technology Stack

| Layer | Technology | Why |
|---|---|---|
| AI Model | Claude Sonnet 4.6 | Fast, capable, supports tool use |
| AI SDK | anthropic[mcp] | Official SDK + MCP bridge |
| Tool Protocol | MCP (Model Context Protocol) | Standard for AI tools |
| Web Framework | FastAPI | Modern async Python web framework |
| Web Server | Uvicorn | ASGI server for FastAPI |
| Database | SQLite | Built into Python, zero setup |
| Vector Database | ChromaDB | Local vector store, no server needed |
| Embeddings | sentence-transformers | Local ML model, no API cost |
| PDF (text) | pypdf | Lightweight PDF text extraction |
| PDF (scanned) | pymupdf + Tesseract | Render pages → OCR → text |
| Version Control | Git + GitHub | Code history and backup |
| Language | Python 3.12 | Everything |

---

## File Map

```
MCP Project/
│
├── api.py              Web server — FastAPI, routes, SSE, lifespan
├── agent.py            CLI agent — terminal interface, same MCP logic
├── mcp_server.py       MCP server — 8 tool definitions and handlers
├── database.py         SQLite helpers — notes and sessions CRUD
├── rag.py              ChromaDB helpers — chunk, embed, index, search
├── convert_pdfs.py     PDF OCR — pymupdf + Tesseract → txt
├── inspect_db.py       Utility — print SQLite contents
│
├── templates/
│   └── chat.html       Browser chat UI — SSE streaming, session storage
│
├── docs/               Drop documents here
│   ├── *.txt           Plain text files
│   ├── *.md            Markdown files
│   └── *.pdf           PDFs (convert scanned ones first)
│
├── data.db             SQLite database (auto-created, gitignored)
├── chroma_db/          ChromaDB vector store (auto-created, gitignored)
│
├── CLAUDE.md           Guidance for Claude Code
├── README.md           Project overview and setup
├── ARCHITECTURE.md     This file
├── LEARNING_JOURNEY.md Phase-by-phase learning record
└── requirements.txt    Python dependencies
```
