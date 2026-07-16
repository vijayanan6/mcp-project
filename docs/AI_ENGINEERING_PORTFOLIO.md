# Applied AI Engineer — LLM Systems, MCP & RAG | Vijay Anantaneni

> Built a production-grade AI assistant from scratch — no tutorials, no boilerplate.
> Every concept below was learned by implementing it in running code.

---

## Highlights

**GitHub:** [github.com/vijayanan6/mcp-project](https://github.com/vijayanan6/mcp-project)

A full-stack AI application built entirely from first principles — no LangChain, no scaffolding template, no copied boilerplate. Every capability below was implemented, tested against real API calls and real data, and in several cases debugged down to a root cause most engineers would have missed.

- **A real, working AI product** — semantic document search (RAG), custom MCP tools, live model routing, multimodal (image/PDF) input, and a full LLM cost-observability dashboard with mobile push alerts, all running together as one system.
- **A recurring engineering discipline, not a one-off**: across at least six separate features, the same pattern shows up — verify the actual behavior of a dependency (an SDK, an API response, a validator) against a live test before trusting an assumption, because self-consistent code can still be systematically wrong. This caught real bugs in cost tracking, citation parsing, MCP resource URIs, and model-routing compatibility — see sections 1–6 below.
- **Automated quality gates, not manual spot-checks**: a 12/12 (100%) passing eval suite that scores tool selection and model routing on every prompt change, run as a gate before shipping.
- **Production-grade cost and security discipline**: token-level cost tracking with credit/burn-rate forecasting and Discord mobile alerts; secret-scanning pre-commit hooks; SSH-signed, GitHub-verified commits; dependency vulnerability audits with root-cause tracing (not blanket patching).
- **Continuously extended, not a frozen demo** — most recently: ephemeral multimodal chat attachments with PDF citations, the full MCP protocol surface (tools *and* resources *and* prompts, not just tools), and a full code-review backlog (10 real findings, tracked as GitHub issues) closed end-to-end with a verified fix and a live regression check for every single one.
- **Directs multi-agent workflows, not just single-turn prompts** — designs and runs agent pipelines with deliberate structural constraints (e.g. a code-review "reviewer" agent given read-only tools so it's architecturally incapable of silently fixing instead of critiquing), not just sequential chat turns. See section 17.

---

## What I Built

A full-stack AI application where Claude (Anthropic's LLM) uses custom tools to answer questions, search documents semantically, and maintain persistent multi-turn conversations across browser sessions.

```
Browser ──HTTP/SSE──► FastAPI (api.py) ──stdio/JSON-RPC──► MCP Server (mcp_server.py)
                           │                                        │
                           └──► Anthropic API (Claude)      SQLite + ChromaDB
```

**Portfolio:** [github.com/vijayanan6/mcp-project/blob/main/docs/AI_ENGINEERING_PORTFOLIO.md](https://github.com/vijayanan6/mcp-project/blob/main/docs/AI_ENGINEERING_PORTFOLIO.md)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Claude Sonnet 4.6 / Haiku 4.5 (Anthropic) |
| AI Protocol | MCP (Model Context Protocol) |
| Native Tools | web_search (server-side), text editor (client-side, `BetaAsyncBuiltinFunctionTool`) |
| Alerting | Discord webhooks — 4 alert types, traffic-triggered (no scheduler dependency) |
| Web Framework | FastAPI + Uvicorn |
| Vector Database | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Relational Database | SQLite |
| PDF Processing | pypdf, pymupdf, Tesseract OCR |
| Language | Python 3.12 |
| Version Control | Git + GitHub |
| UI Testing | Playwright MCP (browser automation via Claude Code) |

---

## Skills & Concepts — Implemented, Not Just Studied

*Ordered by engineering-discipline signal, not build chronology — the strongest debugging/verification work comes first. Full phase-by-phase build history is in [LEARNING_JOURNEY.md](LEARNING_JOURNEY.md).*

### 1. MCP — Model Context Protocol

Anthropic's open standard for connecting LLMs to external tools. Built a custom MCP server exposing 8 tools over stdio/JSON-RPC — not using a pre-built connector, implementing the protocol directly.

**Tools built:** `get_current_datetime`, `calculate`, `get_weather`, `manage_notes`, `list_docs`, `read_doc`, `index_docs`, `search_docs`

```python
@app.list_tools()
async def list_tools():
    return [types.Tool(name="search_docs", description="...", inputSchema={...})]

@app.call_tool()
async def call_tool(name, arguments):
    return [types.TextContent(type="text", text=result)]
```

---

### 2. RAG — Retrieval Augmented Generation

Built the full pipeline from scratch: chunk → embed → store → search → retrieve. No LangChain wrapper.

```
User question → embed → ChromaDB similarity search → top 4 chunks → Claude → answer
```

- Chunking with overlap (500 char chunks, 100 char overlap at natural boundaries)
- Local embedding model: `all-MiniLM-L6-v2` via `sentence-transformers`
- Auto-indexes on server startup; re-index by chat command
- Supports `.txt`, `.md`, `.csv`, scanned PDFs (via OCR)
- Verified — not assumed — the actual ranking mechanism: confirmed the installed ChromaDB defaults to cosine distance for this embedding function, then proved it empirically with the project's own model — two paraphrased sentences sharing zero words scored 0.556 similarity vs. 0.09 for an unrelated pair

---

### 3. Anthropic-Native Tools — Server-Side and Client-Side, Beyond MCP

Extended the tool surface beyond MCP with two Anthropic-native tools that don't run through `mcp_server.py` at all: `web_search` (server-side — Anthropic executes it) and a text editor tool (client-side — this process executes it), each requiring a different integration pattern and each surfacing a real production bug that got found and fixed with live testing, not assumption.

```python
# Client-side builtin tool: implement the SDK's runnable-tool interface
class ProjectNotesEditorTool(BetaAsyncBuiltinFunctionTool):
    def to_dict(self):
        return {"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}

    async def call(self, input: dict) -> str:
        path = self._check_path(input.get("path", ""))  # hard-fails outside one allowed file
        ...
```

**Built and verified, with real browser tests (Playwright MCP) and direct API inspection:**
- **Server-side vs. client-side tool architecture** — `web_search` needed only a dict declaration (Anthropic resolves it entirely); the text editor tool required implementing `BetaAsyncBuiltinFunctionTool` (`to_dict()` + `call()`) because Claude only *requests* the edit, this process has to execute it
- **Path-confined tool execution** — the text editor tool is hard-restricted to exactly one file (`knowledge_base/project_notes.md`), not the whole `knowledge_base/` folder; every path is resolved and compared for exact equality before any file operation runs, verified against both `../` traversal and same-folder sibling-file escape attempts
- **Found and fixed a silent cost-tracking gap** — server-side tool calls arrive as `server_tool_use` content blocks, a different type than the `tool_use` blocks the cost-tracking code checked for; `web_search` calls were billed correctly but invisible in the "Cost by Tool" dashboard view until this was found by directly querying `/usage/data`, not by trusting that the feature "looked like it worked"
- **Found and fixed a real production bug via model-routing interaction** — `web_search`'s default configuration requires programmatic tool calling, which this project's Haiku tier (used by the cost-based model router) doesn't support; the Anthropic API validates *every declared tool* against model capability at request time, so unrelated Haiku-routed messages started 400ing purely from `web_search` being present in the tool list — fixed with `allowed_callers: ["direct"]`, caught by re-testing the exact failing request end-to-end after the fix, not just reasoning that it should work

**Why this matters:** shared infrastructure (a tool list, a model router) has failure modes that only appear at the *intersection* of two features that each work fine independently. Finding this bug required treating a live end-to-end test as the source of truth over the code's apparent correctness — the same discipline as the `.env` UTF-8 BOM bug (see the Claude Code section below), applied to a different layer of the stack.

---

### 4. Multimodal Chat Input — Ephemeral Image/PDF Attachments with Citations

Extended the chat beyond text-only input: users can attach one image or PDF per message, read directly via Claude's native vision/document understanding — no OCR pipeline, no indexing step, for ad-hoc content brought into a live conversation rather than the curated `knowledge_base/` corpus.

```python
def _build_api_messages(windowed: list, attachment, current_text: str) -> list:
    """Multimodal content exists ONLY here — for this one API call.
    `history` (what gets persisted to SQLite) never sees it."""
    if attachment is None:
        return windowed
    content = [_attachment_content_block(attachment)]  # image or document block
    if current_text:
        content.append({"type": "text", "text": current_text})
    api_messages = list(windowed)          # never mutate the caller's list
    api_messages[-1] = {"role": "user", "content": content}
    return api_messages
```

**Built and verified, with real files and real API responses — not just UI clicks:**
- **Ephemeral design, confirmed by inspecting raw storage, not by trusting the code's intent** — the multimodal content block is built in a throwaway list used for exactly one `tool_runner` call; `history` only ever receives plain text via a small `_history_text_for()` helper. Verified by querying the SQLite row directly after a real attachment turn: every stored message was a plain string, never base64
- **PDF citations, with a bug caught by testing against the raw API, not the full app stack** — enabled `citations: {enabled: true}` on PDF content blocks so responses cite the exact page they drew from. First implementation silently produced zero citations; a standalone script calling the Anthropic API directly and printing the real response object revealed the citation object's fields are flat (`start_page_number` alongside a `type: "page_location"` discriminator), not nested the way the field name suggested — the original `getattr` chain was checking an attribute that never existed
- **Distinguished "reads as a PDF" from "has a text layer a citation engine can address"** — a test PDF built by saving a rendered image (no embedded text) was read correctly via vision but produced no citations, which looked like the same bug again until a PDF with real embedded text worked immediately — a distinction the file format alone doesn't reveal
- **Closed a silent-failure gap in the frontend before it could ship** — a rejected/oversized attachment returns a plain JSON `400`, not an SSE stream; the existing SSE parser would have silently swallowed it (no `data:`-prefixed line to match). Added an explicit `!res.ok` check ahead of the parsing loop as part of the same change, not as a follow-up bug fix
- **No new cost-tracking code required, confirmed empirically** — image/PDF content bills as ordinary input tokens; a PDF-attached turn showed 2814 input tokens vs. 1002 for a same-session plain-text follow-up, and the existing cost dashboard picked up the difference with zero new wiring

**Why this matters:** the highest-value bug here wasn't visible in the UI at all — a wrong `getattr` chain returned `None` silently, with no traceback, no error, just a feature that quietly did nothing. Catching it required stepping outside the running app to call the raw API directly and print the actual object, rather than debugging through the full request/response cycle. The same discipline — verify the real shape of a dependency's response before writing extraction code against an assumed one — generalizes past this one feature.

---

### 5. The Full MCP Protocol Surface — Resources and Prompts, Not Just Tools

Most MCP integrations stop at tools. Extended this project's MCP server to expose all three primitives the protocol actually defines, verifying each design decision against the real SDK and real project data rather than the textbook example.

```python
@app.list_resources()
async def list_resources() -> list[types.Resource]:
    """Built fresh on every call so note:// entries always reflect current state."""
    resources = [types.Resource(uri=AnyUrl("knowledgebase://files"), ...)]
    for title in note_list():  # notes are keyed by title, not a numeric ID
        resources.append(types.Resource(
            uri=AnyUrl(f"note://{urllib.parse.quote(title, safe='')}"), ...
        ))
    return resources
```

**Built and verified against the real SDK, not the concept:**
- **Read the installed SDK's source before writing a single decorator** — inspected `mcp/server/lowlevel/server.py` directly to confirm the exact signatures for `list_resources`/`read_resource`/`list_prompts`/`get_prompt`, and `types.Resource.model_fields` for the real constructor fields, rather than assuming from documentation or the concept alone
- **Caught an RFC violation before it ever reached the server** — the natural resource URI, `knowledge_base://files`, silently looked correct in code but fails `pydantic.AnyUrl` validation: RFC 3986 disallows underscores in URI scheme names. Verified with a two-line test script before touching the real handler; renamed to `knowledgebase://`
- **Adapted a generic example to this project's actual schema, not copied it literally** — the natural tutorial-style resource URI is `note://1`, implying numeric IDs; this project's notes are keyed by `title` (a `TEXT PRIMARY KEY`). Verified via a live test that `urllib.parse.quote`/`unquote` round-trips correctly through `pydantic.AnyUrl` for titles containing spaces, mixed case, and slashes, before building the real `note://<title>` resource
- **Verified end-to-end against a tool whose own auth blocked the obvious path** — MCP Inspector requires a session token printed to its launching terminal, which blocked scripted verification. Rather than fight the browser auth flow, wrote a standalone script using `mcp.ClientSession` — the same client class this project's own `api.py` uses — to call `list_resources`/`read_resource`/`list_prompts`/`get_prompt` directly, confirming correctness with the identical protocol calls Inspector's UI makes
- **Caught, via a follow-up `/code-review`, that "verified with a standalone script" and "reachable through the actual running app" are different claims** — the server-side implementation above was correct, but `api.py`'s `lifespan()` never called `list_resources()`/`list_prompts()` at all, so the entire feature was unreachable through the deployed chat app — dead code from the running system's perspective, only ever exercised by the standalone test script. Fixed by keeping the MCP session on `app.state` and adding four routes that call it live; verified by hitting all four against the actually-running server (`GET /resources`, `GET /resources/content`, `GET /prompts`, `POST /prompts/{name}`), not just re-running the original script

**Why this matters:** three of the four bugs here were "obviously correct" code that failed at a boundary the code itself never suggested existed — a valid-looking URI string, a plausible-looking ID scheme, and a feature that worked perfectly in isolated testing while being completely unreachable in production. All three were caught by testing the exact assumption against the real validator, the real database schema, or the real running app — not by staring at the code harder.

---

### 6. AI Cost Dashboard & Credit Tracking

Built a full observability layer for LLM API spend — the same class of tooling used in enterprise AI platforms to control costs.

**What it tracks:**
- Token usage per turn: `input`, `cache_write`, `cache_read`, `output` — broken out per model
- Estimated USD cost per message, accumulated in SQLite (`usage_logs` table)
- Per-session cost breakdown — top 10 sessions ranked by spend
- Daily usage bar chart (14-day rolling window, hover tooltips)
- Cost forecast — 30/60/90 day projected spend based on burn rate (pure frontend math, no backend changes)

**Credit tracker (with alerting):**
```
Starting balance: $5.00 | Alert threshold: $1.00
───────────────────────────────────────
Remaining: $4.72   Burn rate: $0.14/day   Est. Runway: ~33d
Progress:  ████████░░░░░░░░░░░░  5.6% used
```

- `POST /usage/credit` — saves balance + alert threshold to `credit_config` SQLite table (singleton row, upserted); optional `reset: true` starts a fresh spend-tracking period (see below)
- Progress bar changes colour: green → yellow (< 2× threshold) → red (below threshold)
- **Low-credit alert badge** in the chat UI header pulses red when remaining balance falls below the threshold — checked every 60 seconds live
- **"Est. Runway" is a forecast, not a limit** — labeled explicitly (with a tooltip) as `remaining ÷ burn rate`, not an actual credit expiration, after the plain "Days Left" label was found to imply a hard, calendar-based cutoff that doesn't exist for API credits

**Non-destructive spend-period reset (for real balance top-ups):**

A real Anthropic account top-up shouldn't blend with lifetime spend when computing what's "remaining." A confirm-gated checkbox in the credit banner sets `reset: true`, which:
- Starts a new tracking period (`credit_config.period_start`) — remaining/burn-rate/forecast recalculate from that point forward
- Archives the outgoing period's cost + active-days into a single `prev_period_*` snapshot, shown in the banner
- Never touches `usage_logs` — every historical chart and table always reflects full lifetime data regardless of resets

```python
# database.py
def credit_status(project=None) -> dict:
    """Credit config + spend/active-days scoped to the current period
    (since last reset, or all-time if the feature has never been used)."""
```

**Endpoints:**
| Route | Purpose |
|-------|---------|
| `GET /usage` | Visual HTML dashboard |
| `GET /usage/data` | JSON: totals, by_model, by_day, by_session, by_tool, by_project, period-scoped credit status |
| `GET /usage/data?project=name` | Same but filtered to one project |
| `POST /usage/credit` | Save starting balance and alert threshold; `reset: true` archives the current period and starts fresh |

**Multi-project support (Option C — multi-tenancy at the data layer):**

Added `project` column to `usage_logs` so multiple AI projects can report to the same dashboard. Dashboard shows a project filter dropdown — switch between projects and all cards, charts, and tables update.

```python
# Any new project reports with one line
usage_log(session_id, model, ..., project="my-new-project")
```

This is the same multi-tenancy pattern used in enterprise SaaS — one database, multiple tenants isolated by a tag column (`org_id` in Salesforce, `account_id` in Stripe, `project` here).

**Upgrade path to Option A (centralised HTTP endpoint):** Deploy dashboard to GCP Cloud Run → expose `POST /usage/log` → any project anywhere reports over HTTP. Option C works locally; Option A works in production.

**Cost by Tool breakdown:**

Every MCP tool call is now tracked — stored as a JSON array in `tools_used` column of `usage_logs`, aggregated via SQLite's `json_each()`:

```sql
SELECT json_each.value AS tool_name, COUNT(*) AS calls,
       SUM(estimated_cost_usd) AS cost_usd, AVG(estimated_cost_usd) AS avg_cost_usd
FROM usage_logs, json_each(usage_logs.tools_used)
GROUP BY json_each.value ORDER BY calls DESC
```

The dashboard shows which tools are called most and what they cost — `search_docs` dominates because it routes to Sonnet with document context; `get_weather` is nearly free.

**Token economics understood:**
```
Claude reads  → INPUT  tokens  → you pay input price
Claude writes → OUTPUT tokens  → most expensive per token (3–5×)
Cache hit     → READ   tokens  → 10× cheaper than input
System prompt cached after message 1 → near-free on every subsequent turn
```

**Key engineering decision:** cost is estimated from token counts × pricing table — no extra API call. Schema migration handled safely with `ALTER TABLE ... ADD COLUMN` + try/except. A stale pricing entry (old Haiku 3.5 rates left in place after migrating to Haiku 4.5) was later found by comparing the dashboard's live balance against the real console.anthropic.com figure — fixed, all affected historical rows backfilled, and the silent fallback that let it hide replaced with a warning for any future unpriced model.

---

### 7. Mobile Alerting — Designing for Real Runtime Constraints, Not the Textbook Pattern

Directly extends the cost dashboard above: turned its passive in-browser alert badge into five real-time Discord push notifications — two-tier low-balance (warning/critical), a spend-spike detector, a per-tool budget cap, a daily digest, and a missing-pricing-data alert — landing on a phone instead of requiring the dashboard tab to be open.

```python
async def _maybe_send_low_credit_alert() -> None:
    # Two independent cooldowns, each auto-clearing on recovery — critical
    # supersedes warning so a single drop never double-alerts
    if remaining <= alert_threshold:
        if cfg.get("last_warning_sent_at"):
            clear_warning_cooldown()  # bug found via transition testing, not per-tier testing
        ...
```

**Built and verified, with a real Discord webhook and live production data (no staging environment):**
- **Rejected the "obvious" architecture after checking a runtime assumption** — a background scheduler firing at a fixed time (the standard way to build a "daily digest") silently assumes the process is always running, which this app isn't (`uvicorn --reload`, started manually). Redesigned the trigger to piggyback on real traffic instead: compare today's date to the last-sent date on every request, no new dependency, no missed days
- **Found a stateful bug that per-tier testing couldn't catch** — testing "does warning fire" and "does critical fire" both passed, but the transition of dropping straight from normal into critical (skipping the warning zone) left the warning tier's cooldown stale, which would have silently suppressed a legitimate re-warn on a later partial recovery. Caught only by testing the actual transition sequence, then fixed and re-verified
- **Handled a live secret end-to-end safely** — when a real Discord webhook URL arrived directly in the conversation, verified `.gitignore` coverage structurally (`git check-ignore`) and confirmed the write with `grep -c` rather than ever printing the value back
- **Test discipline against production data with no staging copy** — every alert path (2 balance tiers, spike, per-tool budget, digest) was tested by capturing exact current state, temporarily perturbing only what was needed to force each condition, verifying the effect via direct query, then restoring the original values exactly — zero corruption to real credit tracking across all four test runs
- **A silent failure mode found its own recurrence, and got caught before shipping again** — a code review flagged that `_estimate_cost()`'s fallback for an unrecognized model only printed to stdout, the exact "invisible unless you're tailing server logs" shape as the original Haiku pricing-drift bug this warning was built to catch. Added a fifth Discord alert (one-time per model, not a daily cooldown — this is a config gap, not a spend threshold) and verified it end-to-end against real code with an obviously-fake model name, `_send_discord` monkeypatched to capture instead of actually notifying, and the fake test rows deleted with the deletion explicitly re-verified afterward

**Why this matters:** the highest-value bug here wasn't a syntax error or a missing null check — it was a design assumption (always-on process) that would have shipped invisibly broken, and a state-transition gap that per-state testing structurally cannot find. Both required stepping back from "does this feature work" to "does this feature's design match the environment it actually runs in."

---

### 8. Tool Use Internals — Beyond the SDK Abstraction

This project's tool-calling (see the MCP section above) runs on the Anthropic SDK's `tool_runner` helper. To understand what it actually automates, built the same mechanics by hand against this project's own `get_weather` and `manage_notes` tool schemas — no `tool_runner`, no MCP — in a standalone script (`tool_use_demo.py`).

```python
# Forcing a specific tool call — bypasses "auto" and any prompt-wording persuasion
resp = client.messages.create(
    model=MODEL, tools=[GET_WEATHER_TOOL],
    tool_choice={"type": "tool", "name": "get_weather"},
    messages=[{"role": "user", "content": "Tell me a fact about deserts"}],
)
# stop_reason is guaranteed "tool_use" — Claude still infers a best-guess
# argument (city: "Sahara") rather than refusing, even though the prompt
# never asked about weather
```

**Demonstrated, with real API calls and verified results:**
- **`tool_choice` modes** — `auto` (Claude answered the desert question directly, no tool call) vs. forced `{"type": "tool", "name": "get_weather"}` (same prompt, tool call mandatory) — proved forcing constrains the *action*, not the model's judgment about arguments
- **`disable_parallel_tool_use`** — a two-tool-inviting prompt produced 2 parallel `tool_use` blocks under `tool_choice: any`; adding `disable_parallel_tool_use: True` collapsed it to exactly 1
- **Streaming tool arguments** — watched `input_json_delta` events arrive as raw, unparseable JSON fragments (`'{"cit'` → `'{"city": "'` → `'{"city": "Seattle"}'`), only valid once the content block closed — the layer `tool_runner` hides (its Python implementation returns complete messages, not token-level deltas)
- **Manual multi-turn loop** — built the `tool_use` → execute → `tool_result` → loop cycle from scratch (save a note, read it back, 3 turns total), matching `tool_use_id` by hand and verifying the SQLite write actually persisted via `inspect_db.py` — not just trusting the model's summary

**Why this matters:** every production framework (`tool_runner`, LangChain agents, LlamaIndex) is a convenience layer over these exact primitives. Understanding the raw request/response cycle means being able to debug or reimplement tool-calling behavior when the abstraction doesn't fit — e.g. adding human-in-the-loop approval before a tool executes, which requires the manual loop, not `tool_runner`.

---

### 9. Prompt Evaluation Pipeline

Built an eval pipeline to verify Claude follows system prompt rules — not manually, but automatically with a scored pass/fail report.

```
evals/dataset.json   → 12 test cases (expected tool + expected model per input)
evals/run_evals.py   → calls /chat, scores tool selection + model routing, reports %
```

**Result: 12/12 (100%) passing**

```
doc-001   List files → list_docs       OK  OK   PASS
doc-002   Summarize  → search_docs     OK  OK   PASS
math-001  Math       → no tool, Haiku  OK  OK   PASS
notes-001 Save note  → manage_notes    OK  OK   PASS
...
Score: 12/12 (100%) — All evals passed!
```

Evals caught two real bugs that manual testing missed:
- `/chat` endpoint was not returning the `model` field in its response
- System prompt was ambiguous about `search_docs` vs `list_docs`

---

### 10. Configuration & Security

- `.env` + `python-dotenv` for API key management (industry standard)
- `temperature=0.3` — tuned for a tool-using assistant (consistent, not creative)
- SSL workaround for Windows corporate certificate chains
- Diagnosed a silent auth failure caused by a UTF-8 byte-order-mark in `.env` — root-caused via structural checks (`grep -c "^ANTHROPIC_API_KEY="`) rather than ever printing the key itself
- Evaluated a third-party MCP server (Playwright, Microsoft's official package) before installing — checked publisher trust, exact access boundary (browser automation only, no filesystem/shell reach), and where prompt-injection risk actually lives (untrusted external content, not applicable when testing `localhost`)
- Standing discipline: after every new file, dependency, or MCP server, check `git status` for untracked artifacts and confirm `.gitignore` covers them before considering a change complete — caught a real gap where Playwright's screenshot/snapshot output wasn't ignored and could have leaked session data into the public repo
- **Indirect prompt injection defense** — identified that `search_docs`/`read_doc` results flow back into Claude's context as `tool_result` blocks, indistinguishable from real instructions unless told otherwise (OWASP's #1 LLM risk, and the standard failure mode for RAG pipelines specifically). Added a `<security>` tag to `SYSTEM_PROMPT` explicitly instructing Claude to treat retrieved document/note content as data, never as commands — verified via the eval suite that the change didn't alter tool-routing behavior
- **Input sanitization** — `_sanitize_input()` strips control/non-printable characters and caps message length before any user input reaches history or the model, closing off context-window abuse as a separate, cheaper first layer
- **Caught a stale technique before it shipped** — a planned "response prefilling" approach for structured JSON output turned out to return a hard 400 on this project's own routed model (`claude-sonnet-4-6`); verified live via the Models API that both routed models support `output_config.format` / `client.messages.parse()` instead, and used that as the correct forward path for structured outputs

---

### 11. Streaming — Server-Sent Events

Real-time response streaming from Claude to the browser as text is generated — the same pattern used by ChatGPT and Claude.ai.

```python
async def generate():
    async for msg in runner:
        if block.type == "text":
            yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"

return StreamingResponse(generate(), media_type="text/event-stream")
```

Event types: `tool` (tool being called), `text` (chunk), `done` (model + token breakdown), `error`

---

### 12. Prompt Caching

System prompt marked with `cache_control: ephemeral` — saves ~90% of system prompt token costs after the first API call in a 5-minute window.

```python
SYSTEM_PROMPT = [{
    "type": "text",
    "text": "You are a helpful assistant...",
    "cache_control": {"type": "ephemeral"}
}]
```

Token breakdown tracked per response: `input`, `cache_write`, `cache_read`, `output` — displayed live in the UI.

---

### 13. Model Routing

Automatically routes each query to the cheapest model that can handle it — Haiku (10–20× cheaper) for simple queries, Sonnet for complex/document queries.

```python
def _pick_model(message: str) -> str:
    if len(message) > 120 or any(signal in message.lower() for signal in _COMPLEX_SIGNALS):
        return "claude-sonnet-4-6"
    return "claude-haiku-4-5"
```

---

### 14. Persistent Conversation History

Multi-turn sessions stored in SQLite. Full history saved to DB; only the last 10 messages sent to Claude (caps token cost without losing continuity).

- `_safe_window()` — guards against orphaned `tool_result` turns at the history boundary
- Empty assistant turn guard — never corrupts history on partial responses
- Sessions survive server restarts and browser refreshes

---

### 15. FastAPI + Async Python

- Lifespan hooks keep the MCP server alive across all requests (not spawned per request)
- Pydantic request validation, async route handlers
- `app.state` shares tools and API client across all requests
- REST endpoints: `GET /`, `GET /tools`, `GET /resources`, `GET /resources/content`, `GET /prompts`, `POST /prompts/{name}`, `GET /attachment-limits`, `POST /chat`, `POST /stream`, `GET /sessions`, `DELETE /session/{id}`

---

### 16. PDF OCR Pipeline

- Text-based PDFs: extracted directly via `pypdf`
- Scanned PDFs: `pymupdf` renders pages to images at 300 DPI → `pytesseract` extracts text
- Path traversal protection on all file access

---

### 17. Multi-Agent Orchestration — Directing Isolated Agents, Not Just Prompting One

Beyond using an AI assistant conversationally, designed and ran actual multi-agent pipelines against real work on this repo — with deliberate structural constraints, not just instructions the agents were trusted to follow.

```
Two-agent draft/review pipeline on a real bug (unawaited task cancellation in
an SSE cleanup path):
  Drafter  — full edit access, implements the fix, does not commit
  Reviewer — read-only tools only (no Edit/Write available at all)
             independently re-reads the live file (doesn't trust the diff
             handed to it), traces the correctness argument, renders a verdict
  Orchestrator (human-directed) — decides ship/revise based on the verdict
```

- **Tool access as an architectural guarantee, not a hoped-for behavior** — the reviewer agent's "don't fix, just critique" constraint wasn't an instruction it could ignore; it had no `Edit`/`Write` tool available in its toolset at all, so bypassing the constraint was structurally impossible, not just discouraged
- **Verified the verifier** — before trusting the reviewer's verdict, independently pulled the actual `git diff` rather than accepting the drafter's self-reported summary of its own change; the reviewer was separately instructed to re-read the live file itself rather than trust the diff it was handed, catching a real, non-obvious correctness argument (why catching a specific exception at a specific point is safe, tied to an internal invariant of a different function) that the drafter's own report hadn't surfaced
- **Delegation scoped by actual context need, not applied by default** — used a fully isolated `Explore` subagent (no shared memory with the driving conversation) to investigate a separate, real GitHub issue before fixing it, since that task benefited from a scoped, self-contained brief and a checkable file:line-cited report; used direct execution (no subagent) for smaller, linear fixes afterward, since spawning an agent per small fix would have added context-reload overhead without a matching benefit — the orchestration pattern was chosen per-task, not applied uniformly
- **Verified an SDK's actual guarantee before stacking a redundant layer on top of it** — before implementing a planned retry-with-backoff mechanism for Anthropic API rate limits, read the installed SDK's source directly and found `AsyncAnthropic` already retries 429s/5xx/timeouts internally with exponential backoff and jitter by default; building the originally-planned retry loop anyway would have shipped two silently-stacked retry layers. Redirected the actual fix to the real gap — a clean failure path once those built-in retries are exhausted, which had no error handling at all

**Why this matters:** the differentiated skill here isn't "can prompt an LLM" — it's treating agent output as a claim to verify rather than a result to trust, matching delegation structure to the actual shape of a task instead of defaulting to either "always delegate" or "never delegate," and using tool-access scoping as a real engineering control rather than a documentation-only convention. This is the same discipline that runs through every other section of this portfolio — verify before trusting — applied one level up, to coordinating agents instead of coordinating code.

---

## Key Engineering Decisions

| Decision | Why |
|----------|-----|
| MCP over direct tool calls | Standard protocol — portable across any MCP-compatible client |
| ChromaDB over in-memory search | Persists embeddings across restarts |
| SQLite for sessions | Production pattern — survives restarts, zero setup |
| Prompt caching | ~90% token savings on system prompt at scale |
| Model routing | 10–20× cost reduction for simple queries |
| SSE over WebSockets | Simpler for one-directional streaming; sufficient for chat |
| `temperature=0.3` | Tool-using assistants need consistency, not creativity |
| `.env` over OS env vars | Portable, project-scoped, git-ignored |
| Client-side cost estimation | Token count × pricing table — no extra API call needed |
| Credit alert in chat header | Surface spend pressure where the user is working, not a separate admin screen |

---

## AI-Powered Engineering — Claude Code

This entire project was built using **Claude Code** as an AI-powered development environment — not just as a chatbot, but as an integrated engineering tool.

### How I use Claude Code professionally

| Capability | How I use it |
|------------|-------------|
| **AI pair programming** | Build features, debug issues, and refactor code through natural language in the terminal |
| **`/code-review`** | Run structured code reviews at configurable depth before every commit |
| **`/verify`** | Confirm a change works in the running app, not just in tests |
| **`/simplify`** | Audit changed code for reuse, efficiency, and unnecessary complexity |
| **`/security-review`** | Review pending changes for OWASP-level vulnerabilities |
| **MCP servers** | Evaluated and wired up Playwright MCP (Microsoft's official browser-automation server) at project scope — assessed publisher trust, access boundary, and prompt-injection risk before installing, then used it to drive the chat UI and cost dashboard end-to-end, which caught a real `.env` encoding bug (UTF-8 BOM silently breaking API auth) that code review alone had missed |
| **Hooks** | Automate lifecycle actions (PreToolUse, PostToolUse, SessionStart) |
| **Skills** | Custom slash commands for project-specific workflows |
| **Memory system** | Persistent context across sessions — project state, preferences, learning path |
| **Subagents & orchestration** | Spawn isolated agents for independent research or code tasks, and design multi-agent pipelines with real structural constraints (e.g. a read-only reviewer agent) — see section 17 |

### Why this matters for engineering teams

Claude Code changes how engineering work gets done — not by replacing engineers, but by eliminating the friction between intent and implementation. An engineer who knows how to use AI tooling effectively ships faster, catches more bugs, and spends more time on architecture decisions than boilerplate.

Using Claude Code throughout this project means every decision — from database choice to token optimization to security — was made with AI-assisted reasoning, then verified against the running code.

---

## Security Engineering — Supply Chain & Secret Hygiene

Beyond application-level security (path traversal defense, prompt injection resistance, sandboxed `eval()`), this project's development workflow itself was hardened using practices standard on professional engineering teams:

| Practice | Implementation |
|----------|-----------------|
| Secret-leak prevention | `gitleaks` pre-commit hook — blocks any commit containing a likely secret before it ever reaches git history; re-verified against the full commit history (86 commits as of this writing, zero findings) |
| Commit provenance | SSH-based commit signing — every commit cryptographically signed, independently verified via GitHub's API (`"verified": true`), not just a local display badge |
| Dependency vulnerability scanning | `pip-audit` run against all project dependencies; found and fixed 5 real CVEs in `pip`; correctly identified one CVE in `chromadb` as inapplicable after tracing the actual code path (`PersistentClient`, embedded — not the vulnerable networked server mode) |
| Network exposure review | OS-level firewall audit — identified and closed inbound rules unnecessarily exposed on untrusted (Public) network profiles |

**Why this matters:** a dependency scanner or CVE database tells you a vulnerability exists somewhere in your dependency tree — it doesn't tell you whether *your* code exercises the vulnerable path. Treating every flagged CVE as equally urgent either causes alert fatigue (patch everything reflexively) or missed real risk (start ignoring the scanner). The discipline demonstrated here is reading the advisory and tracing the actual call path before deciding whether a finding requires action.

---

## What's Next

| Phase | Concept |
|-------|---------|                                                                                                   
| Testing (pytest) | Unit + integration tests for MCP tools and API endpoints |
| Docker | Containerisation and portability |
| PostgreSQL | Production database (replacing SQLite) |
| GCP Cloud Run | Cloud deployment |
| React Frontend | Replace chat.html with a proper React UI |
| Authentication (JWT) | Multi-user, secure sessions |

---

*Full learning journey documented in [LEARNING_JOURNEY.md](LEARNING_JOURNEY.md)*
