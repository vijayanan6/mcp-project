# MCP Learning Project Notes

## What I Built
- A custom MCP server in Python with 6 tools
- An AI agent using Claude Sonnet that connects to the server
- The agent answers questions by calling tools automatically

## Tools in This Project
| Tool | What it does |
|------|-------------|
| get_current_datetime | Returns current date and time |
| calculate | Evaluates math expressions safely |
| get_weather | Mock weather data for cities |
| manage_notes | In-memory CRUD for notes |
| list_docs | Lists files in the docs/ folder |
| read_doc | Reads a document from docs/ folder |

## Key Learnings
1. MCP uses JSON-RPC 2.0 under the hood
2. Claude never runs code directly — it requests tool calls
3. Tool descriptions are critical — they tell Claude WHEN to use each tool
4. stdio transport = local subprocess; HTTP/SSE = network accessible
5. The tool_runner in the Anthropic SDK handles the full loop automatically

## Tech Stack
- Python 3.12
- anthropic[mcp] — Anthropic SDK with MCP integration
- mcp — Python MCP reference implementation
- Claude Sonnet 4.6 — the AI model

## Next Steps to Explore
- Add a real weather API (OpenWeatherMap)
- Connect to a database (SQLite tool)
- Expose the server via HTTP/SSE for external access
- Add to Claude Desktop app
