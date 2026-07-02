# AI Engineering Portfolio — Vijay Anantaneni

**GitHub:** github.com/vijayanan6/mcp-project

---

## What I Built

A production-grade AI assistant from scratch — no tutorials, no boilerplate. Starting from zero knowledge of AI tooling, I designed and built a full-stack application where Claude (Anthropic's LLM) uses custom tools to answer questions, search documents semantically, and maintain persistent multi-turn conversations across browser sessions.

The app is live locally at `http://localhost:8000` and the full source is on GitHub.

---

## Architecture

```
Browser ──HTTP/SSE──► FastAPI (api.py) ──stdio/JSON-RPC──► MCP Server (mcp_server.py)
                           │                                        │
                           └──► Anthropic API (Claude)      SQLite + ChromaDB
```

Three processes. Two databases. One streaming chat interface. Built and understood every layer.

---

## Skills Demonstrated

### 1. MCP (Model Context Protocol)
**What it is:** Anthropic's open standard for connecting LLMs to external tools and data sources.

**What I built:**
- A custom MCP server (`mcp_server.py`) exposing 8 tools over stdio/JSON-RPC
- Tools: `get_current_datetime`, `calculate`, `get_weather`, `manage_notes`, `list_docs`, `read_doc`, `index_docs`, `search_docs`
- The server stays alive across all web requests via FastAPI's lifespan — not restarted per request

**Why it matters:** MCP is becoming the standard way enterprises connect AI to internal tools (databases, APIs, file systems). Building a custom server from scratch demonstrates I understand the protocol, not just how to use pre-built connectors.

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
**What it is:** A technique where documents are chunked, embedded into vectors, stored in a vector database, and searched semantically to give an LLM relevant context.

**What I built:**
- `rag.py` — full RAG pipeline: chunk → embed → store → search
- Chunking with overlap (500 char chunks, 100 char overlap at natural boundaries)
- Local embedding model: `all-MiniLM-L6-v2` via `sentence-transformers`
- Vector database: ChromaDB (persistent, on-disk)
- Auto-indexing on server startup; re-index by chat command

**Why it matters:** RAG is the most common pattern for giving LLMs access to private/internal knowledge. I implemented it from scratch, understanding every step — not just calling a LangChain wrapper.

```
User question → embed → ChromaDB similarity search → top 4 chunks → Claude → answer
```

---

### 3. Streaming (Server-Sent Events)
**What it is:** A technique where the server pushes chunks of data to the browser in real time as they're generated, rather than waiting for the full response.

**What I built:**
- `/stream` endpoint that yields SSE events as Claude generates text
- Event types: `tool` (tool being called), `text` (response chunk), `done` (includes model + token breakdown), `error`
- Frontend renders each chunk as it arrives — no page refresh

**Why it matters:** Every production AI chat UI (ChatGPT, Claude.ai, Gemini) uses streaming. Building it yourself means you understand the full request lifecycle, not just the happy path.

```python
async def generate():
    async for msg in runner:
        if block.type == "text":
            yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"

return StreamingResponse(generate(), media_type="text/event-stream")
```

---

### 4. Prompt Caching
**What it is:** Anthropic's feature that caches a fixed prefix of your prompt across API calls, reducing token costs by ~90% for repeated prefixes.

**What I built:**
- System prompt marked with `cache_control: {"type": "ephemeral"}`
- Token usage tracking across all tool-runner turns — `input`, `cache_write`, `cache_read`, `output`
- Token breakdown displayed live in the UI after each response

**Why it matters:** In production, the system prompt is sent on every API call. Without caching, a 500-token system prompt costs 500 tokens × every message × every user. With caching, it costs ~50 tokens after the first call. At scale, this is the difference between a viable and an unviable product.

```python
SYSTEM_PROMPT = [{
    "type": "text",
    "text": "You are a helpful assistant...",
    "cache_control": {"type": "ephemeral"}   # ~90% token savings after first call
}]
```

---

### 5. Model Routing
**What it is:** Automatically selecting the right LLM for each query based on complexity — cheap/fast model for simple queries, powerful model for complex ones.

**What I built:**
- `_pick_model()` function that routes to Haiku (10–20× cheaper) or Sonnet based on:
  - Message length > 120 chars → Sonnet
  - Keywords: doc, search, summarize, analyze → Sonnet
  - Everything else → Haiku
- Model name included in the `done` SSE event so the UI shows which model answered

**Why it matters:** Model routing is a standard cost-control pattern in enterprise AI. Blindly sending every query to your most powerful model is wasteful and expensive. Routing on heuristics without adding latency is the pragmatic production approach.

```python
def _pick_model(message: str) -> str:
    if len(message) > 120 or any(signal in message.lower() for signal in _COMPLEX_SIGNALS):
        return "claude-sonnet-4-6"
    return "claude-haiku-4-5"
```

---

### 6. Session Management & Persistent Conversation History
**What it is:** Storing multi-turn conversation history per user so the LLM can refer back to earlier messages.

**What I built:**
- SQLite `sessions` table — each session stores full conversation history as JSON
- History window: full history saved to DB, but only last 10 messages sent to Claude
- `_safe_window()` — guards against orphaned `tool_result` turns at the history boundary (an edge case that crashes the API if unhandled)
- Empty assistant turn guard — never saves a blank assistant turn to avoid corrupting history

**Why it matters:** This is the difference between a demo and a real product. Without persistence, every message starts fresh. With it, Claude remembers context across turns, browser refreshes, and server restarts.

---

### 7. FastAPI + Async Python
**What I built:**
- FastAPI web server with lifespan hooks, Pydantic request validation, async route handlers
- REST endpoints: `GET /`, `GET /tools`, `POST /chat`, `POST /stream`, `GET /sessions`, `DELETE /session/{id}`
- MCP server kept alive as a long-running subprocess (not spawned per request)
- `app.state` used to share tools and API client across all requests

---

### 8. PDF Processing (OCR Pipeline)
**What I built:**
- `convert_pdfs.py` — converts scanned PDFs to text using `pymupdf` (renders to image at 300 DPI) + `pytesseract` (OCR)
- Text-based PDFs read directly via `pypdf`
- Path traversal protection on all file access in `read_doc` tool

---

### 9. Configuration & Security Fundamentals
**What I built:**
- `.env` file + `python-dotenv` for API key management (industry standard, not OS env vars)
- `temperature=0.3` sampling — tuned for a tool-using assistant (consistent, not creative)
- SSL workaround for Windows corporate certificate chains — monkey-patched `httpx` before model download

---

### 10. Git & GitHub Workflow
- Feature branch workflow for every change
- Conventional commit messages (`feat:`, `fix:`, `docs:`)
- `.gitignore` for secrets (`.env`, `data.db`, `chroma_db/`)
- 10+ commits with clean history

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

---

## Key Engineering Decisions (and Why)

| Decision | Why |
|----------|-----|
| MCP over direct tool calls | Standard protocol — works with any MCP-compatible client |
| ChromaDB over in-memory search | Persists embeddings across restarts — no re-indexing cost |
| SQLite over dict | Survives server restarts — production pattern |
| Prompt caching | ~90% token savings on system prompt — cost-critical at scale |
| Model routing | 10–20× cost reduction for simple queries — standard enterprise pattern |
| SSE over WebSockets | Simpler for one-directional streaming; sufficient for chat |
| `temperature=0.3` | Tool-using assistants need consistency, not creativity |
| `.env` over OS env vars | Portable, project-scoped, industry standard |

---

## LinkedIn Post (Ready to Publish)

---

**Built a production-grade AI assistant from scratch. Here's what I learned.**

Over the past few weeks, I built a full-stack AI application using Anthropic's Claude — not with a no-code tool or a tutorial, but from the ground up.

Here's what's running:

**The stack:**
- FastAPI web server with real-time streaming (SSE)
- Custom MCP server with 8 tools Claude can use autonomously
- RAG pipeline: documents → chunked → embedded → ChromaDB → semantic search
- SQLite for persistent multi-turn conversation history
- Model routing: Haiku for simple queries, Sonnet for complex ones

**The concepts I implemented:**
- MCP (Model Context Protocol) — Anthropic's standard for AI tool integration
- Retrieval Augmented Generation (RAG) — from scratch, no LangChain
- Prompt caching — ~90% token savings on repeated system prompts
- Streaming responses — real-time text generation in the browser
- Session management — conversations that persist across restarts
- Model routing — automatic cost optimisation per query

**What I learned that most tutorials skip:**
- Prompt caching can cut your API costs by 90% — but you have to implement it deliberately
- Model routing is not optional at scale — not every query needs GPT-4/Sonnet
- RAG is 5 concepts stacked: chunk, embed, store, search, retrieve — understand each one
- Persistent history + a sliding window is how every real chat product works
- The MCP protocol is becoming the USB-C of AI tool integration

Full source on GitHub: github.com/vijayanan6/mcp-project

If you're learning AI engineering — build something end-to-end. Concepts only stick when they're solving a real problem in running code.

#AIEngineering #Python #MCP #RAG #Anthropic #Claude #FastAPI #MachineLearning #LLM

---

*GitHub: github.com/vijayanan6/mcp-project*
