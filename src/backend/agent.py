#!/usr/bin/env python3
"""
AI Agent — Learning Project

Connects to mcp_server.py and uses Claude to answer questions with tools.

Architecture:
  You ──► agent.py ──► Claude API ──► (tool call) ──► mcp_server.py
                                      (tool result) ◄──

SETUP:
  pip install anthropic[mcp] mcp
  set ANTHROPIC_API_KEY=your-key-here   (Windows)
  export ANTHROPIC_API_KEY=your-key     (macOS / Linux)

RUN (from the project root):
  python src/backend/agent.py
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# mcp_server.py lives in the same folder as this file
SERVER_SCRIPT = str(Path(__file__).parent / "mcp_server.py")

# AsyncAnthropic reads ANTHROPIC_API_KEY from the environment automatically
client = AsyncAnthropic()


def check_api_key() -> None:
    """Fail fast with a clear message if the API key is missing."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print()
        print("  Windows PowerShell : $env:ANTHROPIC_API_KEY='sk-ant-...'")
        print("  Windows CMD        : set ANTHROPIC_API_KEY=sk-ant-...")
        print("  macOS / Linux      : export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)


async def main() -> None:
    check_api_key()

    print()
    print("═" * 55)
    print("  MCP Learning Agent")
    print("  Claude + Custom MCP Tools")
    print("═" * 55)

    # StdioServerParameters tells the MCP client how to launch the server.
    # It spawns mcp_server.py as a child process and pipes stdin/stdout.
    server_params = StdioServerParameters(
        command=sys.executable,   # same Python interpreter running this file
        args=[SERVER_SCRIPT],
    )

    print("\nStarting MCP server...", flush=True)

    # stdio_client launches the server subprocess and gives us read/write streams
    async with stdio_client(server_params) as (read, write):

        # ClientSession handles the MCP JSON-RPC protocol layer
        async with ClientSession(read, write) as mcp_session:

            # initialize() performs the MCP handshake (capability negotiation)
            await mcp_session.initialize()

            # Ask the server: "what tools do you have?"
            tools_response = await mcp_session.list_tools()

            # async_mcp_tool wraps each MCP tool so the Anthropic tool runner
            # can execute it asynchronously when Claude requests it
            tools = [async_mcp_tool(t, mcp_session) for t in tools_response.tools]
            tool_names = [t.name for t in tools_response.tools]

            print(f"Connected! Tools: {', '.join(tool_names)}")
            print("\nAsk me anything. Claude will use tools when relevant.")
            print("Type 'quit' to exit.")
            print("─" * 55)

            # history stores the full conversation so Claude has context
            # across multiple turns
            history: list[dict] = []

            while True:
                print()
                try:
                    user_text = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye!")
                    break

                if not user_text:
                    continue
                if user_text.lower() in {"quit", "exit", "q", "bye"}:
                    print("Goodbye!")
                    break

                # Append user message to conversation history
                history.append({"role": "user", "content": user_text})

                print("\nClaude:", flush=True)

                # tool_runner handles the full agentic loop automatically:
                #   1. Send history to Claude
                #   2. If Claude returns tool_use blocks → execute them via MCP
                #   3. Feed tool results back to Claude
                #   4. Repeat until Claude gives a final text-only response
                #
                # tool_runner() is a synchronous call that returns an async iterable.
                # Each yielded message = one round-trip to the Claude API.
                runner = client.beta.messages.tool_runner(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    system=(
                        "You are a helpful assistant with access to tools. "
                        "IMPORTANT: When answering any question, ALWAYS call search_docs first "
                        "to check if relevant information exists in the user's documents. "
                        "Base your answer on the search results if they are relevant. "
                        "Only fall back to general knowledge if search_docs returns nothing relevant. "
                        "If documents are not yet indexed, call index_docs first. "
                        "Be concise."
                    ),
                    tools=tools,
                    messages=history,
                )

                assistant_response = ""

                # Iterate through messages from the runner.
                # If Claude uses tools, you get ≥2 messages:
                #   msg 1: Claude's tool call request (tool_use block)
                #   msg 2: Claude's final answer (text block, after tool results)
                async for msg in runner:
                    for block in msg.content:
                        if block.type == "tool_use":
                            # Show tool invocations so you can see what's happening
                            print(f"  [→ {block.name}]", flush=True)

                        elif block.type == "text" and block.text:
                            print(block.text, end="", flush=True)
                            assistant_response += block.text

                print()  # newline after the response

                # Store the assistant's final text in history for future turns.
                # The intermediate tool calls are handled internally by the runner.
                if assistant_response:
                    history.append({"role": "assistant", "content": assistant_response})


if __name__ == "__main__":
    asyncio.run(main())
