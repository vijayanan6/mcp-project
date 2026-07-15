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

**`src/backend/mcp_server.py`** — MCP server with 8 tools. No knowledge of Claude or HTTP. Notes stored in SQLite via `database.py`. Document search via `rag.py` + ChromaDB.

**`src/backend/text_editor_tool.py`** — `ProjectNotesEditorTool`, a client-side Anthropic builtin tool (`BetaAsyncBuiltinFunctionTool`) executed in-process by `api.py`, not via MCP.

**`src/backend/agent.py`** — Original CLI version. Same MCP connection logic as `api.py` but uses `input()` instead of HTTP.

```
Browser ──HTTP/SSE──► api.py ──stdio/JSON-RPC──► mcp_server.py (8 tools)
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

## Image + PDF Attachments (Chat)

Not an MCP/server-side/client-side tool like the 10 above — this is a native Anthropic Messages API content-block feature (vision + document), wired directly into `/chat` and `/stream`. `ChatRequest.attachment` (`Attachment` model: `media_type`, `data` base64, optional `filename`) carries at most one image or PDF per turn.

**Ephemeral by design:** `history` (what `session_save()` persists to SQLite) only ever receives plain text from `_history_text_for()` — the message plus a `[User attached a file: name]` marker, never the base64 binary. The multimodal content block only exists in the locally-built `api_messages` list from `_build_api_messages()`, used for that one `tool_runner` call and discarded after. A later turn in the same session has no way to re-see the file unless it's re-attached — confirmed via SQLite inspection during testing (every persisted `content` field is a plain string).

**Validation:** `_validate_attachment()` raises `HTTPException(400)` before any state changes for an unsupported `media_type` (allowlist: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `application/pdf`), invalid base64, or oversized payload (`_MAX_IMAGE_ATTACHMENT_BYTES` = 5MB, matching Anthropic's own image limit; `_MAX_PDF_ATTACHMENT_BYTES` = 10MB). In `/stream`, this validation runs in `stream_chat()`'s body *before* `StreamingResponse` is constructed, so a 400 comes back as a normal JSON error, not a broken SSE stream — the frontend's `send()` in `chat.html` checks `!res.ok` before parsing SSE for exactly this reason.

**Citations (PDF only):** `_attachment_content_block()` adds `citations: {enabled: true}` to `document`-type blocks (not `image` blocks — citations don't apply to images). When Claude cites a specific page, both endpoints append an inline `(p.N)` marker to the response text by reading `start_page_number` directly off each citation object. **Gotcha found during testing:** the citation object's location fields are flat with a `type: "page_location"` discriminator string — not nested under a `.page_location` sub-attribute the way the field name might suggest. Also: citations only work against a PDF with a real embedded text layer — a purely rasterized/image-based PDF (e.g. one built by saving images via Pillow) has nothing for Claude to cite against, which is correct behavior, not a bug.

**No new cost-tracking code needed** — image/PDF tokens bill as ordinary `input_tokens` in the API response, already captured by the existing `usage_log()` → `_estimate_cost()` pipeline. Confirmed during testing: a PDF-attached turn showed `2814 in` vs. `1002 in` for a plain-text follow-up in the same session, and the `/usage` totals picked up the difference automatically.

**Frontend (`chat.html`):** a 📎 button + hidden `<input type="file">` in the footer, client-side allowlist/size checks mirroring the backend exactly, and a filename chip with a remove (×) control. Drag-drop/paste and multiple attachments per turn are explicitly out of scope for now — file-picker, one file, is the only supported flow.

## Cost Dashboard & Credit Tracking

`GET  /usage`         — visual HTML dashboard (token usage, cost, daily chart, per-session table)
`GET  /usage/data`    — JSON: totals, by_model, by_day, by_session, by_tool, by_project, credit config
`GET  /usage/data?project=name` — same but filtered to one project
`POST /usage/credit`  — save starting balance and alert threshold `{ starting_balance: 5.00, alert_threshold: 1.00, reset: false }`

Features: credit balance tracker, burn rate ($/day), estimated runway (labeled "Est. Runway" — a burn-rate forecast, not an actual credit expiration; API credits don't expire on a day count), 30/60/90-day cost forecast, per-session cost table, cost by tool, cost by project, low-credit alert badge in chat header (pulses red when remaining < threshold).

**Pricing table maintenance:** `database.py`'s `_PRICING` dict is a manual snapshot — Anthropic's API has no endpoint that returns live pricing (the Models API returns capabilities/context window, not cost). Found stale on 2026-07-15: `claude-haiku-4-5` carried old Haiku-3.5-era rates ($0.0008/$0.004 per 1K instead of the correct $0.001/$0.005), undercounting every Haiku-routed request by ~20%, caught only by comparing the dashboard's "remaining" balance against the real console.anthropic.com figure — fixed, and all 44 affected historical rows in `usage_logs` were recomputed and backfilled (not just fixed going forward). Re-verify `_PRICING` by hand against console.anthropic.com/settings/billing (or the claude-api skill's Current Models table) whenever Anthropic changes pricing, or whenever `_pick_model()` starts routing to a model not yet in the dict. `_estimate_cost()`'s fallback for an unrecognized model now prints a console warning instead of silently inheriting Sonnet's rate — that silent fallback is exactly what let the Haiku drift go unnoticed.

**web_search cost tracking:** `web_search` is billed at $10 per 1,000 searches ($0.01/use) on top of normal token costs — a flat server-side fee, not derivable from token counts. `usage_logs.web_search_requests` (read from `usage.server_tool_use.web_search_requests` on each turn) stores the raw count; `_estimate_cost()` in `database.py` folds `web_search_requests × $0.01` into `estimated_cost_usd`, so it flows automatically into every existing aggregate (by_model, by_day, by_session, by_tool, by_project, credit/burn-rate math) with no separate dashboard wiring. The "Web Searches" stat card on `/usage` surfaces the raw count.

### Discord Mobile Alerts

The in-dashboard badge only helps if the browser tab is open. `_run_alert_checks()` in `api.py` runs after every logged request (`/chat` and `/stream`) and pushes real-time alerts to a Discord webhook — Discord's mobile app turns these into phone push notifications, so alerts reach you without the dashboard open.

**Config:** `DISCORD_WEBHOOK_URL` in `.env` (optional — every check silently no-ops if unset). No other secret involved; email was deliberately skipped as a channel — it needs a heavier credential (SMTP/app password) for a channel that isn't checked. The URL lives only in `.env` (gitignored), read via `os.environ`, never stored in SQLite or returned by any API endpoint.

**Four alert types, each independently cooldown-gated so none of them can spam Discord:**

| Alert | Trigger | Cooldown | Config |
|---|---|---|---|
| 🟡 Warning (low balance) | `remaining ≤ warning_threshold` (and above critical) | 24h, clears on recovery above `warning_threshold` | `credit_config.warning_threshold`, default $5 |
| 🔴 Critical (low balance) | `remaining ≤ alert_threshold` | 24h, clears on recovery above `alert_threshold`; also clears a stale warning cooldown (critical supersedes warning) | `credit_config.alert_threshold`, default $1 — same field the dashboard badge already uses |
| 📈 Spend spike | Today's spend ≥ `SPIKE_MIN_ABSOLUTE` ($1) **and** ≥ `SPIKE_MULTIPLIER` (3×) the trailing 7-day daily average | Once per calendar day | Constants in `api.py` — catches a runaway loop or bug *causing* spend, not just the low balance that results from it |
| 🔎 web_search budget | `web_search`'s cost alone (exact, via `web_search_requests × $0.01`) exceeds `WEB_SEARCH_DAILY_BUDGET` ($1) for the day | Once per calendar day | Constant in `api.py` |
| 📋 Daily digest | First request of a new calendar day | Once per calendar day | N/A — fires with yesterday's spend/tokens/top-tools recap, plus an "Available credit" line (same `remaining` formula as the dashboard banner) when credit tracking is configured (`starting_balance > 0`) |

**Why the digest fires on first-request-of-the-day, not a fixed time:** this app only runs when `uvicorn` is started — there's no guarantee it's running at any fixed wall-clock time, so a background scheduler (e.g. APScheduler firing at 8am) could silently miss days entirely. Piggybacking on real traffic means the digest always eventually fires, just possibly later than a fixed hour on light-usage days.

**`warning_threshold` is stored but not yet in the dashboard UI** — change it via `POST /usage/credit` with `{"warning_threshold": N}` (omit the field entirely to leave it unchanged; the existing dashboard form doesn't send it, so it can't accidentally reset it).

**Two-tier low-balance logic (`_maybe_send_low_credit_alert`) mirrors the exact "remaining" formula the dashboard banner uses** (`usage.html`): `remaining = max(starting_balance - period_cost_usd, 0)`. Critical is checked first — being in the critical zone skips the warning tier entirely (it would be a redundant, less-urgent duplicate).

### Resetting Spend Tracking (Balance Top-Ups)

A real Anthropic account top-up doesn't mean past spend should keep counting against the new balance. The "Reset spend tracking" checkbox in the credit banner (with a confirm prompt, since it overwrites the single archived snapshot below) sets `reset: true` on `POST /usage/credit`, which:

- Starts a new tracking period from now (`credit_config.period_start`) — remaining balance, burn rate, and forecasts recalculate from that point forward.
- Archives the outgoing period's totals into `prev_period_cost_usd` / `prev_period_days` / `prev_period_end` — a **single slot**, overwritten on every reset. There's a confirm dialog specifically because this data isn't recoverable if you reset twice in a row.
- **Never touches `usage_logs`.** All historical charts (daily chart, per-model, per-session, per-project tables) always show full lifetime data regardless of resets — only the credit banner's live remaining/burn-rate math is period-scoped.

`database.py`'s `credit_status(project=None)` computes the live period's spend/active-days (falling back to all-time totals if never reset, so existing installs behave unchanged). The dashboard JS falls back to the *previous* period's burn rate — marked `(est.)` with a tooltip — for forecasting in the gap right after a reset, before any usage has landed in the new period; it switches to real numbers once a request is logged.

## Multi-Project Support — How to Wire Up a New Project

This dashboard supports multiple projects reporting to a single SQLite database. All data is tagged by `project` column in `usage_logs`.

**To add a second project:**

1. Copy `src/backend/database.py` into the new project (or import it as a shared module)
2. Point `DB_PATH` to the same `data.db` file used by this project:
   ```python
   DB_PATH = Path("c:/Users/vijay/OneDrive/Desktop/Claude Workspace/MCP Project/data/data.db")
   ```
3. In the new project's streaming endpoint, pass the project name to `usage_log()`:
   ```python
   usage_log(session_id, model, input, cache_write, cache_read, output,
             tools=tools_called, project="my-new-project")
   ```
4. That's it — the new project appears in the dashboard dropdown automatically.

**Filter in dashboard:** Use the Project dropdown in the header to view one project at a time. All cards, charts, and tables filter to the selected project.

**Future upgrade path:** When deployed to GCP, replace the shared file path with a `POST /usage/log` endpoint so any project anywhere can report usage over HTTP — this is Option A (centralised dashboard). Option C (shared file) works locally; Option A works in production.

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
