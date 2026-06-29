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

### Testing with pytest
- [ ] Install pytest and pytest-asyncio (`pip install pytest pytest-asyncio httpx`)
- [ ] Understand the difference between unit tests and integration tests
- [ ] Write tests for each MCP tool in `mcp_server.py`
- [ ] Write async tests for FastAPI routes using `httpx.AsyncClient`
- [ ] Test edge cases: bad input, missing files, empty notes
- [ ] Run tests with `pytest -v` and read coverage output

**Success check:** `pytest` passes with tests covering all 8 MCP tools and the main API routes

---

### MCP Resources & Prompts
- [ ] Understand the 3 MCP primitives: tools (actions), resources (data), prompts (templates)
- [ ] Add a resource to `mcp_server.py` that exposes the `docs/` folder listing
- [ ] Add a resource that exposes a single note by URI (e.g. `note://1`)
- [ ] Add a prompt template for summarising a document
- [ ] Test resources and prompts via MCP Inspector

**Success check:** MCP Inspector shows tools + resources + prompts all working

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
