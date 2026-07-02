# Learning Plan — AI Engineering Roadmap

Personal learning roadmap based on the MCP Learning Project foundation.
Track progress by checking off items as completed.

Last updated: June 2026

---

## Current Position

### Completed ✅
- [x] Python (intermediate)
- [x] MCP (Model Context Protocol) — server, tools, stdio transport
- [x] FastAPI — web server, SSE streaming, lifespan, Pydantic
- [x] SQLite — persistence, CRUD, sessions
- [x] ChromaDB — vector database, embeddings
- [x] RAG — chunking, semantic search, sentence-transformers
- [x] PDF processing — pypdf (text), Tesseract OCR (scanned)
- [x] Git + GitHub — branches, commits, pull requests
- [x] GCP concepts — Cloud Run, Cloud SQL, Secret Manager, IAM, VPC (theory)

### Not Yet Started ❌
- [ ] MCP Inspector — visual debugger for MCP servers (test tools without a full client)
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
- [ ] Understand system prompt design — how Claude reads and prioritises instructions
- [ ] Learn few-shot prompting — giving Claude examples inside the prompt to shape behaviour
- [ ] Learn chain-of-thought prompting — asking Claude to reason step by step before answering
- [ ] Understand prompt injection — how users can hijack your system prompt and how to defend against it
- [ ] Practice iterating on prompts and measuring behaviour change
- [ ] Understand the difference between system prompt, user turn, and assistant turn

**Success check:** Rewrite your system prompt using chain-of-thought and few-shot patterns, then eval the difference in tool selection accuracy

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
- [ ] Understand prompt injection — user input that overrides your system prompt
- [ ] Sanitise user input before passing to Claude — strip control characters, cap length
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

**Success check:** `pytest` passes with tests covering all 8 MCP tools and the main API routes

---

### Prompt Evaluation (Evals) ✅
- [x] Understand what evals are and why they differ from unit tests
- [x] Build an eval dataset (JSON) covering system prompt instructions — tool selection, model routing, edge cases
- [x] Write an eval runner that scores tool selection (did Claude call the right tool?)
- [x] Run evals after every system prompt change to catch regressions
- [ ] Implement LLM-as-judge to score open-ended response quality
- [ ] Explore Promptfoo (open source) as an eval framework

**Result: 12/12 (100%) passing — evals/dataset.json + evals/run_evals.py**

---

### MCP Resources & Prompts
- [ ] Understand the 3 MCP primitives: tools (actions), resources (data), prompts (templates)
- [ ] Add a resource to `mcp_server.py` that exposes the `docs/` folder listing
- [ ] Add a resource that exposes a single note by URI (e.g. `note://1`)
- [ ] Add a prompt template for summarising a document
- [ ] Test resources and prompts via MCP Inspector

**Success check:** MCP Inspector shows tools + resources + prompts all working

---

### Observability & Logging (Basic — Before Production)
- [ ] Add structured logging to `api.py` using Python's `logging` module (not `print`)
- [ ] Log every request: session_id, model used, token count, latency, tool calls
- [ ] Log every error with full traceback to a log file
- [ ] Understand the difference between DEBUG, INFO, WARNING, ERROR, CRITICAL log levels
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

## Phase 4 — Advanced AI Engineering (Weeks 15+)
**Goal: Build production-grade AI features**

### Observability
- [ ] Set up Langfuse (free tier)
- [ ] Track every Claude API call
- [ ] Monitor cost per user per day
- [ ] Set up alerts for failed tool calls
- [ ] Experiment with prompt versions

### Advanced RAG
- [ ] Implement hybrid search (keyword + semantic)
- [ ] Add re-ranking (cross-encoder models)
- [ ] Migrate ChromaDB to Vertex AI Vector Search on GCP
- [ ] Replace sentence-transformers with Vertex AI Embeddings API

### LangChain (optional)
- [ ] Understand when to use LangChain vs raw SDK
- [ ] Build a multi-step research pipeline
- [ ] Implement agent memory patterns

---

## Final Phase — Claude Code Skill / Plugin
**Goal: Ship a real Claude Code plugin that packages all standards built throughout this project**

This is the end product of the entire learning journey. Everything built and learned feeds into this.

### Plugin Skills to include
- [ ] `/ai-engineer:setup` — scaffolds a new AI project with CLAUDE.md, .env, .gitignore, evals/ folder
- [ ] `/ai-engineer:eval` — runs the eval pipeline and reports pass/fail score
- [ ] `/ai-engineer:document` — updates CLAUDE.md, LEARNING_JOURNEY.md, and portfolio after a phase
- [ ] `/ai-engineer:review` — reviews system prompts for enterprise patterns (caching, routing, injection defense)

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
- Environment management — `.env` + `python-dotenv` standard

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
Month 5+:  Advanced AI → Langfuse, advanced RAG, Vertex AI
```

---

## Notes
- Update this file as you complete each item
- Add new learnings and discoveries as you go
- Each phase builds on the previous — do them in order
- Hands-on practice matters more than reading — build something with every new concept
