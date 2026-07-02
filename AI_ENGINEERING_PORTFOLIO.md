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

---

### 10. Prompt Evaluation Pipeline

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
| **MCP servers** | Extend Claude Code with GitHub, Playwright, and custom tools |
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
