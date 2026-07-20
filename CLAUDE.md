# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Folder Structure

```
MCP Project/
├── src/
│   ├── backend/          # app code — api.py, agent.py, mcp_server.py, database.py, rag.py, text_editor_tool.py
│   └── frontend/         # chat.html, usage.html served by api.py
├── scripts/              # standalone utilities — convert_pdfs.py, inspect_db.py, tool_use_demo.py
├── knowledge_base/       # RAG source documents Claude searches (was docs/ before the Phase 22 reorg)
├── docs/                 # project markdown documentation (this file and README.md stay at root)
├── data/                 # data.db (SQLite) and chroma_db/ (ChromaDB) — both gitignored, auto-created
└── evals/                # eval dataset + runner
```

Cross-module imports inside `src/backend/` stay flat (e.g. `from database import ...` in `api.py`) rather
than becoming a real installable package — `uvicorn`/scripts add `src/backend/` to `sys.path` via
`--app-dir` or an explicit `sys.path.insert` instead. See the "Commands" run lines below for the exact
invocations this requires.

## Commands

```powershell
# Install all dependencies
pip install anthropic[mcp] mcp pymupdf pytesseract pypdf fastapi "uvicorn[standard]" chromadb sentence-transformers python-dotenv httpx

# Run the web app (primary entry point) — from the project root
python -m uvicorn api:app --reload --port 8000 --app-dir src/backend
# Open: http://localhost:8000

# Run the CLI agent (original learning version) — from the project root
python src/backend/agent.py

# Run eval pipeline (WARNING: consumes API credits — 1 Claude API call per test case)
# Start the app first, then in a second terminal:
python evals/run_evals.py

# Convert scanned PDFs in knowledge_base/ to .txt using Tesseract OCR
python scripts/convert_pdfs.py

# Inspect SQLite database contents
python scripts/inspect_db.py

# Tool Use Fundamentals demo (WARNING: consumes API credits — ~6 short Claude API calls)
python scripts/tool_use_demo.py
```

Tesseract must be installed at `C:\Program Files\Tesseract-OCR\` for `convert_pdfs.py` to work.

## Architecture

Three processes when the web app runs:

**`src/backend/api.py`** — FastAPI web server. Spawns `src/backend/mcp_server.py` on startup via lifespan, keeps it alive across all requests. Handles HTTP routes, SSE streaming, session management. Auto-indexes `knowledge_base/` into ChromaDB on startup. Stores sessions in SQLite. Also declares two non-MCP Anthropic tools directly in `app.state.tools` — see "Non-MCP Tools" below.

**`src/backend/mcp_server.py`** — MCP server exposing all three MCP primitives: 8 tools, 2 resource kinds (`knowledgebase://files`, `note://<title>`), and 1 prompt (`summarize_document`) — see "MCP Resources & Prompts" below. No knowledge of Claude or HTTP. Notes stored in SQLite via `database.py`. Document search via `rag.py` + ChromaDB.

**`src/backend/text_editor_tool.py`** — `ProjectNotesEditorTool`, a client-side Anthropic builtin tool (`BetaAsyncBuiltinFunctionTool`) executed in-process by `api.py`, not via MCP.

**`src/backend/agent.py`** — Original CLI version. Same MCP connection logic as `api.py` but uses `input()` instead of HTTP.

```
Browser ──HTTP/SSE──► api.py ──stdio/JSON-RPC──► mcp_server.py (8 tools, 2 resource kinds, 1 prompt)
                        │
                        ├──► text_editor_tool.py (client-side, in-process)
                        │
                        └──► Anthropic API (Claude Sonnet 4.6 / Haiku 4.5)
                                  └── web_search (server-side, runs on Anthropic's infra)
```

## Tools (10 total)

Three different execution models share one `tools` list passed to Claude — don't assume every tool is an MCP tool.

| Tool | Execution | Notes |
|---|---|---|
| `get_current_datetime` | MCP | No params |
| `calculate` | MCP | `eval()` with restricted namespace — only math functions allowed |
| `get_weather` | MCP | Mock data dict — replace with real API for production |
| `manage_notes` | MCP | SQLite-backed — persists across restarts via `database.py` |
| `list_docs` | MCP | Reads `knowledge_base/` folder; supports `.txt .md .csv .json .py .html .xml .pdf` |
| `read_doc` | MCP | Path traversal blocked; 8000-char cap; PDF via `pypdf` or `pymupdf+Tesseract` |
| `index_docs` | MCP | Chunks all docs → embeds with `all-MiniLM-L6-v2` → stores in ChromaDB |
| `search_docs` | MCP | Semantic search via ChromaDB; returns top N chunks with relevance scores |
| `web_search` | **Server-side** | Anthropic-hosted, no local code executes it. `max_uses: 3` caps searches/turn. `allowed_callers: ["direct"]` is required — the `web_search_20260209` default (`["code_execution_20260120"]`, for dynamic filtering) 400s on Haiku, which `_pick_model()` can route to and which doesn't support programmatic tool calling. |
| `str_replace_based_edit_tool` | **Client-side** | `ProjectNotesEditorTool` in `text_editor_tool.py`. Hardcoded to `knowledge_base/project_notes.md` only — every path Claude sends is resolved and compared against that exact file; anything else (other `knowledge_base/` files, `../` traversal, absolute paths) raises `ToolError` before touching disk. |

## Adding a New Tool

**MCP tool** (runs in `mcp_server.py`, needs local execution logic):
1. Add a `types.Tool(...)` entry in `list_tools()` in `mcp_server.py`
2. Add an `if name == "tool_name":` handler in `call_tool()` returning `list[types.TextContent]`
3. Restart `api.py` — tool discovery is automatic on each session start

**Anthropic server-side tool** (e.g. web_search, code_execution): declare it as a plain dict directly in `app.state.tools` in `api.py`'s lifespan (see `web_search_tool` there) — Anthropic executes it, no local handler needed. Check `allowed_callers` against every model your app routes to, per the `web_search` gotcha above.

**Anthropic client-side builtin tool** (e.g. text editor, bash): write a class implementing `anthropic.lib.tools.BetaAsyncBuiltinFunctionTool` (`to_dict()` returns the tool declaration, `call(input)` executes it) — see `text_editor_tool.py` — and instantiate it into `app.state.tools`. Client-side tools must NOT be declared as raw dicts in `tool_runner()`'s `tools` list — the runner only executes objects implementing this interface.

`server_tool_use` blocks (server-side tools) are a **different content-block type** than `tool_use` (client/MCP tools) in the response stream — code that only checks `block.type == "tool_use"` for logging/tracking (e.g. `tools_used.append(...)`) will silently miss every server-side tool call. Handle both types wherever tool calls are counted.

## MCP Resources & Prompts

`mcp_server.py` uses all three MCP primitives, not just tools:

- **Resources** (`@app.list_resources()` / `@app.read_resource()`) — read-only, URI-addressable data the client reads directly, without a function call. Two kinds, both dynamically enumerated on every `list_resources()` call so they reflect current state: `knowledgebase://files` (static — same listing `list_docs` returns, exposed as a resource instead of a tool call) and `note://<url-quoted-title>`, one per row in `note_list()`. Notes are keyed by `title` (TEXT PRIMARY KEY in `database.py`), not a numeric ID, so the URI encodes the title directly via `urllib.parse.quote`/`unquote` — verified this round-trips correctly for spaces, mixed case, and slashes via `pydantic.AnyUrl`.
- **Prompts** (`@app.list_prompts()` / `@app.get_prompt()`) — reusable request templates a client can invoke by name. `summarize_document` takes a `filename` argument and returns a pre-built message that drives the existing `read_doc`/`search_docs` tools, rather than introducing an unrelated example.

**Gotcha found via testing, not guessing:** a URI scheme cannot contain an underscore per RFC 3986 (`scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )`) — `AnyUrl("knowledge_base://files")` raises a `url_parsing` validation error; `AnyUrl("knowledgebase://files")` (no underscore) is required instead.

Tested via a direct `mcp.ClientSession` script (`list_resources`/`read_resource`/`list_prompts`/`get_prompt`) rather than only through MCP Inspector's UI — Inspector's browser-based proxy requires a session auth token printed to the launching terminal, which blocked automated verification; the direct client script exercises the identical protocol calls Inspector's UI makes.

**Reachable through the running app, not just standalone scripts/Inspector:** `api.py`'s `lifespan()` keeps the `mcp_session` on `app.state.mcp_session` (not just the tool wrappers), and four routes call it live — `GET /resources`, `GET /resources/content?uri=...`, `GET /prompts`, `POST /prompts/{name}`. This was a real gap found by `/code-review` (GitHub issue #4): the two primitives were fully implemented server-side but the client (`api.py`) never called `list_resources()`/`list_prompts()` at all, so the entire feature was dead code from the running app's perspective until fixed. `/resources`/`/prompts` are plain JSON routes, not additional entries in the `tools` list Claude sees — they're a separate access pattern (client reads a resource directly, or invokes a prompt template), not new Claude-facing tools.

## Image + PDF Attachments (Chat)

Not an MCP/server-side/client-side tool like the 10 above — this is a native Anthropic Messages API content-block feature (vision + document), wired directly into `/chat` and `/stream`. `ChatRequest.attachment` (`Attachment` model: `media_type`, `data` base64, optional `filename`) carries at most one image or PDF per turn.

**Ephemeral by design:** `history` (what `session_save()` persists to SQLite) only ever receives plain text from `_history_text_for()` — the message plus a `[User attached a file: name]` marker, never the base64 binary. The multimodal content block only exists in the locally-built `api_messages` list from `_build_api_messages()`, used for that one `tool_runner` call and discarded after. A later turn in the same session has no way to re-see the file unless it's re-attached — confirmed via SQLite inspection during testing (every persisted `content` field is a plain string). `attachment.filename` is documented as display-only and deliberately unvalidated by `_validate_attachment()`, but it still lands in that persisted marker and gets resent to Claude as ordinary text on later turns — `_history_text_for()` routes it through the same `_sanitize_input()` the message text already uses before embedding it (GitHub issue #2).

**Validation:** `_validate_attachment()` raises `HTTPException(400)` before any state changes for an unsupported `media_type` (allowlist: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `application/pdf`), invalid base64, or oversized payload (`_MAX_IMAGE_ATTACHMENT_BYTES` = 5MB, matching Anthropic's own image limit; `_MAX_PDF_ATTACHMENT_BYTES` = 10MB). In `/stream`, this validation runs in `stream_chat()`'s body *before* `StreamingResponse` is constructed, so a 400 comes back as a normal JSON error, not a broken SSE stream — the frontend's `send()` in `chat.html` checks `!res.ok` before parsing SSE for exactly this reason. Whitespace/newlines are stripped from the base64 payload before decoding (standard line-wrapped encoders like Python's `base64.encodebytes` or the Unix `base64` CLI insert a newline every 76 chars, which `validate=True` would otherwise reject — only the JS client's single-line `FileReader` output passed before this fix). The decoded size is also derived exactly from the encoded length *before* decoding, so an oversized payload is rejected without paying the cost of actually decoding it first (GitHub issues #6, #7).

**Attachment-aware model routing:** `_pick_model(message, has_attachment=...)` always routes to Sonnet when an attachment is present, regardless of the text message — `chat.html` allows sending an attachment with no typed text, and an empty message string has no signal about the attached document/image's actual complexity (GitHub issue #3; previously this case silently routed to Haiku).

**Limits served from the backend, not triplicated:** `GET /attachment-limits` returns the allowed MIME types and size caps as JSON; `chat.html` fetches it on load and updates its JS constants (`ATTACHMENT_ALLOWED_TYPES`, `MAX_IMAGE_BYTES`, `MAX_PDF_BYTES`) and the file input's `accept` attribute from the response, instead of the type/cap values existing independently in three places (backend, JS constants, `accept` attribute) able to silently drift out of sync (GitHub issue #11). The JS constants keep their original hardcoded values as the pre-fetch default so the UI still works during the brief window before the fetch resolves.

**Citations (PDF only):** `_attachment_content_block()` adds `citations: {enabled: true}` to `document`-type blocks (not `image` blocks — citations don't apply to images). When Claude cites a specific page, both endpoints append an inline `(p.N)` marker to the response text via the shared `_text_with_citations(block)` helper, which reads `start_page_number` directly off each citation object — extracted into one function after `/chat` and `/stream` each had their own copy of the identical loop (GitHub issue #10). **Gotcha found during testing:** the citation object's location fields are flat with a `type: "page_location"` discriminator string — not nested under a `.page_location` sub-attribute the way the field name might suggest. Also: citations only work against a PDF with a real embedded text layer — a purely rasterized/image-based PDF (e.g. one built by saving images via Pillow) has nothing for Claude to cite against, which is correct behavior, not a bug.

**No new cost-tracking code needed** — image/PDF tokens bill as ordinary `input_tokens` in the API response, already captured the same way every other request's tokens are reported to SpendGaugeAI. Confirmed during testing (back when this project's own local dashboard still existed): a PDF-attached turn showed `2814 in` vs. `1002 in` for a plain-text follow-up in the same session, and the totals picked up the difference automatically.

**Frontend (`chat.html`):** a 📎 button + hidden `<input type="file">` in the footer, client-side allowlist/size checks mirroring the backend exactly, and a filename chip with a remove (×) control. Drag-drop/paste and multiple attachments per turn are explicitly out of scope for now — file-picker, one file, is the only supported flow.

## Cost Dashboard & Credit Tracking — REMOVED 2026-07-19

This project's own local `/usage` dashboard, credit tracking, and Discord alerting
(`GET /usage`, `GET /usage/data`, `POST /usage/credit`, `_run_alert_checks()` and its six
`_maybe_send_*` alert functions in `api.py`) were removed in favor of
[SpendGaugeAI](https://github.com/vijayanan6/SpendGaugeAI) — see § Logging & Tracing below for
this project's SpendGaugeAI reporting config, and that repo's own `docs/DESIGN.md` for the
current feature set (it has the same 4-way token breakdown, cost by model/project/tool, credit
tracker, and Discord alert types this section used to document, plus multi-app support without
needing the "copy `database.py` into every project" approach below).

**`database.py`'s underlying tables/functions (`usage_logs`, `credit_config`, `pricing_warnings`,
`usage_log()`, `usage_summary()`, `credit_status()`, `credit_set()`, `daily_digest()`, etc.) were
deliberately left in place, unused** — removing them would mean editing the shared `init_db()`
that also creates `notes`/`sessions`, for a benefit (dead code cleanup) that didn't justify the
risk. The historical data is still in `data/data.db` if it's ever worth revisiting; nothing reads
it anymore.

**Worth preserving from the removed implementation, in case this pattern comes up again:**
- **Pricing table drift is a real, recurring failure mode, not hypothetical.** `_PRICING` (a
  manual snapshot — Anthropic's API has no live-pricing endpoint) went stale on 2026-07-15:
  `claude-haiku-4-5` carried old Haiku-3.5-era rates, undercounting every Haiku-routed request by
  ~20%, caught only by comparing the dashboard's balance against the real console.anthropic.com
  figure. Re-verify any hardcoded pricing table by hand whenever Anthropic changes rates.
- **Per-tool cost attribution needs "once per distinct tool per turn," not "once per mention."**
  A turn calling the same tool 3 times naively summed as 3× the turn's real cost if grouped
  directly on exploded `tools_used` JSON rows — the `calls` count looked right, which is exactly
  what made the wrong `cost_usd` number look trustworthy. Fix: group to `(row_id, tool_name)`
  first, then aggregate. See that project's Insight #37 if this comes up again.
- **A background scheduler (APScheduler etc.) can silently miss days** if the app isn't
  guaranteed to be running at a fixed wall-clock time — piggybacking a "daily digest" on the
  first real request of a new day instead is more reliable for a locally-run tool.
- **A silent fallback (e.g. defaulting an unrecognized model to Sonnet's price) is exactly what
  lets pricing drift go unnoticed** — surface it (console warning, one-time alert) instead.

## Persistence

- **SQLite** (`data/data.db`) — notes, sessions, usage_logs, credit_config tables. Managed by `database.py`. Auto-created on startup.
- **ChromaDB** (`data/chroma_db/`) — vector embeddings for semantic doc search. Managed by `rag.py`. Auto-indexed on `api.py` startup.
- Both `data/data.db` and `data/chroma_db/` are in `.gitignore` — local only.

## knowledge_base/ Folder

Place `.txt`, `.md`, or `.pdf` files here (renamed from `docs/` in the Phase 22 reorg — `docs/` is now project markdown documentation instead). Scanned PDFs must be pre-converted via `scripts/convert_pdfs.py` (Tesseract OCR). Text-based PDFs are read directly via `pypdf`. All files here are auto-indexed into ChromaDB on `api.py` startup. Re-index after adding new files by saying "Re-index my documents" in chat or restarting the server.

## System Prompt Behaviour

`api.py` uses a smart system prompt that tells Claude to call `search_docs` first for topic-specific questions (people, projects, subjects) but skip it for clearly general questions (math, weather, time). This avoids unnecessary tool calls while still prioritising document content.

The prompt is defined as `SYSTEM_PROMPT` with `cache_control: ephemeral` so Anthropic caches it across turns — saving ~90% of those input tokens after the first call.

Conversation history is capped at the last **10 messages** (`HISTORY_LIMIT`) to keep context size bounded. Full history is still persisted to SQLite; only the window sent to Claude is trimmed.

Both `/chat` and `/stream` slice their history window through the same module-level `_safe_window()` (never split a `tool_use`/`tool_result` pair — drops a leading orphaned `tool_result` if the window boundary lands mid-pair). `_safe_window()` used to be a closure local to `stream_chat()`, so `/chat` had no equivalent guard and could send Anthropic a malformed window in a long tool-heavy session (a real gap, GitHub issue #9) — hoisted to module scope so both routes share one implementation instead of `/chat` getting a duplicated copy.

## API Error Handling

`AsyncAnthropic`'s default `max_retries=2` already retries 429/5xx/timeout/connection errors internally with exponential backoff + jitter (honoring a `Retry-After` header when present) before raising — confirmed by reading `anthropic/_base_client.py`'s `_should_retry`/`_calculate_retry_timeout`, not assumed. Don't hand-roll a second retry loop around `tool_runner()`; it would just duplicate what the SDK already does.

What *was* missing: a clean failure path once those built-in retries are exhausted. `/chat`'s `tool_runner` loop previously had no error handling at all — any Anthropic API error propagated as a raw 500 with a full traceback. Both `/chat` and `/stream` now catch `anthropic.APIError` (the common base class for `RateLimitError`/`APITimeoutError`/`APIConnectionError`/`APIStatusError`) specifically: `/chat` raises a clean `HTTPException(503, ...)`, `/stream` yields a clean `{"type": "error", ...}` SSE event instead of leaking the raw exception string. A broader `except Exception` still exists in `/stream` as a fallback for genuinely unexpected (non-Anthropic) errors.

## Logging & Tracing

**Structured logging** — `api.py` uses a named `logger` (Python's `logging` module, not `print()`), with two handlers: console (level scales with `ENVIRONMENT` — `DEBUG` in development, `INFO` elsewhere) and a `TimedRotatingFileHandler` writing to `data/app.log` (rotates at midnight, keeps 14 days, always captures `INFO`+ regardless of environment). Levels are chosen deliberately per call site: routine events (startup, indexing) are `INFO`; non-fatal caught failures (a Discord webhook failing, one alert check failing) are `WARNING`; genuinely unexpected/crash-class failures are `ERROR` with `exc_info=True` so the full traceback lands in the file, not just a one-line message.

**`GET /logs`** — a dashboard for browsing `data/app.log` (today's entries only; rotation moves prior days to dated backup files, out of scope for this live-tail view). `_parse_log_file()` parses the timestamp-prefixed lines into structured entries, folding unprefixed continuation lines (tracebacks) into whichever entry precedes them. `GET /logs/data?level=ERROR&limit=200` returns the parsed JSON; the page itself has click-to-filter summary cards, expandable tracebacks, and tab-visibility-aware polling.

**Request latency** — `_log_latency(route, start_time, **fields)` is called at *every* exit point of both `/chat` and `/stream` (success and every failure path alike — latency on a failing request is exactly as useful to know as on a succeeding one), logged at `INFO` and surfaced in the response body (`/chat`) / `done` SSE event (`/stream`).

**Langfuse tracing (optional)** — set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env` (free tier at cloud.langfuse.com) to get full end-to-end tracing of every Claude API call. Same optional-feature pattern as `DISCORD_WEBHOOK_URL`: `langfuse_client` is `None` if the keys aren't set, and every call site checks for that before doing anything — the feature no-ops cleanly rather than erroring if unconfigured. `/chat` and `/stream` each open a `generation` span (via `langfuse_client.start_observation(as_type="generation", ...)`, **not** the older `@observe()`-decorator-only or manual `trace()`/`generation()` context-manager APIs some tutorials describe — the SDK went through a major v3→v4 rework, now OpenTelemetry-based; verified via context7 before writing this, not assumed from training data) around the `tool_runner` call, closed at every exit point via the shared `_lf_finish()` helper, which never lets a Langfuse SDK failure break the actual chat response. `langfuse_client.flush()` runs at shutdown (`lifespan()`) since spans are batched and sent on a background timer — without an explicit flush, whatever's still queued at shutdown is lost.

**SpendGaugeAI reporting** — set `SPENDGAUGEAI_URL` and `SPENDGAUGEAI_API_KEY` in `.env` to report every request's usage to a running [SpendGaugeAI](https://github.com/vijayanan6/SpendGaugeAI) instance (a separate, standalone sibling project — see its own `docs/DESIGN.md` §10). Same optional-feature pattern as Langfuse, with one more layer: `spendgauge_client` is `None` if the env vars aren't set *or* if the `spendgaugeai` package isn't installed (it's intentionally not a hard dependency in `requirements.txt` — `pip install spendgaugeai` or `pip install -e ../SpendGaugeAI` to opt in). `_spendgauge_report()` is called in both `/chat` and `/stream`, wrapped in its own try/except (on top of `SpendGaugeAIClient.alog()`'s own internal silent-failure guarantee — belt and suspenders, matching this file's other optional integrations) so a SpendGaugeAI outage can never break a real chat response. As of 2026-07-19 this is the **only** usage/cost/alert reporting path this project has — its own local `usage_log()`/`/usage` dashboard was removed in favor of it (see § Cost Dashboard & Credit Tracking above).

## SSL Note (Windows)

Two SSL patches are applied on Windows machines with corporate certificate chains or network monitoring drivers:

1. **`rag.py`** — patches `httpx.Client.__init__` and `httpx.AsyncClient.__init__` to default `verify=False` before the HuggingFace model download. The model (~80MB) is cached after first download.
2. **`api.py` lifespan** — clears the `SSLKEYLOGFILE` environment variable (set by monitoring drivers like `nllMonFltProxy`) and passes `httpx.AsyncClient(verify=False)` explicitly to `AsyncAnthropic()` to prevent SSL context creation failures.

## .env Encoding Note (Windows)

`.env` must be saved as plain **UTF-8 (no BOM)**. Windows tools (Notepad, some PowerShell
`Set-Content`/`Out-File` defaults) commonly save "UTF-8 with BOM" instead. The BOM character
silently merges with the first line, turning `ANTHROPIC_API_KEY` into an unrecognized variable
name — `python-dotenv` never loads it, and the SDK fails with a generic
`"Could not resolve authentication method"` error even though the key itself is correct.

Verify without exposing the key: `grep -c "^ANTHROPIC_API_KEY=" .env` should return `1`. If it
returns `0`, strip the BOM:
```powershell
$content = Get-Content -Raw -Path .env
[System.IO.File]::WriteAllText(".env", $content, (New-Object System.Text.UTF8Encoding $false))
```
Note `uvicorn --reload` does not watch `.env` for changes — a full process restart is required
after fixing it.

## Playwright MCP (UI Testing)

A Playwright MCP server is configured at project scope in `.mcp.json` (Microsoft's official
`@playwright/mcp` package, no secrets in config, safe to share). It lets Claude Code drive
`chat.html` and `usage.html` in a real browser — navigate, click, type, screenshot — to verify
UI changes actually work, per the testing standard in this file, instead of only reading source.

Screenshots and page snapshots land in `.playwright-mcp/` — gitignored, since they can contain
session IDs and cost data from local testing.

## Security Standard — After Every Change

After any file edit, new dependency, new MCP server, or config change: check `git status` for
new untracked files, confirm nothing secret is in what's about to be committed, and confirm
`.gitignore` covers any new artifact-producing tool (test output, logs, generated screenshots).
Never print a secret value to diagnose it — use structural checks (`grep -c`, redacted `sed`)
instead. This applies to every change in this repo, not just app code.

## Secret Scanning & Commit Signing

A `gitleaks` pre-commit hook lives at `.git/hooks/pre-commit` (local only — not tracked or
shared via clone, like all git hooks). It runs `gitleaks protect --staged --redact --verbose`
on every `git commit`, scanning only what's staged, and blocks the commit (non-zero exit) if a
likely secret is found. `--redact` means it reports *where* a secret was found, never the value
itself. If it ever blocks a false positive, add an allowlist rule to a `.gitleaks.toml` file
(not currently present — only needed if a false positive occurs).

All commits are also SSH-signed (`git config --global commit.gpgsign true`, `gpg.format ssh`,
signing key at `~/.ssh/git_signing_key`) — this is a **global** git config, not scoped to this
repo, so it applies to every repo on this machine. Signed commits show a green "Verified" badge
on GitHub. Verify signing status with `gh api repos/<owner>/<repo>/commits/<sha> --jq
'.commit.verification'` rather than `git log --show-signature`, which reports `No signature`
locally unless `gpg.ssh.allowedSignersFile` is separately configured — that's a local display
limitation, not a sign the commit is actually unsigned.

Run `pip-audit` periodically to check installed dependencies for known CVEs. On this machine,
`pip-audit`'s PyPI lookups fail with `CERTIFICATE_VERIFY_FAILED` due to corporate SSL
interception (same root cause as the SSL Note above, but a different fix — `pip` itself isn't
affected, only `requests`/`urllib3`-based tools are). Fixed once via `pip install
pip_system_certs`, which makes Python defer to the Windows certificate store instead of
`certifi`'s bundled CA list. When a scan flags a CVE, check whether this project's code actually
exercises the vulnerable code path before treating it as actionable — e.g. a ChromaDB RCE
advisory affecting its standalone HTTP server API doesn't apply here, since `rag.py` only uses
`chromadb.PersistentClient` (embedded, no network listener).

## Git Workflow

See `GIT_COMMANDS.md` for the full reference. Standard workflow:

```powershell
git checkout -b feature/name     # new feature branch
git add .
git commit -m "feat: description"
git checkout main
git merge feature/name
git push origin main
```

Commit prefix conventions: `feat:` new feature — `docs:` documentation — `fix:` bug fix

## Eval Pipeline

`evals/dataset.json` — 12 test cases covering tool selection and model routing
`evals/run_evals.py` — runner that calls `/chat`, scores results, exits 1 on failure

Currently passing: **12/12 (100%)**

Run after every system prompt change or model routing change to catch regressions.

## Documentation Files

`README.md` and `CLAUDE.md` stay at the project root by convention; the rest live in `docs/`:

| File | Purpose |
|---|---|
| `README.md` (root) | Project overview and setup |
| `docs/ARCHITECTURE.md` | System design in plain English |
| `docs/LEARNING_JOURNEY.md` | Phase-by-phase build record |
| `docs/INSIGHTS.md` | Key lessons and principles |
| `docs/TUTORIAL.md` | Beginner teaching guide with exercises |
| `docs/GIT_COMMANDS.md` | All Git commands used with explanations |
| `docs/AI_ENGINEERING_PORTFOLIO.md` | LinkedIn/GitHub portfolio of skills |
| `docs/LEARNING_PLAN.md` | Forward-looking curriculum/roadmap |
| `docs/AI_ENGINEERING_TEACHING_ASSISTANT.md` | Teaching-assistant plugin design doc |
| `docs/LINKEDIN_POSTS.md` | LinkedIn drafts — gitignored, personal |

## Key Dependencies

| Package | Purpose |
|---|---|
| `anthropic[mcp]` | Anthropic SDK + `async_mcp_tool` bridge |
| `mcp` | MCP server/client protocol implementation |
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI web server |
| `pypdf` | Text extraction from text-based PDFs |
| `pymupdf` | Renders PDF pages to images for OCR |
| `pytesseract` | Python wrapper for Tesseract OCR |
| `chromadb` | Vector database for semantic search |
| `sentence-transformers` | Local embedding model (all-MiniLM-L6-v2) |
| `python-dotenv` | Loads `.env` file into environment variables |
| `httpx` | HTTP client used by eval runner and Anthropic SDK |
