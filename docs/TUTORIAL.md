# MCP Tutorial — Build Your First AI Agent with Tools

A hands-on guide for complete beginners. By the end you will have built
your own MCP server with custom tools and an AI agent that uses them.

No prior AI experience needed. You need Python and an Anthropic API key.

---

## What You Will Build

```
You → agent.py → Claude API → (tool call) → mcp_server.py → result → Claude → You
```

A custom MCP server with tools, and an AI agent that connects Claude to
those tools. When you ask a question, Claude decides which tool to call,
your server runs it, and Claude uses the result to answer you.

---

## Prerequisites

- Python 3.10 or higher
- An Anthropic API key (get one free at console.anthropic.com)
- Basic Python knowledge (functions, if/else, strings)

### Install required packages

```powershell
pip install anthropic[mcp] mcp
```

### Set your API key (one time, permanent)

```powershell
# Windows
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-YOUR_KEY", "User")

# macOS / Linux — add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
```

Close and reopen your terminal after setting it.

---

## Concept Check Before You Code

**What is MCP?**
MCP is a standard protocol that lets AI models call external tools.
Instead of Claude knowing everything, it can call your code to get answers.

**What is an MCP server?**
A Python program that declares tools and runs them when called.
It has no knowledge of Claude — it just defines and executes functions.

**What is a tool?**
A Python function with a name, description, and defined inputs/outputs.
Claude reads the description to decide when to use it.

**Key rule:**
Claude never runs your code directly. It asks "please call this tool
with these inputs." Your code runs it and returns the result.

```
Claude  →  "call get_weather(city=London)"
Your code  →  runs get_weather  →  returns "14°C, Overcast"
Claude  →  "The weather in London is 14°C and overcast."
```

---

## Part 1 — Your First MCP Tool (Hello World)

Create a file called `my_server.py`:

```python
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

app = Server("my-first-server")

@app.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="say_hello",
            description="Says hello to a person by name. Use when the user wants to greet someone.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The person's name"
                    }
                },
                "required": ["name"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "say_hello":
        person = arguments["name"]
        return [types.TextContent(type="text", text=f"Hello, {person}! Welcome to MCP.")]

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

**What this does:**
- Creates an MCP server named `my-first-server`
- Declares one tool: `say_hello`
- When called with a name, returns a greeting
- Runs over stdio transport

---

## Part 2 — Connect Claude to Your Tool

Create a file called `my_agent.py` in the same folder:

```python
import asyncio
import sys
from pathlib import Path
from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Path to your MCP server
SERVER = str(Path(__file__).parent / "my_server.py")
client = AsyncAnthropic()

async def main():
    print("Starting MCP server...")

    server_params = StdioServerParameters(command=sys.executable, args=[SERVER])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools from the server
            result = await session.list_tools()
            tools = [async_mcp_tool(t, session) for t in result.tools]
            print(f"Connected. Tools: {[t.name for t in result.tools]}")
            print("Type your message (quit to exit)\n")

            while True:
                user_input = input("You: ").strip()
                if user_input.lower() in {"quit", "exit"}:
                    break
                if not user_input:
                    continue

                runner = client.beta.messages.tool_runner(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system="You are a helpful assistant. Use tools when relevant.",
                    tools=tools,
                    messages=[{"role": "user", "content": user_input}],
                )

                print("Claude: ", end="", flush=True)
                async for msg in runner:
                    for block in msg.content:
                        if block.type == "tool_use":
                            print(f"\n  [calling {block.name}]", flush=True)
                        elif block.type == "text" and block.text:
                            print(block.text, end="", flush=True)
                print("\n")

asyncio.run(main())
```

**Run it:**
```powershell
python my_agent.py
```

**Try asking:**
```
Say hello to Sarah
Greet my friend John
```

You should see `[calling say_hello]` appear and then Claude's response using the result.

---

## Part 3 — Understand What Just Happened

When you asked "Say hello to Sarah":

1. `my_agent.py` sent your message to Claude with the `say_hello` tool schema
2. Claude read the tool description and decided to call `say_hello`
3. Claude returned: `{"type": "tool_use", "name": "say_hello", "input": {"name": "Sarah"}}`
4. `tool_runner` in the SDK intercepted this and called `my_server.py`
5. `my_server.py` ran `call_tool("say_hello", {"name": "Sarah"})`
6. The server returned: `"Hello, Sarah! Welcome to MCP."`
7. Claude received that result and wrote the final response

**The description is what drives everything.**
Change the description to "Use only when specifically asked to greet someone named Sarah"
and Claude will only call it for Sarah. That is how you control Claude's behaviour.

---

## Part 4 — Add a Second Tool

Add this to `list_tools()` in `my_server.py`:

```python
types.Tool(
    name="add_numbers",
    description="Adds two numbers together. Use for any addition calculation.",
    inputSchema={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "First number"},
            "b": {"type": "number", "description": "Second number"}
        },
        "required": ["a", "b"]
    }
)
```

Add this to `call_tool()`:

```python
if name == "add_numbers":
    result = arguments["a"] + arguments["b"]
    return [types.TextContent(type="text", text=f"{arguments['a']} + {arguments['b']} = {result}")]
```

Restart `my_agent.py` and ask:
```
What is 47 plus 83?
Say hello to Maria and tell me what 10 + 5 is
```

Notice: Claude can call **both tools in one conversation turn** if needed.

---

## Part 5 — Common Errors and Fixes

### Error: `ModuleNotFoundError: No module named 'anthropic'`
```powershell
pip install anthropic[mcp] mcp
```

### Error: `ANTHROPIC_API_KEY is not set`
```powershell
# Windows — set it permanently
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
# Then close and reopen the terminal
```

### Error: `uvicorn not recognised`
uvicorn's executable is not on PATH. Use:
```powershell
python -m uvicorn api:app --reload --port 8000
```

### Error: Tool is never called
Your tool description is too vague. Claude does not know when to use it.
Add more context — *when* and *why* should Claude call this tool?

### Error: `SSL certificate verify failed` (Windows)
When downloading ML models (sentence-transformers). Add this to the top
of your file before any imports:
```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

### Agent answers without calling any tool
The system prompt may not mention tools. Or the tool description is too
weak. Strengthen the description: describe exactly when Claude should use it.

---

## Part 6 — Exercises

Try these in order. Each one builds on the previous.

**Exercise 1 — Reverse a string tool**
Build a tool called `reverse_text` that takes a string and returns it reversed.
Test: `"Reverse the word hello"`

**Exercise 2 — Current time tool**
Build a `get_current_time` tool with no parameters that returns the
current time using Python's `datetime.now()`.
Test: `"What time is it?"`

**Exercise 3 — Temperature converter tool**
Build a `convert_temperature` tool that converts between Celsius and
Fahrenheit. Parameters: `value` (number) and `unit` ("celsius" or "fahrenheit").
Test: `"What is 100 degrees Fahrenheit in Celsius?"`

**Exercise 4 — Read a file tool**
Build a `read_file` tool that reads a `.txt` file from a `files/` folder.
Parameters: `filename`. Return the file contents.
Test: create `files/note.txt` and ask `"What is in my note.txt?"`

**Exercise 5 — Count words tool**
Build a `count_words` tool that takes a `text` parameter and returns
the word count.
Test: `"How many words are in 'The quick brown fox jumps over the lazy dog'?"`

**Exercise 6 — Build your own idea**
Think of something useful in your daily work. A tool that queries your
own data, calls an API you use, or automates something repetitive.
Build it as an MCP tool.

---

## Key Rules to Remember

**1. Every tool needs a clear description**
The description is how Claude decides when to use the tool. Write it for Claude, not for humans. Be specific about when to call it.

**2. Tool names should be verbs**
`get_weather`, `calculate`, `read_file`, `send_email` — not `weather`, `math`, `file`.

**3. Return TextContent, not raw strings**
```python
# Wrong
return "result"

# Right
return [types.TextContent(type="text", text="result")]
```

**4. Always validate inputs**
```python
if not arguments.get("filename"):
    return [types.TextContent(type="text", text="Error: filename is required.")]
```

**5. The server knows nothing about Claude**
`mcp_server.py` has no imports from anthropic. It only uses `mcp`.
The two sides are completely independent.

---

## What to Build Next

Once you are comfortable with the basics:

1. **Add a web interface** — use FastAPI to serve a browser chat UI
2. **Add persistence** — use SQLite to save notes and conversation history
3. **Add document search** — use ChromaDB to search your own documents with AI
4. **Connect to real APIs** — weather, calendar, email, database
5. **Expose over HTTP** — make your MCP server accessible from any agent on any machine

The pattern is always the same. Two functions. One server. Infinite possibilities.
