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
            app.state.client = AsyncAnthropic()

            init_db()  # ensure tables exist
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
        max_tokens=2048,
        system=(
                        "You are a helpful assistant with access to tools. "
                        "IMPORTANT: When answering any question, ALWAYS call search_docs first "
                        "to check if relevant information exists in the user's documents. "
                        "Base your answer on the search results if they are relevant. "
                        "Only fall back to general knowledge if search_docs returns nothing relevant. "
                        "If documents are not yet indexed, call index_docs first."
                    ),
        tools=app.state.tools,
        messages=history,
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

    async def generate():
        response_text = ""
        try:
            runner = app.state.client.beta.messages.tool_runner(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=(
                        "You are a helpful assistant with access to tools. "
                        "IMPORTANT: When answering any question, ALWAYS call search_docs first "
                        "to check if relevant information exists in the user's documents. "
                        "Base your answer on the search results if they are relevant. "
                        "Only fall back to general knowledge if search_docs returns nothing relevant. "
                        "If documents are not yet indexed, call index_docs first."
                    ),
                tools=app.state.tools,
                messages=history,
            )

            async for msg in runner:
                for block in msg.content:
                    if block.type == "tool_use":
                        yield f"data: {json.dumps({'type': 'tool', 'name': block.name})}\n\n"
                    elif block.type == "text" and block.text:
                        response_text += block.text
                        yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"

            history.append({"role": "assistant", "content": response_text})
            session_save(session_id, history)   # ← persist to SQLite
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
