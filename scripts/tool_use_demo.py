"""
Tool Use Fundamentals — hands-on demo (LEARNING_PLAN.md: Tool Use Fundamentals)

Five short, labeled demos against the real Anthropic API, using this project's
own get_weather and manage_notes tool schemas (copied from mcp_server.py).
No MCP server or api.py involved — just the raw Anthropic SDK, so the
tool_choice / streaming / manual-loop mechanics are visible without
tool_runner's abstraction in the way.

Makes ~6 short calls to claude-sonnet-4-6 (small max_tokens each) — a few
cents of API credit total.

Run (from the project root): python scripts/tool_use_demo.py
"""
import json
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

import httpx
os.environ.pop("SSLKEYLOGFILE", None)  # Windows corporate cert/monitoring driver fix — see CLAUDE.md
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend"))
from database import init_db, note_save, note_get

client = Anthropic(http_client=httpx.Client(verify=False))
MODEL = "claude-sonnet-4-6"

# Real tool schemas, copied from mcp_server.py's list_tools()
GET_WEATHER_TOOL = {
    "name": "get_weather",
    "description": (
        "Returns current weather conditions for a city. "
        "NOTE: This uses demo/mock data, not a real weather API. "
        "Use when the user asks about weather in a specific place."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'London', 'Tokyo', 'New York'"}
        },
        "required": ["city"],
    },
}

MANAGE_NOTES_TOOL = {
    "name": "manage_notes",
    "description": (
        "Save, read, list, or delete personal notes stored in SQLite. "
        "Use 'save' to store a note, 'read' to retrieve one by title, "
        "'list' to see all titles, 'delete' to remove one."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["save", "read", "list", "delete"]},
            "title": {"type": "string", "description": "Note title / key"},
            "content": {"type": "string", "description": "Note body (for save)"},
        },
        "required": ["action"],
    },
}

# Same mock data shape as mcp_server.py's get_weather handler (trimmed)
WEATHER_DB = {"london": (14, "Overcast"), "tokyo": (27, "Humid"), "seattle": (16, "Rainy")}


def run_get_weather(city: str) -> str:
    temp_c, condition = WEATHER_DB.get(city.lower(), (20, "Clear"))
    return f"{city}: {round(temp_c * 9 / 5 + 32)}°F, {condition}"


def run_manage_notes(action: str, title: str = "", content: str = "") -> str:
    if action == "save":
        note_save(title, content)
        return f"Note '{title}' saved."
    if action == "read":
        note = note_get(title)
        return note["content"] if note else f"No note found: {title}"
    return f"Unsupported action in this demo: {action}"


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


# ── 1. tool_choice: auto (baseline) — Claude decides ─────────────────────
section("1. tool_choice: auto — ambiguous prompt, Claude's call")
resp = client.messages.create(
    model=MODEL, max_tokens=300, tools=[GET_WEATHER_TOOL],
    tool_choice={"type": "auto"},
    messages=[{"role": "user", "content": "Tell me an interesting fact about deserts."}],
)
print("stop_reason:", resp.stop_reason)
for block in resp.content:
    print(" ", block.type, "->", block.input if block.type == "tool_use" else block.text)


# ── 2. tool_choice: forced tool — same ambiguous prompt ──────────────────
section("2. tool_choice: forced get_weather — SAME ambiguous prompt")
resp = client.messages.create(
    model=MODEL, max_tokens=300, tools=[GET_WEATHER_TOOL],
    tool_choice={"type": "tool", "name": "get_weather"},
    messages=[{"role": "user", "content": "Tell me an interesting fact about deserts."}],
)
print("stop_reason:", resp.stop_reason)
for block in resp.content:
    print(" ", block.type, "->", block.input if block.type == "tool_use" else block.text)
print("Notice: forced tool_choice ignores what the prompt actually asked for.")


# ── 3. disable_parallel_tool_use ──────────────────────────────────────────
section("3. disable_parallel_tool_use — a request that invites two tool calls")
tools_both = [GET_WEATHER_TOOL, MANAGE_NOTES_TOOL]
prompt = "What's the weather in Tokyo, and also list my saved notes?"

resp_parallel = client.messages.create(
    model=MODEL, max_tokens=400, tools=tools_both,
    tool_choice={"type": "any"},
    messages=[{"role": "user", "content": prompt}],
)
calls = [b.name for b in resp_parallel.content if b.type == "tool_use"]
print("tool_choice=any                -> tool calls in one turn:", calls)

resp_serial = client.messages.create(
    model=MODEL, max_tokens=400, tools=tools_both,
    tool_choice={"type": "any", "disable_parallel_tool_use": True},
    messages=[{"role": "user", "content": prompt}],
)
calls2 = [b.name for b in resp_serial.content if b.type == "tool_use"]
print("disable_parallel_tool_use=True -> tool calls in one turn:", calls2)


# ── 4. Streaming — watch input_json_delta arrive in pieces ──────────────
section("4. Streaming a forced tool call — raw input_json_delta fragments")
with client.messages.stream(
    model=MODEL, max_tokens=300, tools=[GET_WEATHER_TOOL],
    tool_choice={"type": "tool", "name": "get_weather"},
    messages=[{"role": "user", "content": "weather check please, Seattle"}],
) as stream:
    buffer = ""
    for event in stream:
        if event.type == "content_block_delta" and event.delta.type == "input_json_delta":
            buffer += event.delta.partial_json
            print(f"  fragment received so far: {buffer!r}")
    parsed = json.loads(buffer)
    print("Final parsed input:", parsed)
    print("Executed for real:", run_get_weather(parsed["city"]))


# ── 5. Manual multi-turn loop — no tool_runner, real SQLite note ────────
section("5. Manual tool loop — save a note, then read it back (2 round trips)")
init_db()
messages = [{
    "role": "user",
    "content": (
        "Save a note titled 'tool-use-demo' with content 'written by the manual loop demo', "
        "then read it back to confirm it saved correctly."
    ),
}]

turn = 0
while True:
    turn += 1
    resp = client.messages.create(
        model=MODEL, max_tokens=500, tools=[MANAGE_NOTES_TOOL],
        messages=messages,
    )
    print(f"  turn {turn}: stop_reason={resp.stop_reason}")

    if resp.stop_reason != "tool_use":
        final_text = next((b.text for b in resp.content if b.type == "text"), "")
        print("  Claude's final answer:", final_text)
        break

    messages.append({"role": "assistant", "content": resp.content})

    tool_results = []
    for block in resp.content:
        if block.type == "tool_use":
            print(f"    -> executing {block.name}({block.input})")
            result = run_manage_notes(**block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
    messages.append({"role": "user", "content": tool_results})

print("\nDone. Run inspect_db.py to see the 'tool-use-demo' note persisted in SQLite.")
