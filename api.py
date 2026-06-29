#!/usr/bin/env python3
"""
FastAPI Web Server — MCP Learning Project

Replaces the CLI (agent.py) with a proper web API + streaming chat UI.

Key FastAPI concepts used here:
  - lifespan: startup/shutdown hooks (keep MCP server alive)
  - Pydantic models: request body validation
  - StreamingResponse: Server-Sent Events for real-time streaming
  - app.state: share objects (tools, client) across all requests

Run:
  uvicorn api:app --reload
  Then open http://localhost:8000
"""
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from database import init_db, session_get, session_save, session_list, session_delete

SERVER_SCRIPT = str(Path(__file__).parent / "mcp_server.py")


# ── Lifespan: runs on startup and shutdown ───────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler.
    Everything before `yield` runs at startup.
    Everything after `yield` runs at shutdown.

    We start the MCP server here so it stays alive for ALL requests —
    not started fresh on every API call.
    """
    server_params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()

            tools_response = await mcp_session.list_tools()
            tools = [async_mcp_tool(t, mcp_session) for t in tools_response.tools]
            tool_names = [t.name for t in tools_response.tools]

            # Store on app.state so all route handlers can access them
            app.state.tools = tools
            app.state.tool_names = tool_names

            # Windows: SSLKEYLOGFILE may point to a monitoring driver that Python
            # can't write to. Pop it before creating any SSL context.
            import os as _os
            import httpx as _httpx
            _os.environ.pop("SSLKEYLOGFILE", None)
            # Pass a custom httpx client with verify=False to avoid the Windows
            # corporate certificate chain issue when calling the Anthropic API.
            app.state.client = AsyncAnthropic(
                http_client=_httpx.AsyncClient(verify=False)
            )
            from rag import index_all, get_stats

            init_db()  # ensure tables exist

            # Auto-index docs on startup so RAG works immediately
            indexed = index_all()
            stats = get_stats()
            if indexed:
                print(f"Indexed {len(indexed)} doc(s) -> {stats['total_chunks']} chunks in ChromaDB")

            print(f"MCP server ready. Tools: {tool_names}")
            yield
            # MCP server subprocess is cleaned up automatically here


# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="MCP Learning Agent", lifespan=lifespan)


# ── Request / response models (Pydantic) ─────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""   # empty = start a new session


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the chat UI."""
    html = Path(__file__).parent / "templates" / "chat.html"
    return HTMLResponse(html.read_text(encoding="utf-8"))


@app.get("/tools")
async def list_tools():
    """Return the list of available MCP tools."""
    return {"tools": app.state.tool_names}


@app.get("/sessions")
async def list_sessions():
    """Return all session IDs and last updated time."""
    return session_list()


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    if not session_delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"cleared": session_id}


SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": (
            "You are a helpful assistant with access to tools.\n\n"
            "For any question about a specific topic, subject, person, or project, "
            "ALWAYS call search_docs first — the user's documents may contain relevant information. "
            "Base your answer on those results if relevant.\n\n"
            "Only skip search_docs for clearly general questions (math, current time, weather, etc.) "
            "that could not possibly be in a document.\n\n"
            "If search_docs returns nothing useful, answer from general knowledge. "
            "If documents are not yet indexed, call index_docs first."
        ),
        "cache_control": {"type": "ephemeral"},
    }
]

HISTORY_LIMIT = 10  # keep last N messages to cap context size


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Non-streaming chat endpoint.
    Waits for Claude to finish before returning the full response.
    Good for testing; use /stream for the real UI.
    """
    session_id = req.session_id or str(uuid.uuid4())
    history = session_get(session_id)
    history.append({"role": "user", "content": req.message})

    runner = app.state.client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=app.state.tools,
        messages=history[-HISTORY_LIMIT:],
    )

    response_text = ""
    tools_used = []

    async for msg in runner:
        for block in msg.content:
            if block.type == "tool_use":
                tools_used.append(block.name)
            elif block.type == "text" and block.text:
                response_text += block.text

    history.append({"role": "assistant", "content": response_text})
    session_save(session_id, history)

    return {
        "session_id": session_id,
        "response": response_text,
        "tools_used": tools_used,
    }


@app.post("/stream")
async def stream_chat(req: ChatRequest):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    The frontend receives chunks in real time as Claude generates them.

    SSE format:  data: <json>\\n\\n
    Event types:
      { type: "tool",  name: "get_weather" }   — tool being called
      { type: "text",  content: "..." }         — text chunk from Claude
      { type: "done",  session_id: "..." }      — response complete
      { type: "error", message: "..." }         — something went wrong
    """
    session_id = req.session_id or str(uuid.uuid4())
    history = session_get(session_id)
    history.append({"role": "user", "content": req.message})

    def _safe_window(hist: list, limit: int) -> list:
        """Slice history to limit while never splitting a tool_use/tool_result pair."""
        window = hist[-limit:]
        # Drop leading tool_result turns that have no matching tool_use in window
        while window and window[0].get("role") == "user":
            content = window[0].get("content", "")
            # A user turn whose content is a list starting with tool_result is orphaned
            if isinstance(content, list) and content and isinstance(content[0], dict) \
                    and content[0].get("type") == "tool_result":
                window = window[1:]
            else:
                break
        return window

    async def generate():
        response_text = ""
        try:
            runner = app.state.client.beta.messages.tool_runner(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=app.state.tools,
                messages=_safe_window(history, HISTORY_LIMIT),
            )

            # Accumulate usage across all runner turns (one turn per tool round-trip)
            total_input = total_cache_write = total_cache_read = total_output = 0
            has_usage = False
            async for msg in runner:
                if hasattr(msg, "usage") and msg.usage:
                    u = msg.usage
                    total_input += u.input_tokens
                    total_cache_write += getattr(u, "cache_creation_input_tokens", 0)
                    total_cache_read += getattr(u, "cache_read_input_tokens", 0)
                    total_output += u.output_tokens
                    has_usage = True
                for block in msg.content:
                    if block.type == "tool_use":
                        yield f"data: {json.dumps({'type': 'tool', 'name': block.name})}\n\n"
                    elif block.type == "text" and block.text:
                        response_text += block.text
                        yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"

            # Only save a non-empty assistant turn to avoid corrupting history
            if response_text:
                history.append({"role": "assistant", "content": response_text})
                session_save(session_id, history)

            done_data = {"type": "done", "session_id": session_id}
            if has_usage:
                done_data["usage"] = {
                    "input": total_input,
                    "cache_write": total_cache_write,
                    "cache_read": total_cache_read,
                    "output": total_output,
                }
            yield f"data: {json.dumps(done_data)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
