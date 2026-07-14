#!/usr/bin/env python3
"""
MCP Server — Learning Project

This file creates a custom MCP (Model Context Protocol) server.
It exposes 6 tools that Claude can call:

  • get_current_datetime  — real-time date/time (no params)
  • calculate             — safe math expression evaluator
  • get_weather           — mock weather data by city
  • manage_notes          — SQLite-backed CRUD for text notes (persistent)

How it works:
  1. The server starts and listens on stdin for JSON-RPC messages
  2. agent.py launches this as a subprocess and connects via stdio
  3. agent.py asks "what tools do you have?" → list_tools() is called
  4. When Claude wants to use a tool → call_tool() is called
  5. Results are returned as TextContent and fed back to Claude
"""
import asyncio
import math
from datetime import datetime
from pathlib import Path

try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

from database import init_db, note_save, note_get, note_list, note_delete
from rag import index_all, search, get_stats

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Create the MCP server — the name shows up in logs and debug output
app = Server("learning-mcp-server")

# Initialize the SQLite database on startup
init_db()


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """
    Called by MCP clients to discover what tools this server offers.

    Each Tool definition has three parts:
      - name        : identifier used when calling the tool
      - description : tells Claude WHEN and HOW to use the tool (very important!)
      - inputSchema : JSON Schema describing the tool's parameters
    """
    return [
        # ── Tool 1: No parameters ─────────────────────────────────────────
        types.Tool(
            name="get_current_datetime",
            description=(
                "Returns the current date and time. "
                "Use this when the user asks about the date, day of the week, or current time."
            ),
            inputSchema={
                "type": "object",
                "properties": {},   # no parameters needed
            },
        ),

        # ── Tool 2: Required string parameter ────────────────────────────
        types.Tool(
            name="calculate",
            description=(
                "Safely evaluates a mathematical expression and returns the result. "
                "Supports: +, -, *, /, ** (power), sqrt(), sin(), cos(), tan(), "
                "log(), pi, e, abs(), round(). "
                "Examples: 'sqrt(144)', '2 ** 10', 'sin(pi / 2)', '100 * 1.08'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate, e.g. 'sqrt(144)'",
                    }
                },
                "required": ["expression"],
            },
        ),

        # ── Tool 3: Required string parameter ────────────────────────────
        types.Tool(
            name="get_weather",
            description=(
                "Returns current weather conditions for a city. "
                "NOTE: This uses demo/mock data, not a real weather API. "
                "Use when the user asks about weather in a specific place."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 'London', 'Tokyo', 'New York'",
                    }
                },
                "required": ["city"],
            },
        ),

        # ── Tool 4: Enum + optional parameters ───────────────────────────
        types.Tool(
            name="manage_notes",

            description=(
                "Save, read, list, or delete personal notes stored in memory. "
                "Notes are lost when the agent exits. "
                "Use 'save' to store a note, 'read' to retrieve one by title, "
                "'list' to see all titles, 'delete' to remove one."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["save", "read", "list", "delete"],
                        "description": "What operation to perform",
                    },
                    "title": {
                        "type": "string",
                        "description": "Note title / key (required for save, read, delete)",
                    },
                    "content": {
                        "type": "string",
                        "description": "The text body of the note (required for save)",
                    },
                },
                "required": ["action"],
            },
        ),

        # ── Tool 5: Index documents into ChromaDB ────────────────────────
        types.Tool(
            name="index_docs",
            description=(
                "Indexes all documents in the knowledge_base/ folder into ChromaDB for semantic search. "
                "Call this once after adding new documents, or when the user asks to index/update docs. "
                "Only needs to be called again when new files are added."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),

        # ── Tool 6: Semantic search across indexed documents ──────────────
        types.Tool(
            name="search_docs",
            description=(
                "Semantically searches all indexed documents and returns the most relevant chunks. "
                "Use this INSTEAD of read_doc when answering questions about documents — "
                "it finds only the relevant parts without reading entire files. "
                "Returns the top matching passages with their source filenames."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or topic to search for",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of chunks to return (default 4)",
                    },
                },
                "required": ["query"],
            },
        ),

        # ── Tool 7: List documents ────────────────────────────────────────
        types.Tool(
            name="list_docs",
            description=(
                "Lists all readable documents in the knowledge_base/ folder. "
                "Call this first when the user asks a question about their documents "
                "or files, to see what is available before reading one."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),

        # ── Tool 6: Read a document ───────────────────────────────────────
        types.Tool(
            name="read_doc",
            description=(
                "Reads the full content of a document from the knowledge_base/ folder. "
                "Use this to retrieve file contents so you can answer questions about it. "
                "Always call list_docs first to confirm the filename."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Exact filename to read, e.g. 'report.txt' or 'notes.md'",
                    }
                },
                "required": ["filename"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """
    Called when Claude (via the agent) invokes a tool.
    Receives the tool name and a dict of arguments.
    Must return a list of TextContent objects.
    """

    # ── Tool: get_current_datetime ────────────────────────────────────────
    if name == "get_current_datetime":
        now = datetime.now()
        return [types.TextContent(
            type="text",
            text=now.strftime("Today is %A, %B %d, %Y. The current time is %I:%M %p."),
        )]

    # ── Tool: calculate ───────────────────────────────────────────────────
    if name == "calculate":
        expr = arguments.get("expression", "")

        # Use eval() with a restricted namespace for safe math.
        # Setting __builtins__ to {} blocks access to open(), exec(),
        # __import__(), and all other dangerous built-ins.
        safe_env = {
            "__builtins__": {},
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "pi": math.pi,
            "e": math.e,
            "abs": abs,
            "round": round,
            "pow": pow,
        }
        try:
            result = eval(expr, safe_env)  # noqa: S307
            return [types.TextContent(type="text", text=f"{expr} = {result}")]
        except Exception as err:
            return [types.TextContent(type="text", text=f"Cannot evaluate '{expr}': {err}")]

    # ── Tool: get_weather ─────────────────────────────────────────────────
    if name == "get_weather":
        city = arguments.get("city", "Unknown")

        # Mock data — swap this for a real API call (e.g. OpenWeatherMap) in production
        weather_db = {
            "london":   (14, "Overcast",      78),
            "new york": (22, "Partly Cloudy",  55),
            "tokyo":    (27, "Humid",          82),
            "paris":    (17, "Light Rain",     70),
            "sydney":   (22, "Sunny",          48),
            "dubai":    (38, "Hot and Sunny",  30),
            "mumbai":   (32, "Tropical",       85),
            "berlin":   (12, "Cloudy",         72),
            "singapore":(30, "Thunderstorms",  90),
        }
        temp_c, condition, humidity = weather_db.get(city.lower(), (20, "Clear", 60))
        temp_f = round(temp_c * 9 / 5 + 32)

        return [types.TextContent(
            type="text",
            text=(
                f"Weather in {city}:\n"
                f"  Condition   : {condition}\n"
                f"  Temperature : {temp_c}°C / {temp_f}°F\n"
                f"  Humidity    : {humidity}%"
            ),
        )]

    # ── Tool: manage_notes ────────────────────────────────────────────────
    if name == "manage_notes":
        action  = arguments.get("action", "")
        title   = arguments.get("title", "").strip()
        content = arguments.get("content", "")

        if action == "save":
            if not title:
                return [types.TextContent(type="text", text="Error: 'title' is required to save a note.")]
            note_save(title, content)   # ← saved to SQLite, survives restarts
            return [types.TextContent(type="text", text=f"Note '{title}' saved.")]

        if action == "read":
            if not title:
                return [types.TextContent(type="text", text="Error: 'title' is required to read a note.")]
            note = note_get(title)
            if not note:
                return [types.TextContent(type="text", text=f"No note found with title '{title}'.")]
            return [types.TextContent(
                type="text",
                text=f"Note: {title}\nCreated: {note['created_at']}\n\n{note['content']}",
            )]

        if action == "list":
            titles = note_list()
            if not titles:
                return [types.TextContent(type="text", text="No notes saved yet.")]
            listing = "\n".join(f"  • {t}" for t in titles)
            return [types.TextContent(type="text", text=f"Saved notes ({len(titles)}):\n{listing}")]

        if action == "delete":
            if not title:
                return [types.TextContent(type="text", text="Error: 'title' is required to delete a note.")]
            if not note_delete(title):
                return [types.TextContent(type="text", text=f"No note found with title '{title}'.")]
            return [types.TextContent(type="text", text=f"Note '{title}' deleted.")]

    # ── Tool: index_docs ─────────────────────────────────────────────────
    if name == "index_docs":
        results = index_all()
        if not results:
            return [types.TextContent(type="text", text="No supported files found in knowledge_base/. Add .txt or .md files first.")]
        lines = "\n".join(f"  • {f}: {c} chunks" for f, c in results.items())
        stats = get_stats()
        return [types.TextContent(
            type="text",
            text=f"Indexed {len(results)} file(s) into ChromaDB:\n{lines}\n\nTotal: {stats['total_chunks']} chunks ready for search.",
        )]

    # ── Tool: search_docs ─────────────────────────────────────────────────
    if name == "search_docs":
        query = arguments.get("query", "").strip()
        n = arguments.get("n_results", 4)
        if not query:
            return [types.TextContent(type="text", text="Error: 'query' is required.")]

        stats = get_stats()
        if stats["total_chunks"] == 0:
            return [types.TextContent(
                type="text",
                text="No documents indexed yet. Call index_docs first.",
            )]

        chunks = search(query, n_results=n)
        if not chunks:
            return [types.TextContent(type="text", text="No relevant content found for that query.")]

        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[{i}] Source: {chunk['source']} (relevance: {chunk['score']})\n{chunk['content']}")

        return [types.TextContent(type="text", text="\n\n---\n\n".join(parts))]

    # ── Tool: list_docs ───────────────────────────────────────────────────
    if name == "list_docs":
        docs_dir = Path(__file__).parent.parent.parent / "knowledge_base"
        docs_dir.mkdir(exist_ok=True)  # create folder if it doesn't exist yet

        supported = {".txt", ".md", ".csv", ".json", ".py", ".html", ".xml", ".pdf"}
        files = sorted(f.name for f in docs_dir.iterdir() if f.is_file() and f.suffix in supported)

        if not files:
            return [types.TextContent(
                type="text",
                text="No documents found in the knowledge_base/ folder. Add .txt or .md files there and try again.",
            )]

        listing = "\n".join(f"  • {f}" for f in files)
        return [types.TextContent(type="text", text=f"Documents available ({len(files)}):\n{listing}")]

    # ── Tool: read_doc ────────────────────────────────────────────────────
    if name == "read_doc":
        filename = arguments.get("filename", "").strip()
        if not filename:
            return [types.TextContent(type="text", text="Error: 'filename' is required.")]

        docs_dir = Path(__file__).parent.parent.parent / "knowledge_base"

        # Resolve paths and block directory traversal (e.g. ../../secrets.txt)
        try:
            target = (docs_dir / filename).resolve()
            if not str(target).startswith(str(docs_dir.resolve())):
                return [types.TextContent(type="text", text="Error: access outside knowledge_base/ folder is not allowed.")]
        except Exception:
            return [types.TextContent(type="text", text="Error: invalid filename.")]

        if not target.exists():
            return [types.TextContent(type="text", text=f"File '{filename}' not found. Use list_docs to see available files.")]

        try:
            # PDF: extract text from all pages using pypdf
            if target.suffix.lower() == ".pdf":
                if not PDF_SUPPORT:
                    return [types.TextContent(
                        type="text",
                        text="PDF support requires pypdf. Run: pip install pypdf",
                    )]
                reader = PdfReader(str(target))
                pages_text = []
                for i, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_text.append(f"--- Page {i} ---\n{text.strip()}")
                content = "\n\n".join(pages_text) if pages_text else "[No readable text found in PDF]"
                total_pages = len(reader.pages)
            else:
                content = target.read_text(encoding="utf-8")
                total_pages = None

            size = len(content)
            # Cap at 8000 chars to stay within Claude's context comfortably
            if size > 8000:
                content = content[:8000] + f"\n\n[... truncated — showing first 8000 of {size} chars ...]"

            header = f"=== {filename} ==="
            if total_pages:
                header += f" ({total_pages} pages)"
            return [types.TextContent(type="text", text=f"{header}\n\n{content}")]
        except Exception as err:
            return [types.TextContent(type="text", text=f"Error reading '{filename}': {err}")]

    return [types.TextContent(type="text", text=f"Unknown tool: '{name}'")]


async def main():
    """Start the MCP server. It communicates via stdin/stdout (stdio transport)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
