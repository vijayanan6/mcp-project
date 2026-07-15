# Learning Plan — AI Engineering Roadmap

Personal learning roadmap based on the MCP Learning Project foundation.
Track progress by checking off items as completed.

Last updated: July 2026

---

## Current Position

### Completed ✅
- [x] Python (intermediate)
- [x] MCP (Model Context Protocol) — server, tools, stdio transport
- [x] FastAPI — web server, SSE streaming, lifespan, Pydantic
- [x] SQLite — persistence, CRUD, sessions, schema migration
- [x] ChromaDB — vector database, embeddings
- [x] RAG — chunking, semantic search, sentence-transformers
- [x] PDF processing — pypdf (text), Tesseract OCR (scanned)
- [x] Git + GitHub — branches, commits, pull requests
- [x] GCP concepts — Cloud Run, Cloud SQL, Secret Manager, IAM, VPC (theory)
- [x] Token economics — input / cache_write / cache_read / output pricing, why caching matters
- [x] LLM cost observability — usage_logs table, cost estimation, per-session and per-tool breakdown
- [x] Prompt caching — cache_control ephemeral, cache hit rate, burn rate calculation
- [x] Model routing — Haiku vs Sonnet cost tradeoff, signal-based routing heuristics
- [x] Prompt evaluation — evals/dataset.json, run_evals.py, 12/12 passing
- [x] Evaluating third-party MCP servers before install — publisher trust, access boundary, prompt-injection risk surface, project vs user scope
- [x] Playwright MCP — browser automation for UI testing, wired into Claude Code at project scope
- [x] Tool use fundamentals — `tool_choice` modes, forced tool calls, streaming tool_use blocks (beneath `tool_runner`)
- [x] Anthropic-native tools beyond MCP — server-side (`web_search`, no local execution) vs. client-side (`BetaAsyncBuiltinFunctionTool`, local execution) vs. MCP; found and fixed a real multi-model tool-capability bug in production
- [x] Multi-channel alerting with stateful cooldowns — Discord webhook alerts, tested at the state *transitions* (not just each state), designed around actual runtime guarantees instead of the textbook scheduler pattern
- [x] MCP Inspector — launched via `npx @modelcontextprotocol/inspector python src/backend/mcp_server.py`, connected past the proxy auth-token prompt, tested at least one tool directly against the running server, no Claude API call needed

### Not Yet Started ❌
- [ ] pytest — testing framework for MCP tools and FastAPI routes
- [ ] MCP resources & prompts — the two MCP primitives beyond tools
- [ ] Docker
- [ ] GCP hands-on deployment
- [ ] React frontend
- [ ] PostgreSQL
- [ ] Authentication (JWT / Firebase)
- [ ] Advanced AI engineering (Langfuse, LangChain)

---

## Pre-Docker — Foundation Gaps (1–2 Weeks)
**Goal: Fill the gaps that every production AI engineer is expected to know**

### Prompt Engineering Fundamentals
- [x] Understand system prompt design — how Claude reads and prioritises instructions
- [x] Learn few-shot prompting — giving Claude examples inside the prompt to shape behaviour (applied to `SYSTEM_PROMPT`; found and fixed a lexical-overlap regression — see Phase 15)
- [ ] Learn chain-of-thought prompting — asking Claude to reason step by step before answering (covered conceptually — deliberately not applied to this routing prompt; CoT's token/latency cost isn't justified for a simple tool-routing decision)
- [x] Understand prompt injection — how users can hijack your system prompt and how to defend against it (direct: user hijacks own chat; indirect: malicious text in a retrieved doc — the real risk for `search_docs`/`read_doc`. Defended via `<security>` tag in `SYSTEM_PROMPT` telling Claude tool results are data, not instructions — see `api.py`)
- [x] Practice iterating on prompts and measuring behaviour change (rewrote prompt → eval regressed 12/12 → 10/12 → diagnosed root cause → fixed)
- [x] Understand the difference between system prompt, user turn, and assistant turn
- [x] Learn role prompting — giving Claude a scoped persona/job in the system prompt (not just "a helpful assistant") to reduce ambiguous behaviour at the edges
- [x] Learn XML tag structuring — wrapping instructions, examples, and rules in tags (`<instructions>`, `<examples>`, `<rules>`) so Claude parses precedence reliably as a prompt grows past one prose block
- [x] Learn response prefilling — the classic technique (seeding the assistant turn with `{` to force JSON) now returns a hard 400 on current models (Sonnet 4.6/5, Opus 4.6+, Fable 5) — confirmed `claude-sonnet-4-6` is in the blocked list, meaning it would break mid-router-switch in this app. Modern replacement, verified supported on both routed models (`claude-sonnet-4-6`, `claude-haiku-4-5`) via a live Models API capability check: `output_config.format` / `client.messages.parse()` with a Pydantic model — this is what Phase 5 (Structured Outputs) will actually use
- [x] Understand **context engineering** as the broader term the industry now uses — not just the prompt text, but everything that ends up in the context window: system prompt, conversation history, RAG-retrieved chunks, and tool results. "Prompt engineering" is one piece of the larger discipline of deciding what Claude sees and when (mapped each category to real code: `SYSTEM_PROMPT`, `HISTORY_LIMIT`, `search_docs` chunking, `read_doc`'s 8000-char cap, and `_safe_window()`'s tool_use/tool_result pairing — every cap in the app is a context-engineering tradeoff)
- [x] Understand what cosine similarity actually measures — why two chunks of text with similar *meaning* end up as vectors that point in a similar *direction*, and why that's what makes `search_docs` work (verified `rag.py`'s ChromaDB collection defaults to `hnsw:space="cosine"` via `SentenceTransformerEmbeddingFunction.default_space()`, confirming `score = 1 - distance` at [rag.py:175](rag.py#L175) is literal cosine similarity; demoed with zero-keyword-overlap sentences scoring 0.556 vs 0.09)
- [x] Understand extended/adaptive thinking (`thinking: {"type": "adaptive"}` on `tool_runner`) and deliberately decide *not* to apply it to this project's tool-routing prompt — evaluated where it would go (`api.py`'s `/chat` and `/stream` tool_runner calls), and found two blockers: (1) tool-routing is a shallow classification decision, not the multi-step reasoning problem thinking is built for — no accuracy gain to justify the added latency/cost; (2) `_pick_model()`'s Haiku/Sonnet router recreates the exact multi-model capability trap from Insight #27 (`web_search`) — adaptive thinking isn't supported on Haiku 4.5 at all, and the legacy `budget_tokens` fallback needs more headroom than this app's `max_tokens=1024` allows, so declaring it uniformly would silently break every Haiku-routed request

**Success check:** Rewrite your system prompt using chain-of-thought and few-shot patterns, then eval the difference in tool selection accuracy

---

### Tool Use Fundamentals (API-Level, Beneath `tool_runner`) ✅
- [x] Understand the raw `tool_use` / `tool_result` content block format that `tool_runner` abstracts away
- [x] Learn `tool_choice` modes: `auto` (model decides, default), `any` (must call some tool), `tool` (force one specific tool), `none` (disable tool use for this call)
- [x] Practice forcing a specific tool call with `tool_choice: {"type": "tool", "name": "..."}` and observe the difference vs `auto` (`tool_use_demo.py` — same ambiguous prompt answered directly under `auto`, forced into calling `get_weather` under `tool_choice: {"type": "tool", ...}`, inferring a best-guess argument rather than refusing)
- [x] Understand `disable_parallel_tool_use` — when you'd want to prevent Claude from calling multiple tools in a single turn (demoed: `tool_choice: any` on a two-tool prompt called both tools in one turn; adding `disable_parallel_tool_use: True` collapsed it to one)
- [x] Understand streaming tool use — how tool call arguments arrive as incremental JSON deltas (`input_json_delta`) rather than all at once (watched raw fragments assemble into valid JSON only once the block closed)
- [x] Manually construct one multi-turn tool loop without `tool_runner` — build the follow-up request with a `tool_result` block yourself, to see exactly what the SDK automates (`tool_use_demo.py` §5 — save-then-read note loop, verified the SQLite write with `inspect_db.py`)

**Result: all 6 items demoed hands-on in `tool_use_demo.py` — can explain what `tool_runner` does under the hood, and can force Claude to call a specific tool via `tool_choice` instead of relying on prompt wording alone**

---

### Anthropic-Native Tools — Server-Side & Client-Side, Beyond MCP ✅
- [x] Understand the 3 tool execution models sharing one `tools` array: MCP (your own subprocess), server-side (Anthropic executes entirely — `web_search`), client-side builtin (`BetaAsyncBuiltinFunctionTool` — Claude requests, your process executes)
- [x] Implement a server-side tool — `web_search`, declared as a plain dict, no local handler needed
- [x] Implement a client-side builtin tool — `text_editor_tool.py`'s `ProjectNotesEditorTool`, implementing `to_dict()` + `call()`, hard-confined to editing exactly one file with path-equality checks (not just prefix/`is_relative_to` checks against a folder)
- [x] Recognize that server-side tool calls arrive as `server_tool_use` content blocks, a different type than `tool_use` — code that only pattern-matches one type silently drops the other
- [x] Recognize that declaring a tool is a capability commitment to *every* model a router can select, not just the one that ends up calling it — `web_search`'s default config broke every Haiku-routed request in this project, regardless of whether that request needed search

**Result: real production bug found and fixed (multi-model tool-capability mismatch), plus a cost-tracking gap (server_tool_use vs tool_use) — both documented in `INSIGHTS.md` #26–27 and `LEARNING_JOURNEY.md` Phase 19**

---

### Error Handling & Resilience
- [ ] Handle Anthropic API rate limit errors (429) with exponential backoff retry
- [ ] Handle API timeout errors gracefully — return a user-friendly message, not a 500
- [ ] Handle MCP server crashes — detect and restart automatically
- [ ] Add fallback behaviour when `search_docs` returns no results
- [ ] Never let an unhandled exception reach the user — always return a clean error SSE event
- [ ] Understand circuit breaker pattern — stop calling a failing service temporarily

**Success check:** App handles API rate limits, timeouts, and MCP crashes without crashing or showing raw tracebacks to the user

---

### Security Fundamentals for AI Apps
- [x] Understand prompt injection — user input that overrides your system prompt (see Prompt Engineering Fundamentals above)
- [x] Sanitise user input before passing to Claude — strip control characters, cap length (`_sanitize_input()` in `api.py`, applied in both `/chat` and `/stream`)
- [ ] Validate all tool inputs in `mcp_server.py` — never trust Claude's arguments blindly
- [ ] Understand path traversal — already implemented in `read_doc`, understand why it matters
- [ ] Never expose raw error messages to the browser — they leak implementation details
- [ ] Understand OWASP Top 10 for AI applications

**Success check:** Can explain 3 AI-specific attack vectors and point to where your app defends against each

---

### Environment Management (dev / staging / prod)
- [ ] Understand why dev, staging, and prod must be separate environments
- [ ] Use `.env.development`, `.env.production` with different API keys and DB paths
- [ ] Never use prod data or credentials in development
- [ ] Understand environment variables vs secrets management (Secret Manager in GCP)
- [ ] Add environment name to logs so you always know which environment generated a log line

**Success check:** App runs correctly with a dev `.env` and a prod `.env` — switching between them changes behaviour without code changes

---

### Testing with pytest
- [ ] Install pytest and pytest-asyncio (`pip install pytest pytest-asyncio httpx`)
- [ ] Understand the difference between unit tests and integration tests
- [ ] Write tests for each MCP tool in `mcp_server.py`
- [ ] Write async tests for FastAPI routes using `httpx.AsyncClient`
- [ ] Test edge cases: bad input, missing files, empty notes
- [ ] Run tests with `pytest -v` and read coverage output
- [ ] Understand why testing AI systems is different from testing deterministic code — an LLM call with `temperature > 0` won't return the same string twice, so tests need to check *behavior* (did it call the right tool? is the answer within expected bounds?) instead of exact output matching
- [ ] Write at least one test that asserts on structure/behavior rather than exact text (e.g. "response contains a valid note ID" not "response equals this exact string")

**Success check:** `pytest` passes with tests covering all 8 MCP tools and the main API routes, including at least one test that correctly handles non-deterministic output

---

### Prompt Evaluation (Evals) ✅
- [x] Understand what evals are and why they differ from unit tests
- [x] Build an eval dataset (JSON) covering system prompt instructions — tool selection, model routing, edge cases
- [x] Write an eval runner that scores tool selection (did Claude call the right tool?)
- [x] Run evals after every system prompt change to catch regressions
- [ ] Implement LLM-as-judge to score open-ended response quality
- [ ] Explore Promptfoo (open source) as an eval framework
- [ ] Add RAG-quality evals, not just tool-selection evals — current evals check *did Claude call `search_docs`*, not *was the retrieved chunk actually correct, or was the answer faithful to it*
- [ ] Learn the 3 core RAG metrics (the RAGAS framework popularized these): **faithfulness** (is the answer supported by the retrieved chunk, or did Claude make something up?), **context precision/recall** (did `search_docs` retrieve the right chunk, and only the right chunk?), **answer relevancy** (does the answer actually address the question asked?)
- [ ] Write at least 3 test cases that check retrieval quality directly against `docs/` content, not just whether a tool was called

**Result: 12/12 (100%) passing — evals/dataset.json + evals/run_evals.py**

---

### MCP Resources & Prompts ✅
- [x] Understand the 3 MCP primitives: tools (actions), resources (data), prompts (templates)
- [x] Add a resource to `mcp_server.py` that exposes the `knowledge_base/` folder listing (`knowledgebase://files` — adapted from `docs/` per the Phase 22 reorg; also learned URI schemes can't contain underscores, RFC 3986, caught via a real `pydantic.AnyUrl` validation error)
- [x] Add a resource that exposes a single note by URI (`note://<title>` — adapted from the plan's `note://1` example since notes are keyed by `title`, not a numeric ID; verified URL-encoding round-trips correctly for spaces/mixed case/slashes)
- [x] Add a prompt template for summarising a document (`summarize_document`, drives the existing `read_doc`/`search_docs` tools)
- [x] Test resources and prompts via MCP Inspector (plus a direct MCP client script, since Inspector's browser proxy auth blocked automated verification)

**Result: all three MCP primitives now live in `mcp_server.py` — 8 tools, 2 resource kinds, 1 prompt — verified end-to-end**

---

### Observability & Logging (Partially complete ✅)
- [x] Track token usage per request — input, cache_write, cache_read, output
- [x] Track cost per request — estimated USD using pricing table
- [x] Track tool calls per request — stored as JSON array in usage_logs
- [x] Build visual cost dashboard — daily chart, model split, per-session, per-tool
- [x] Credit tracker — starting balance, burn rate, days remaining, alert badge
- [x] Multi-channel/multi-tier alerting — Discord webhook push (mobile-reachable, unlike the passive in-browser badge): 2-tier low-balance, spend-spike anomaly detection (today vs. trailing 7-day average), per-tool budget cap, daily digest. Each independently cooldown-gated; found and fixed a real state-transition bug (stale cooldown when jumping tiers) by testing transitions, not just states.
- [ ] Add structured logging to `api.py` using Python's `logging` module (not `print`)
- [ ] Log every error with full traceback to a log file
- [ ] Understand DEBUG / INFO / WARNING / ERROR / CRITICAL log levels
- [ ] Add request latency tracking — how long does each `/stream` call take?
- [ ] Explore Langfuse free tier — trace every Claude API call end to end

**Success check:** Every request and error is logged with structured fields. Langfuse shows token usage and latency per conversation turn

---

### Rate Limiting & API Quota Handling
- [ ] Understand Anthropic's rate limits — requests per minute, tokens per minute, tokens per day
- [ ] Implement exponential backoff retry on 429 (rate limit) errors
- [ ] Add a request queue so burst traffic doesn't immediately hit rate limits
- [ ] Display a user-friendly "Claude is busy, retrying..." message instead of an error
- [ ] Track token usage per session to warn when approaching limits

**Success check:** App handles a burst of 10 rapid messages gracefully without crashing or showing raw API errors

---

### CI/CD Pipeline
- [ ] Understand what CI/CD is and why every production team uses it
- [ ] Set up GitHub Actions workflow that runs `pytest` on every push
- [ ] Add eval suite to CI — block merge if evals fail
- [ ] Add a deploy step that pushes to Cloud Run on merge to `main`
- [ ] Understand the difference between continuous integration and continuous deployment

**Success check:** Pushing to GitHub automatically runs tests + evals. Failing tests block the push

---

### AI System Design Practice
- [ ] Understand this is a distinct interview skill — reasoning through tradeoffs out loud, without writing code, not the same as *building* the thing
- [ ] Practice designing (on paper/whiteboard, not code): "design a RAG system for searching legal documents" — chunking strategy, vector DB choice, caching, fallback behaviour
- [ ] Practice designing: "design a multi-tenant AI support agent" — data isolation, cost tracking per tenant (you've built this part), rate limiting per tenant
- [ ] Practice designing: "design a system to safely roll out a new system prompt to production" — versioning, canary rollout, rollback
- [ ] For each design, be able to name the failure modes and how you'd detect them (this project's own observability dashboard is a real answer to "how would you detect it")

**Success check:** Can talk through 2–3 AI system design scenarios out loud in under 10 minutes each, referencing real tradeoffs from this project as evidence

---

## Phase 1 — Deploy to GCP (Weeks 1–6)
**Goal: Get your existing MCP app live on GCP**

### Week 1–2: Docker
- [ ] Install Docker Desktop (`winget install Docker.DockerDesktop`)
- [ ] Understand Dockerfile syntax
- [ ] Write `Dockerfile` for `api.py`
- [ ] Write `Dockerfile` for `mcp_server.py`
- [ ] Write `docker-compose.yml` to run both together
- [ ] Run the full app locally with Docker Compose
- [ ] Understand the difference between image and container

**Success check:** `docker-compose up` starts both services and the chat UI works at `http://localhost:8000`

---

### Week 3–4: GCP Cloud Run
- [ ] Install Google Cloud CLI (`gcloud`)
- [ ] Create a GCP project
- [ ] Enable required APIs (Cloud Run, Artifact Registry, Cloud Build)
- [ ] Push Docker images to Artifact Registry
- [ ] Deploy `api.py` to Cloud Run
- [ ] Deploy `mcp_server.py` to Cloud Run
- [ ] Connect them via environment variable URL
- [ ] Test the live URL

**Success check:** App is live at a `*.run.app` URL and fully working

---

### Week 5–6: GCP Services
- [ ] Create a Secret Manager secret for `ANTHROPIC_API_KEY`
- [ ] Update `api.py` to read from Secret Manager
- [ ] Create a Cloud Storage bucket for `docs/`
- [ ] Update `mcp_server.py` to read docs from GCS
- [ ] Create a Cloud SQL PostgreSQL instance
- [ ] Migrate `database.py` from SQLite to PostgreSQL
- [ ] Connect Cloud Run to Cloud SQL via Cloud SQL Auth Proxy
- [ ] View structured logs in Cloud Logging
- [ ] Set up a budget alert for GCP costs

**Success check:** App running on Cloud Run with PostgreSQL, docs in GCS, API key in Secret Manager

---

## Phase 1.5 — Claude Code Plugin Marketplace (Optional Interlude, ~1 Week)
**Goal: Learn Claude Code's real plugin/marketplace system — directly transferable to contributing
to your company's internal marketplace**

This uses Claude Code's actual marketplace mechanism (not a custom npm registry — GitHub hosting
is the standard approach, so this maps 1:1 to a real internal marketplace repo).

### Build one plugin
- [ ] Create a plugin directory with `.claude-plugin/plugin.json` (`name`, `description`,
      optionally `version`, `author`, `homepage`)
- [ ] Add a skill: `skills/<skill-name>/SKILL.md` with YAML frontmatter (`description` is
      required — it's what tells Claude when to invoke the skill)
- [ ] Test `disable-model-invocation: true` on one skill so it only runs via explicit
      `/plugin-name:skill-name` invocation, and leave another auto-invoked — compare the difference
- [ ] Use `$ARGUMENTS` in a skill to accept user input after invocation
- [ ] Test the plugin locally before publishing anywhere

### Build the marketplace
- [ ] Create a GitHub repo with `.claude-plugin/marketplace.json` at the root
      (required fields: `name`, `description`, `plugins` array)
- [ ] Reference your plugin in the `plugins` array via a `source` (subdirectory in the same
      repo, or a separate repo entirely)
- [ ] Add the marketplace: `/plugin marketplace add <owner>/<repo>`
- [ ] Install your plugin from it: `/plugin install <plugin-name>@<marketplace-name>`
- [ ] Verify the skill namespace shows up correctly (`<plugin-name>:<skill-name>`)
- [ ] Try `/plugin marketplace update`, `/plugin disable`, `/plugin uninstall` to understand
      the full lifecycle
- [ ] Add a second plugin to the same marketplace to see how multi-plugin catalogs work
- [ ] Set an explicit `version` (semver) in `plugin.json` and observe how that differs from
      relying on the git commit SHA

**Success check:** A teammate (or a second machine) can run
`/plugin marketplace add <owner>/<repo>` and `/plugin install <plugin-name>@<repo>` and get
your skill working with zero manual file copying

**Reference:** code.claude.com/docs/en/plugin-marketplaces.md (distribution) and
code.claude.com/docs/en/plugins-reference.md (schema)

---

## Phase 2 — React Frontend (Weeks 7–12)
**Goal: Replace chat.html with a proper React application**

### Week 7–8: React Fundamentals
- [ ] Understand components, props, state
- [ ] Learn `useState` and `useEffect` hooks
- [ ] Build a simple component from scratch
- [ ] Fetch data from your FastAPI backend
- [ ] Understand JSX syntax

---

### Week 9–10: Build the Chat UI
- [ ] Set up a React project with Vite
- [ ] Build a message list component
- [ ] Build a message input component
- [ ] Connect to `/stream` endpoint with EventSource (SSE)
- [ ] Display tool call indicators in real time
- [ ] Handle session persistence

**Success check:** Full chat interface in React matching the current `chat.html` functionality

---

### Async/Background Jobs for AI Products
Most real AI features aren't instant chat — they're "generate this report, come back in 30
seconds." This project's chat is synchronous/streaming; a lot of production AI features
(document summarisation, batch analysis, report generation) are not.
- [ ] Understand why long-running AI tasks need a job queue instead of a blocking HTTP request
- [ ] Learn one job queue pattern — Celery (general Python) or Cloud Tasks (GCP-native)
- [ ] Build one async feature: submit a job → return a job ID immediately → poll (or webhook) for the result
- [ ] Understand polling vs. webhooks vs. WebSockets for delivering the result once ready

**Success check:** One feature in your app (e.g. "summarise all my docs") runs as a background job with a status the UI can poll, instead of blocking the request

---

### Week 11–12: TypeScript + Tailwind CSS
- [ ] Add TypeScript to the React project
- [ ] Type components and API responses
- [ ] Add Tailwind CSS for styling
- [ ] Make the UI responsive (mobile-friendly)
- [ ] Deploy React app to Cloud Run or Firebase Hosting

**Success check:** A professional-looking chat interface deployed to GCP

---

## Phase 3 — Authentication (Weeks 13–14)
**Goal: Make the app multi-user with secure login**

- [ ] Set up Firebase Authentication
- [ ] Add Google login button to React frontend
- [ ] Send JWT token on every API request
- [ ] Verify JWT token in FastAPI middleware
- [ ] Add `user_id` to all PostgreSQL tables
- [ ] Isolate data per user (notes, sessions, documents)
- [ ] Protect all API routes

**Success check:** Multiple users can log in with Google and each sees only their own data

---

## Phase 3.5 — Multi-Model Capability (2 Weeks)
**Goal: Make the existing MCP project run on any LLM — Claude, Gemini, OpenAI, or a free local model. Close the one-project one-provider gap.**

### The Pattern — Model Abstraction Layer
The MCP server doesn't care what model calls it. Tools are provider-agnostic.
Only `api.py` needs to change. The abstraction goes in a new `model_client.py`:

```
api.py → model_client.py → Claude   (Anthropic SDK)
                         → Gemini   (google-generativeai SDK)
                         → OpenAI   (openai SDK)
                         → Ollama   (local, free, offline)
                         → Groq     (free tier, fast inference)
```

Switch provider via `.env`:
```
LLM_PROVIDER=claude      # or gemini, openai, ollama, groq
LLM_MODEL=claude-sonnet-4-6
```

---

### Week 1 — Provider Familiarity

**Claude (already done ✅)**

**Gemini (primary new provider — build something real)**
- [ ] Get a Google AI Studio API key (free tier available at aistudio.google.com)
- [ ] Understand Gemini model family — Flash (fast/cheap), Pro (capable), Ultra (most powerful)
- [ ] Call Gemini API using `google-generativeai` Python SDK
- [ ] Use Gemini's multimodal capabilities — send an audio file or video URL, ask questions about it
- [ ] Compare token pricing, context window, and tool use vs Claude
- [ ] Understand why Gemini + GCP is the natural pairing (same billing, IAM, Vertex AI)

**Success check:** Gemini answers a question about an audio or video file in a standalone script

---

**OpenAI (one day — familiarity only)**
- [ ] Get an OpenAI API key
- [ ] Call the API once using the `openai` Python SDK
- [ ] Compare SDK syntax to Anthropic (tools, streaming, system prompt structure)
- [ ] Understand how OpenAI function calling differs from Anthropic tool use

**Success check:** Can call OpenAI API and read an existing OpenAI codebase without being lost

---

**Ollama — free local models (no API cost, runs offline)**
- [ ] Install Ollama (`winget install Ollama.Ollama`)
- [ ] Pull a model locally (`ollama pull llama3` or `ollama pull mistral`)
- [ ] Call Ollama via its REST API (it mimics OpenAI's API format — `POST /api/chat`)
- [ ] Understand why companies use local models — data privacy, no vendor lock-in, zero API cost at scale
- [ ] Compare response quality vs Claude on the same question

**Success check:** Ollama runs a model locally and answers a question with zero API cost

---

**Groq — free tier, fastest inference on open models**
- [ ] Get a Groq API key (free at console.groq.com)
- [ ] Call Groq API — it uses OpenAI-compatible SDK format
- [ ] Run Llama 3 or Mixtral via Groq and compare speed vs Claude
- [ ] Understand Groq's value: open source models at commercial-grade speed

**Success check:** Groq responds to a question faster than Claude on the same input

---

### Week 2 — Wire Multi-Model Into Your Project

- [ ] Create `model_client.py` — abstraction layer with a `chat()` function that accepts `provider`, `model`, `messages`, `tools`
- [ ] Implement Claude adapter (move existing Anthropic SDK calls here)
- [ ] Implement Gemini adapter
- [ ] Implement OpenAI/Groq/Ollama adapter (they share the same SDK format)
- [ ] Read `LLM_PROVIDER` and `LLM_MODEL` from `.env` at startup
- [ ] Add a provider selector dropdown to `chat.html` — switch models live from the UI
- [ ] Update cost dashboard to show cost by provider (Ollama = $0.00, Claude = highest)
- [ ] Update model routing — `_pick_model()` now routes across providers, not just Haiku vs Sonnet
- [ ] Add provider name to the `done` SSE event so the UI shows which provider answered

**Enterprise pattern learned:**
This is the same abstraction used by LangChain, LiteLLM, and every enterprise AI platform. One interface, multiple backends. Swap providers without touching business logic.

**Success check:** The chat UI has a model selector. Switch between Claude, Gemini, and Ollama mid-conversation. Cost dashboard shows $0.00 for Ollama turns. All 8 MCP tools work regardless of which provider is active.

---

## Phase 4 — Advanced AI Engineering (Weeks 15+)
**Goal: Build production-grade AI features**

### Observability
- [ ] Set up Langfuse (free tier)
- [ ] Track every Claude API call
- [ ] Monitor cost per user per day
- [ ] Set up alerts for failed tool calls
- [ ] Experiment with prompt versions

### Safe Rollout — MLOps for AI (not just "deploy it," but "safely change it once it's live")
- [ ] Understand prompt/model versioning — treat a system prompt change like a code change, not a casual edit
- [ ] Practice a canary rollout — route a small % of requests to a new system prompt or model, compare cost/quality/eval-pass-rate before rolling out to everyone
- [ ] Understand A/B testing for prompts — same question, two prompt versions, compare eval scores
- [ ] Know what a rollback looks like when a new prompt/model version regresses in production

### Advanced RAG
- [ ] Implement hybrid search (keyword + semantic)
- [ ] Add re-ranking (cross-encoder models)
- [ ] Understand multi-index retrieval + routing — splitting one flat ChromaDB collection into separate indexes per content type (different chunking/embedding needs), with a router step (metadata filter, LLM classifier, or query fan-out) deciding which index(es) to search, then re-ranking merged results before handing them to Claude. Only worth building once `knowledge_base/` has genuinely distinct content types (code, structured data, a second project) — not needed at today's scale of one folder of similar docs.
- [ ] Migrate ChromaDB to Vertex AI Vector Search on GCP
- [ ] Replace sentence-transformers with Vertex AI Embeddings API
- [ ] Conceptually compare the vector DB landscape — Pinecone (managed, easy), Weaviate (open source, hybrid search built-in), Qdrant (open source, fast), pgvector (simplest if already on Postgres) — know the tradeoffs even without hands-on time on all of them

### Fine-Tuning Fundamentals (conceptual — not required to actually fine-tune anything)
- [ ] Understand what fine-tuning actually changes (model weights) vs what RAG/prompting change (context only)
- [ ] Understand LoRA/QLoRA at a conceptual level — why they make fine-tuning cheaper than full fine-tuning
- [ ] Build a decision tree: when would you fine-tune vs use RAG vs just improve the prompt? (Most real products never need to fine-tune — knowing why is the actual skill)

### LangChain (optional)
- [ ] Understand when to use LangChain vs raw SDK
- [ ] Build a multi-step research pipeline
- [ ] Implement agent memory patterns

---

## Phase 5 — Structured Outputs (2–3 Days)
**Goal: Get Claude to return reliable JSON instead of prose — critical for any AI feature that feeds data into another system**

- [ ] Understand why unstructured text responses break downstream systems
- [ ] Use `response_format` / tool use pattern to force structured JSON from Claude
- [ ] Build a structured output tool in `mcp_server.py` that always returns typed JSON
- [ ] Handle validation — what happens when Claude returns malformed JSON
- [ ] Use Pydantic models to validate Claude's output before passing it downstream
- [ ] Add a structured output example to the existing project (e.g. note creation returns `{title, content, tags}` not plain text)

**Enterprise pattern:** Every AI feature that writes to a database, calls another API, or feeds a UI component needs structured output. Free-form text is only acceptable for chat.

**Success check:** Claude returns validated, typed JSON that can be inserted directly into SQLite without any string parsing

---

## Phase 6 — Guardrails & Content Moderation (3–4 Days)
**Goal: Add input/output safety layer — required before any enterprise AI app goes to production**

- [ ] Understand the 3 guardrail layers: input filtering, output filtering, tool call validation
- [ ] Implement input sanitisation — strip control characters, cap message length, block obvious injection attempts
- [ ] Implement prompt injection detection — flag messages that try to override the system prompt
- [ ] Implement PII redaction — detect and mask email addresses, phone numbers, credit card numbers in output
- [ ] Add tool call validation in `mcp_server.py` — never trust Claude's arguments blindly, validate every input
- [ ] Never expose raw error messages to the user — always return clean, safe error responses
- [ ] Understand OWASP Top 10 for LLM Applications (published by OWASP, specific to AI)

**Enterprise pattern:** Banks, hospitals, and law firms cannot ship AI features without guardrails. PII leakage and prompt injection are the two most common production AI incidents.

**Success check:** App blocks prompt injection attempts, redacts PII in responses, and validates all tool inputs — with tests proving each case

---

## Phase 7 — pgvector (1–2 Days, alongside PostgreSQL migration)
**Goal: Replace ChromaDB with vector search inside PostgreSQL — one database instead of two**

- [ ] Understand what `pgvector` is — a PostgreSQL extension that adds a `vector` column type
- [ ] Enable pgvector on your Cloud SQL PostgreSQL instance (`CREATE EXTENSION vector`)
- [ ] Migrate `rag.py` from ChromaDB to pgvector — store embeddings as `vector(384)` columns
- [ ] Run semantic similarity search using `<=>` cosine distance operator in SQL
- [ ] Compare query performance: ChromaDB vs pgvector at your data size
- [ ] Understand when to use pgvector (< 1M vectors, existing PostgreSQL) vs dedicated vector DB (Pinecone, Weaviate) at scale

**Enterprise pattern:** Most production teams use pgvector to avoid managing a separate vector database. One database, one backup strategy, one connection pool.

**Success check:** `search_docs` works identically but queries PostgreSQL instead of ChromaDB. ChromaDB dependency removed.

---

## Phase 8 — Multi-Agent Systems (1–2 Weeks)
**Goal: Build agents that spawn sub-agents, plan multi-step tasks, and hand off work — the fastest-growing area in AI engineering**

### Concepts first
- [ ] Understand the difference between a tool-using agent (what you built) and a multi-agent system
- [ ] Understand agent roles: orchestrator (plans + delegates) vs worker (executes a specific task)
- [ ] Understand how agents communicate — shared state, message passing, tool results
- [ ] Read Anthropic's guidance on building effective agents

### Build a multi-agent system in your project
- [ ] Add an "orchestrator" mode to `api.py` — Claude receives a complex task and breaks it into sub-tasks
- [ ] Build a research agent — given a topic, searches docs, summarises findings, returns structured report
- [ ] Build a note-taking agent — listens to a task description, creates and organises notes automatically
- [ ] Implement agent handoff — orchestrator passes context to worker agent and collects result
- [ ] Handle agent failures — what happens when a sub-agent errors or loops

### Frameworks to explore (pick one)
- [ ] LangGraph — graph-based agent orchestration, most production-ready
- [ ] CrewAI — role-based multi-agent, good for learning the concept
- [ ] Raw Anthropic SDK — build custom, understand the primitives (recommended first)

**Enterprise pattern:** Enterprise AI products in 2025-2026 are moving from single-agent chatbots to multi-agent pipelines. A "research assistant" at a law firm might have 5 agents: retriever, summariser, fact-checker, formatter, reviewer.

**Success check:** One user message triggers an orchestrator that spawns 2+ worker agents, collects their results, and returns a synthesised response

---

## Phase 9 — Second Project (2–4 Weeks)
**Goal: Prove the skills transfer to a different domain — not another chatbot**

Build something completely different to demonstrate breadth. Pick one:

**Option A — Meeting Transcription + Action Items**
- Record or upload a meeting audio file
- Whisper (OpenAI) or Gemini transcribes audio to text
- Claude extracts action items, owners, and deadlines as structured JSON
- Saves to SQLite, exportable as markdown
- Teaches: audio AI, structured outputs, batch processing (not chat)

**Option B — AI Code Reviewer**
- User pastes code or connects a GitHub repo
- Claude reviews for bugs, security issues, and style violations
- Returns structured review: `{severity, file, line, issue, suggestion}`
- Teaches: structured outputs, GitHub API, diff parsing, multi-turn review workflow

**Option C — Document Summarisation Pipeline**
- User uploads a folder of PDFs (contracts, reports, research papers)
- Pipeline processes each doc: chunk → summarise → extract key facts → store
- Final output: executive summary across all documents
- Teaches: batch processing, pipeline architecture, async jobs, progress tracking

**Why this matters:** One project = one use case on your portfolio. Two different project types = evidence that the skills transfer, not just familiarity with one codebase.

**Success check:** Second project is on GitHub with its own README. Different domain, different architecture pattern, same underlying AI engineering principles.

---

## Final Phase — Claude Code Skill / Plugin
**Goal: Ship a real Claude Code plugin that packages all standards built throughout this project**

This is the end product of the entire learning journey. Everything built and learned feeds into this.

### Plugin Skills to include
- [ ] `/ai-engineer:setup` — scaffolds a new AI project with CLAUDE.md, .env, .gitignore, evals/ folder
- [ ] `/ai-engineer:eval` — runs the eval pipeline and reports pass/fail score
- [ ] `/ai-engineer:document` — updates CLAUDE.md, LEARNING_JOURNEY.md, and portfolio after a phase
- [ ] `/ai-engineer:review` — reviews system prompts for enterprise patterns (caching, routing, injection defense)
- [ ] `/ai-engineer:security-check` — post-change scan for exposure risk: new untracked files, secrets in tracked files, missing `.gitignore` patterns for generated artifacts (screenshots, logs, snapshots), overly broad token scopes

### Plugin structure
- [ ] Create `.claude-plugin/plugin.json` with name, description, version, author
- [ ] Add each skill as `skills/<skill-name>/SKILL.md` with proper frontmatter
- [ ] Publish to a GitHub repo as a marketplace
- [ ] Test install via `/plugin marketplace add vijayanan6/<repo>`
- [ ] Verify all skills work on a fresh machine

### Standards the plugin encapsulates
- CLAUDE.md discipline — every project starts with proper documentation
- Eval pipeline — `evals/dataset.json` + `evals/run_evals.py` scaffolded automatically
- Prompt engineering patterns — system prompt template with caching, routing, injection defense
- Model routing — `_pick_model()` pattern included in scaffolded code
- RAG setup — ChromaDB + sentence-transformers wired up out of the box
- Environment management — `.env` + `python-dotenv` standard, saved as plain UTF-8 (no BOM) to avoid silent auth failures
- Security-after-every-change discipline — `.gitignore` scaffolded to cover secrets, databases, vector stores, and any browser-automation/test output directories by default; no secret is ever printed to logs or chat, even for debugging

**Success check:** A developer installs your plugin, runs `/ai-engineer:setup`, and gets a production-ready AI project scaffold with all enterprise standards baked in — in under 5 minutes

---

## GCP Services to Learn (Running List)
- [ ] Cloud Run — serverless containers ← start here
- [ ] Artifact Registry — Docker image storage
- [ ] Cloud Build — CI/CD pipelines
- [ ] Secret Manager — encrypted secrets
- [ ] Cloud Storage — file storage
- [ ] Cloud SQL — managed PostgreSQL
- [ ] Cloud Logging — structured logs
- [ ] Cloud Monitoring — metrics + alerts
- [ ] IAM + Service Accounts — access control
- [ ] VPC — private networking
- [ ] Firebase Auth — user authentication
- [ ] Vertex AI — embeddings + vector search
- [ ] Cloud Armor — DDoS + WAF
- [ ] Apigee — API gateway (advanced)

---

## Resources

| Topic | Resource |
|---|---|
| Google AI Studio | aistudio.google.com (free Gemini API key) |
| Gemini SDK | ai.google.dev/gemini-api/docs |
| OpenAI SDK | platform.openai.com/docs/api-reference |
| Ollama | ollama.com (run LLMs locally, free) |
| Groq | console.groq.com (free tier, fast open model inference) |
| LiteLLM | litellm.ai (multi-provider abstraction library — reference) |
| MCP Inspector | modelcontextprotocol.io/docs/tools/inspector |
| pytest | docs.pytest.org |
| pytest-asyncio | pytest-asyncio.readthedocs.io |
| MCP Resources & Prompts | modelcontextprotocol.io/docs/concepts/resources |
| Claude Code Plugin Marketplaces | code.claude.com/docs/en/plugin-marketplaces.md |
| Claude Code Plugins Reference | code.claude.com/docs/en/plugins-reference.md |
| Docker | docs.docker.com/get-started |
| GCP Cloud Run | cloud.google.com/run/docs |
| GCP CLI | cloud.google.com/sdk/docs/install |
| React | react.dev |
| TypeScript | typescriptlang.org/docs |
| Tailwind CSS | tailwindcss.com/docs |
| Firebase Auth | firebase.google.com/docs/auth |
| FastAPI Security | fastapi.tiangolo.com/tutorial/security |
| Langfuse | langfuse.com/docs |
| Vertex AI | cloud.google.com/vertex-ai/docs |

---

## Timeline Overview

```
Weeks 1–2: pytest + MCP resources/prompts → solid foundation
Month 1:   Docker + Cloud Run → app live on GCP
Interlude: Claude Code Plugin Marketplace (optional) → plugin.json, marketplace.json, GitHub-hosted registry
Month 2:   GCP Services → PostgreSQL, GCS, Secret Manager
Month 3:   React frontend → proper chat UI
Month 4:   Authentication → multi-user, secure
2 Weeks:        Multi-model capability — Claude + Gemini + OpenAI + Ollama (free/local) + Groq → model abstraction layer in api.py, provider dropdown in UI, $0 cost on local models
Month 5+:  Advanced AI → Langfuse, advanced RAG, Vertex AI
Month 6:   Structured outputs + Guardrails → production-safe AI features
Month 6:   pgvector → replace ChromaDB, one database for everything
Month 7+:  Multi-agent systems → orchestrator + worker agents, LangGraph
Month 8+:  Second project → different domain, proves skills transfer
Final:     Claude Code plugin → packages everything into a reusable tool
```

---

## Notes
- Update this file as you complete each item
- Add new learnings and discoveries as you go
- Each phase builds on the previous — do them in order
- Hands-on practice matters more than reading — build something with every new concept
