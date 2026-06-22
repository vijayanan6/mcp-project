# MCP Learning Project

A hands-on project to learn **Model Context Protocol (MCP)** by building a custom MCP server with tools and an AI agent that uses them.

---

## What is MCP?

**Model Context Protocol (MCP)** is an open standard that lets AI models (like Claude) call external tools and services in a structured, language-agnostic way. Instead of hard-coding tool logic inside your AI app, you define tools in a separate **MCP server** — and any MCP-compatible AI agent can discover and use them.

Think of it like a USB standard: any device that speaks USB works with any port. MCP is that standard for AI tools.

---

## Project Structure

```
MCP Project/
├── mcp_server.py    — The MCP server (defines and runs your tools)
├── agent.py         — The AI agent (connects Claude to your tools)
└── requirements.txt — Python dependencies
```

---

## Architecture

```
You
 │  type a question
 ▼
agent.py
 │  1. Sends your message + tool schemas → Claude API
 ▼
Claude (claude-sonnet-4-6)
 │  2. Decides which tool to call, returns tool_use block
 ▼
tool_runner  (inside agent.py)
 │  3. Intercepts the tool call, forwards to MCP server
 ▼
mcp_server.py  (subprocess, stdio transport)
 │  4. Executes the tool function, returns result
 ▼
tool_runner
 │  5. Feeds result back to Claude
 ▼
Claude
 │  6. Writes final answer using the tool result
 ▼
You see the answer
```

**Key insight:** Claude never runs your code directly. It returns a JSON description of what tool to call with what inputs. Your `agent.py` is the one that actually executes the tool via the MCP server and feeds the results back to Claude.

---

## Tools

| Tool | Description | Parameters |
|---|---|---|
| `get_current_datetime` | Returns current date and time | None |
| `calculate` | Safely evaluates a math expression | `expression` (string) |
| `get_weather` | Mock weather data for a city | `city` (string) |
| `manage_notes` | In-memory CRUD for text notes | `action`, `title`, `content` |

### Tool descriptions matter
The `description` field in each tool definition is what Claude reads to decide **when** to use a tool. A good description says *when* to call it, not just *what* it does.

```python
# ❌ Weak description — Claude might not know when to use this
types.Tool(name="calculate", description="Does math")

# ✅ Strong description — Claude knows exactly when to use it
types.Tool(
    name="calculate",
    description="Safely evaluates a mathematical expression. "
                "Use this for any arithmetic, algebra, or calculations. "
                "Supports: +, -, *, /, **, sqrt(), sin(), cos(), pi, e"
)
```

---

## Setup

### Prerequisites
- Python 3.10+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Install dependencies
```bash
pip install anthropic[mcp] mcp
```

### Set your API key (one-time, permanent)
```powershell
# Windows PowerShell — saves to user environment variables
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```
```bash
# macOS / Linux — add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Run
```bash
python agent.py
```
`agent.py` automatically starts `mcp_server.py` as a subprocess — you only ever run one file.

---

## Example Session

```
═══════════════════════════════════════════════════════
  MCP Learning Agent
  Claude + Custom MCP Tools
═══════════════════════════════════════════════════════

Starting MCP server...
Connected! Tools: get_current_datetime, calculate, get_weather, manage_notes
Ask me anything. Claude will use tools when relevant.

You: What day is it today?
  [→ get_current_datetime]
Claude: Today is Monday, June 22, 2026 at 03:45 PM.

You: What is sqrt(256) + 2 to the power of 8?
  [→ calculate]
  [→ calculate]
Claude: sqrt(256) = 16, and 2**8 = 256. So the answer is 16 + 256 = 272.

You: Weather in Tokyo?
  [→ get_weather]
Claude: In Tokyo it's currently 27°C / 80°F, humid conditions with 82% humidity.

You: Save a note called "ideas" with content "build more MCP tools"
  [→ manage_notes]
Claude: Done! Note "ideas" has been saved.

You: List my notes
  [→ manage_notes]
Claude: You have 1 note: "ideas"
```

---

## How to Add a New Tool

**Step 1 — Declare the tool in `list_tools()` inside `mcp_server.py`:**
```python
types.Tool(
    name="get_joke",
    description="Returns a random programming joke. Use when the user wants something funny.",
    inputSchema={
        "type": "object",
        "properties": {},   # no parameters
    },
),
```

**Step 2 — Handle it in `call_tool()` inside `mcp_server.py`:**
```python
if name == "get_joke":
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs.",
        "A SQL query walks into a bar, walks up to two tables and asks... can I join you?",
    ]
    import random
    return [types.TextContent(type="text", text=random.choice(jokes))]
```

That's it. Restart `agent.py` and Claude will automatically discover and use the new tool.

---

## Transport: stdio vs HTTP/SSE

Currently this project uses **stdio transport** — the server runs as a local subprocess. This is great for local development.

### stdio (current — local only)
```
agent.py  ──stdin/stdout──►  mcp_server.py (subprocess)
```

### HTTP/SSE (for external access)
Run the server as a web service. External agents connect via URL.
```
any agent  ──HTTP──►  mcp_server running on port 8000
```

### Ways to expose your server externally

| Method | Best for |
|---|---|
| **Claude Desktop config** | Use your tools inside the Claude desktop app |
| **HTTP/SSE server** | Let agents on other machines connect via URL |
| **Anthropic `mcp_servers` API param** | Connect directly from any Anthropic API call |

---

## Key Concepts

| Concept | Where | Purpose |
|---|---|---|
| `Server("name")` | `mcp_server.py` | Creates the MCP server instance |
| `@app.list_tools()` | `mcp_server.py` | Declares available tools (name + description + schema) |
| `@app.call_tool()` | `mcp_server.py` | Executes a tool and returns `TextContent` |
| `stdio_server()` | `mcp_server.py` | stdio transport — communicates via stdin/stdout |
| `StdioServerParameters` | `agent.py` | Tells the client how to launch the server subprocess |
| `ClientSession` | `agent.py` | MCP protocol session handler |
| `async_mcp_tool()` | `agent.py` | Wraps MCP tools for use with the Anthropic SDK |
| `tool_runner` | `agent.py` | Automates the full tool-call loop with Claude |

---

## How the MCP Protocol Works (under the hood)

`agent.py` and `mcp_server.py` communicate using **JSON-RPC 2.0** messages over stdin/stdout. You never see these messages directly, but here's what they look like:

**Agent asks: "what tools do you have?"**
```json
{ "jsonrpc": "2.0", "method": "tools/list", "id": 1 }
```

**Server replies:**
```json
{ "result": { "tools": [ { "name": "calculate", "description": "...", "inputSchema": {...} } ] } }
```

**Agent asks: "run this tool"**
```json
{ "method": "tools/call", "params": { "name": "calculate", "arguments": { "expression": "sqrt(144)" } } }
```

**Server replies:**
```json
{ "result": { "content": [ { "type": "text", "text": "sqrt(144) = 12.0" } ] } }
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic[mcp]` | Anthropic SDK + MCP integration helpers |
| `mcp` | MCP server/client library (Python reference implementation) |

---

## Next Steps

- **Add real tools** — replace mock weather with a real API (OpenWeatherMap, etc.)
- **Add a database tool** — connect to SQLite and let Claude query it
- **Expose via HTTP/SSE** — make your server accessible to external agents
- **Add to Claude Desktop** — use your tools directly in the Claude app
- **Add authentication** — secure your HTTP server with API keys
