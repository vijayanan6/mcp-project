#!/usr/bin/env python3
"""
MCP Server — Learning Project

This file creates a custom MCP (Model Context Protocol) server.
It exposes all three MCP primitives:

  Tools (8)     — actions Claude can invoke: get_current_datetime, calculate,
                  get_weather, manage_notes, list_docs, read_doc, index_docs,
                  search_docs
  Resources (2 kinds) — read-only, URI-addressable data Claude reads directly:
                  knowledgebase://files (static file listing) and
                  note://<title> (one per saved note, enumerated live)
  Prompts (1)   — reusable request templates: summarize_document

How it works:
  1. The server starts and listens on stdin for JSON-RPC messages
  2. agent.py/api.py launch this as a subprocess and connect via stdio
  3. The client asks "what tools/resources/prompts do you have?" →
     list_tools()/list_resources()/list_prompts() are called
  4. When Claude wants to use a tool → call_tool() is called
  5. When a client reads a resource → read_resource() is called
  6. When a client invokes a prompt → get_prompt() is called
  7. Results are returned as TextContent and fed back to Claude
"""
import asyncio
import math
import urllib.parse
from datetime import datetime
from pathlib import Path

from pydantic import AnyUrl

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

_KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent.parent / "knowledge_base"
_SUPPORTED_DOC_SUFFIXES = {".txt", ".md", ".csv", ".json", ".py", ".html", ".xml", ".pdf"}

# search()'s own docstring documents distance < 0.8 (similarity > 0.2) as the
# intended "relevant" cutoff, but never enforced it — every call returned the
# nearest chunks regardless of how weak the actual match was. This is the same
# threshold, now actually applied in search_docs's fallback below.
_SEARCH_RELEVANCE_THRESHOLD = 0.2


def _knowledge_base_files() -> list[str]:
    """Sorted list of supported document filenames in knowledge_base/. Shared
    by list_docs, the knowledgebase:// resource, and search_docs's low-
    relevance fallback — previously duplicated inline in the first two."""
    _KNOWLEDGE_BASE_DIR.mkdir(exist_ok=True)
    return sorted(
        f.name for f in _KNOWLEDGE_BASE_DIR.iterdir()
        if f.is_file() and f.suffix in _SUPPORTED_DOC_SUFFIXES
    )


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
        if not isinstance(expr, str):
            return [types.TextContent(type="text", text="Error: 'expression' must be a string.")]
        # A length cap catches the common case cheaply, but doesn't fully close
        # computational-DoS risk on its own — a short expression like "9**9**9"
        # still explodes to an astronomically large number. __builtins__: {}
        # below is what actually stops code execution; this cap only stops the
        # cheapest attack (a pathologically long expression string).
        if len(expr) > 200:
            return [types.TextContent(type="text", text="Error: expression too long (max 200 characters).")]

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
        title   = arguments.get("title", "")
        content = arguments.get("content", "")
        # .strip() below would crash with AttributeError on a non-string
        # argument (e.g. Claude — or a malformed call — passing a number);
        # never assume the declared inputSchema type was actually honored.
        if not isinstance(title, str) or not isinstance(content, str):
            return [types.TextContent(type="text", text="Error: 'title' and 'content' must be strings.")]
        title = title.strip()
        # content flows back into Claude's own context on a later "read"
        # action — the same reason chat messages get a length cap
        # (_MAX_MESSAGE_LEN in api.py) applies here: bound how much
        # user-controlled text can round-trip into the model's context.
        if len(title) > 200:
            return [types.TextContent(type="text", text="Error: 'title' too long (max 200 characters).")]
        if len(content) > 10000:
            return [types.TextContent(type="text", text="Error: 'content' too long (max 10000 characters).")]

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
        # Confirmed via live testing, not assumed: passing n_results through to
        # ChromaDB unvalidated crashes the tool call outright rather than
        # returning a clean error — a non-int type (e.g. "5" or 3.5) raises
        # TypeError/ValueError deep inside collection.query(), and <= 0 raises
        # "cannot be negative, or zero." A malformed *type* is rejected (the
        # caller should fix its call); an out-of-range *value* is clamped
        # rather than rejected, since the intent (some n) is still clear.
        if not isinstance(n, int) or isinstance(n, bool):
            return [types.TextContent(type="text", text="Error: 'n_results' must be an integer.")]
        n = max(1, min(n, 20))

        stats = get_stats()
        if stats["total_chunks"] == 0:
            return [types.TextContent(
                type="text",
                text="No documents indexed yet. Call index_docs first.",
            )]

        chunks = search(query, n_results=n)
        # ChromaDB's nearest-neighbor search always returns *something* if the
        # collection is non-empty, however weak the actual match — search()'s
        # own docstring names distance < 0.8 (similarity > 0.2) as "relevant"
        # but never enforced it, so a genuinely unrelated query silently got
        # handed the 4 least-bad chunks with no signal they weren't a real
        # match. Now checked against that same documented threshold.
        if not chunks or max(c["score"] for c in chunks) < _SEARCH_RELEVANCE_THRESHOLD:
            available = _knowledge_base_files()
            hint = f" This knowledge base currently covers: {', '.join(available)}." if available else ""
            return [types.TextContent(
                type="text",
                text=f"No sufficiently relevant content found for '{query}'.{hint}",
            )]

        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[{i}] Source: {chunk['source']} (relevance: {chunk['score']})\n{chunk['content']}")

        return [types.TextContent(type="text", text="\n\n---\n\n".join(parts))]

    # ── Tool: list_docs ───────────────────────────────────────────────────
    if name == "list_docs":
        files = _knowledge_base_files()

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


# ── Resources ──────────────────────────────────────────────────────────────
# Read-only, URI-addressable data — a different access pattern from tools:
# clients read a resource by URI instead of calling a function with arguments.

@app.list_resources()
async def list_resources() -> list[types.Resource]:
    """
    Built fresh on every call (not a static list) so it always reflects
    current state — in particular, the note:// entries below are enumerated
    live from whatever notes actually exist right now.
    """
    resources = [
        types.Resource(
            uri=AnyUrl("knowledgebase://files"),
            name="Knowledge base file listing",
            description="Lists all files in the knowledge_base/ folder — same data as the list_docs tool, exposed as a resource.",
            mimeType="text/plain",
        ),
    ]
    for title in note_list():
        resources.append(types.Resource(
            uri=AnyUrl(f"note://{urllib.parse.quote(title, safe='')}"),
            name=title,
            description=f"Saved note: {title}",
            mimeType="text/plain",
        ))
    return resources


@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Called when a client reads a resource by the URI returned above."""

    if uri.scheme == "knowledgebase":
        files = _knowledge_base_files()
        if not files:
            return "No documents found in the knowledge_base/ folder."
        return "\n".join(f"  • {f}" for f in files)

    if uri.scheme == "note":
        title = urllib.parse.unquote(uri.host or "")
        note = note_get(title)
        if not note:
            return f"No note found with title '{title}'."
        return f"Note: {title}\nCreated: {note['created_at']}\n\n{note['content']}"

    raise ValueError(f"Unknown resource URI: {uri}")


# ── Prompts ────────────────────────────────────────────────────────────────
# Reusable request templates a client can invoke by name — distinct from
# tools (actions) and resources (data): a prompt returns pre-built message(s)
# to send to Claude, here one that drives the existing read_doc/search_docs tools.

@app.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="summarize_document",
            description="Generate a request asking Claude to read and summarize a document from knowledge_base/",
            arguments=[
                types.PromptArgument(
                    name="filename",
                    description="Exact filename in knowledge_base/, e.g. 'report.txt'",
                    required=True,
                ),
            ],
        ),
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    if name == "summarize_document":
        filename = (arguments or {}).get("filename", "")
        return types.GetPromptResult(
            description=f"Summarize {filename}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"Please read and summarize the document '{filename}'. "
                            f"Use the read_doc or search_docs tool to retrieve its content, "
                            f"then provide a concise summary of the key points."
                        ),
                    ),
                ),
            ],
        )

    raise ValueError(f"Unknown prompt: '{name}'")


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
