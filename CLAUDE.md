# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
# Install all dependencies
pip install anthropic[mcp] mcp pymupdf pytesseract pypdf

# Run the AI agent (entry point — auto-starts mcp_server.py)
python agent.py

# Convert scanned PDFs in docs/ to .txt using Tesseract OCR
python convert_pdfs.py
```

Tesseract must be installed at `C:\Program Files\Tesseract-OCR\` for `convert_pdfs.py` to work.

## Architecture

Two processes run when the agent is active:

**`agent.py`** — the user-facing CLI. Spawns `mcp_server.py` as a subprocess via stdio transport, performs the MCP handshake, discovers tools, wraps them with `async_mcp_tool()`, and drives the conversation loop using `client.beta.messages.tool_runner()`. Conversation history is kept in a plain list and passed to Claude on every turn. The Anthropic SDK (`anthropic[mcp]`) lives here.

**`mcp_server.py`** — the MCP server. Has no knowledge of Claude or the Anthropic SDK. Exposes 6 tools via `@app.list_tools()` and `@app.call_tool()` decorators. Notes are stored in a module-level dict (in-memory, lost on exit). The `docs/` folder path is resolved relative to this file's location.

```
agent.py  ──stdio/JSON-RPC──►  mcp_server.py (subprocess)
    │
    └──► Anthropic API (Claude claude-sonnet-4-6)
```

## Tools

| Tool | Notes |
|---|---|
| `get_current_datetime` | No params |
| `calculate` | `eval()` with restricted namespace — only math functions allowed |
| `get_weather` | Mock data dict — replace with real API for production |
| `manage_notes` | In-memory only; `notes` dict is module-level in `mcp_server.py` |
| `list_docs` | Reads `docs/` folder; supports `.txt .md .csv .json .py .html .xml .pdf` |
| `read_doc` | Path traversal blocked by resolving and checking against `docs/` root; 8000-char truncation cap |

## Adding a New Tool

1. Add a `types.Tool(...)` entry in `list_tools()` in `mcp_server.py`
2. Add an `if name == "tool_name":` handler in `call_tool()` returning `list[types.TextContent]`
3. Restart `agent.py` — tool discovery is automatic on each session start

## docs/ Folder

Place `.txt`, `.md`, or `.pdf` files here for the agent to read. Scanned PDFs must be pre-converted via `convert_pdfs.py` (Tesseract OCR) before the agent can read their content. Text-based PDFs are read directly by `mcp_server.py` using `pypdf`.

## Key Dependencies

| Package | Purpose |
|---|---|
| `anthropic[mcp]` | Anthropic SDK + `async_mcp_tool` bridge |
| `mcp` | MCP server/client protocol implementation |
| `pypdf` | Text extraction from text-based PDFs |
| `pymupdf` | Renders PDF pages to images for OCR |
| `pytesseract` | Python wrapper for Tesseract OCR |

## Upcoming: SQLite database for persistent storage
