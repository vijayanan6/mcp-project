# LinkedIn Posts — MCP Learning Project

---

## Post 1 — AI Cost Dashboard (Publish first)

**Timing:** Tuesday or Wednesday, 8–10am
**Attach:** Screenshot of the dashboard (credit tracker + daily chart + cost by tool + cost by project)
**Tag:** @Anthropic

---

🎯 I built an AI Cost Dashboard that shows exactly where every dollar goes when you talk to an AI — and it changed how I think about building AI products.

---

**The problem I wanted to solve:**

When I started building with Claude API, I had no idea where my credits were going. Was it the long conversations? The document searches? The model I chose? I just watched the balance drop.

So I built full cost observability into my AI assistant from scratch.

---

**What the dashboard tracks:**

💰 **Credit Tracker — personal accountability**
Set your starting API balance. See remaining credits, burn rate per day, and days of usage left. A red alert badge pulses in the chat UI when you're running low.

*(This tracks your Anthropic API key credits — pay-as-you-go usage from your code. Not your Claude Pro subscription.)*

For a personal project this means: **no surprise bills. No waking up to find your $5 credit is gone.**

📊 **Token Breakdown — 4 types, 4 different prices**
This is what most developers miss entirely. Claude charges differently for:
- **Input tokens** — your message + history sent fresh
- **Cache Write** — system prompt saved to Anthropic's memory (one-time)
- **Cache Read** — system prompt reused from cache (10× cheaper than input)
- **Output tokens** — Claude's response (most expensive per token)

For personal projects: you stop wasting money on tokens you didn't need to pay full price for.

For enterprise: cache hit rate, output token ratio, cost per session — these are the KPIs that determine whether an AI feature is financially viable at scale.

🔧 **Cost by Tool — which features are expensive to run**
Every tool call is tracked. I can now see that `search_docs` costs 10× more than `get_weather` — because it routes to a more powerful model and passes document chunks as context.

For personal projects: you know exactly which feature to optimise first.

For enterprise: this is how product teams decide where to invest in model routing, caching, and prompt compression. A feature that costs $0.015 per call at 1 million users per day is a $15,000/day decision.

📈 **Daily Usage Chart**
14-day trend chart — built in pure SVG, no libraries. Dollar labels on every bar, intensity shading, Y-axis scale. At a glance you can see which days were expensive and why.

🗂️ **Multi-Project Support — one dashboard, all your AI projects**
Added a `project` column to the database so multiple AI projects report to the same dashboard. Switch between projects with a dropdown — all cards, charts, and tables filter instantly.

For personal projects: one place to see all your AI spend across every project you build.

For enterprise: this is the same multi-tenancy pattern used by Salesforce (`org_id`), Stripe (`account_id`), and every SaaS product — one database, multiple tenants, isolated by a tag column. I learned it at small scale. It transfers directly to production.

👤 **Per-Session Cost Table**
Which conversations cost the most? Now you know — ranked by spend.

---

**The bigger lesson:**

You can't optimise what you can't see.

Every enterprise AI team has some version of this dashboard — Langfuse, Datadog, custom tooling. They track token costs, model usage, tool call frequency, and session spend because at scale, a 10% reduction in average token cost saves thousands of dollars per month.

I built mine from scratch using SQLite, FastAPI, and pure JavaScript SVG. No third-party observability tool.

That means I now understand *why* these tools exist, *what* they measure, and *how* to build one — not just how to plug one in.

That's the skill that transfers to enterprise AI engineering.

📂 Full project + learning journey: github.com/vijayanan6/mcp-project

Built on top of @Anthropic's Claude API — the token economics alone are worth understanding deeply.

#AIEngineering #LLM #Claude #Anthropic #Python #BuildInPublic #MachineLearning #CostOptimisation #EnterpriseAI

---

## Post 2 — Learning Journey / Mindset Shift (Publish one week after Post 1)

**Timing:** One week after Post 1, Tuesday or Wednesday 8–10am

---

6 months ago I couldn't explain what an LLM actually does when it "uses a tool."

Today I have a full-stack AI application running in production — semantic document search, real-time streaming, prompt caching, model routing, an eval pipeline, and a cost observability dashboard.

Here's what the journey actually looked like, phase by phase.

---

**Phase 1 — MCP (Model Context Protocol)**
Built a custom MCP server from scratch. Learned the hardest lesson first:

*Claude never runs your code. It reads your tool descriptions and returns a JSON request saying "call this function with these inputs." Your code executes it.*

That one insight changed everything. Claude is an orchestrator, not an executor.

**Phase 2 — Document Reading + Security**
Added file access tools. Immediately ran into path traversal vulnerabilities — a user could escape the docs folder and read any file on the system. Fixed it. Learned that security isn't a feature you add later. It's a constraint you build around from the start.

**Phase 3 — PDF OCR**
Scanned PDFs are images, not text. Added a pipeline: `pymupdf` renders pages to images → `Tesseract` OCR extracts text → saved as `.txt` → indexed for search. Three libraries to solve one problem. Real engineering is like this.

**Phase 4 — Web Layer (FastAPI + SSE)**
Replaced the terminal with a browser UI. Learned Server-Sent Events — the same streaming pattern ChatGPT uses to type responses word by word. The first time I saw Claude respond live in my own app, it felt like something clicked permanently.

**Phase 5 — SQLite Persistence**
The first version lost everything on restart. Notes gone. Sessions gone. Adding SQLite took one file and turned a demo into something I actually use every day. Persistence is not a feature. It's the difference between a toy and a tool.

**Phase 6 — RAG (Retrieval Augmented Generation)**
Built the full pipeline: chunk → embed → store → search → retrieve. No wrapper library. Learned why embedding models exist, what vector similarity actually computes, and why you chunk with overlap.

Claude answered questions from a 50-page document using only 4 relevant paragraphs. That's RAG working correctly.

**Phase 7 — Git & GitHub**
Feature branches. Commit discipline. A clean main branch that always worked, no matter what I was experimenting with. This isn't a development habit — it's confidence infrastructure.

**Phase 8 — Token Optimisation**
Learned that prompt caching saves 90% of system prompt costs after the first API call. Applied `cache_control: ephemeral`. Added a 10-message history window — full history in SQLite, only the last 10 messages sent to Claude. Costs capped. Context preserved.

**Phase 9 — Model Routing**
Not every question needs the same model. Haiku is 10–20× cheaper than Sonnet and handles most conversational queries fine. Built a routing function: short/simple → Haiku, long/document-related → Sonnet.

Cost dropped immediately. Quality stayed the same.

**Phase 10 — Eval Pipeline**
Built an automated test suite: 12 test cases, each making a real Claude API call, scored for correct tool selection and model routing.

Evals found two bugs manual testing missed:
- The `/chat` endpoint wasn't returning the `model` field
- The system prompt was ambiguous about when to use `search_docs` vs `list_docs`

Both were fixed because evals gave objective pass/fail evidence, not just a feeling that things worked.

**Phase 11 — Cost Dashboard**
Added full observability — token breakdown per turn, cost per session, credit tracker, daily chart, cost per tool, multi-project support.

The biggest shift wasn't technical. It was this question:

*A developer asks: "does it work?"*
*An AI engineer asks: "does it work, how much does it cost, is the quality consistent, and how do I know when it breaks?"*

The dashboard answers the second set of questions.

---

**What I actually learned:**

Every phase taught something that transfers directly to enterprise AI:
- MCP → tool protocol used in production AI platforms
- RAG → how companies give AI access to private data without fine-tuning
- SSE → how every major AI product streams responses
- Evals → how enterprise teams maintain LLM behaviour after every change
- Cost dashboard → the same observability tooling every AI team builds (Langfuse, Datadog, custom)
- Multi-tenancy → the `org_id` / `account_id` pattern used in every SaaS product

I didn't learn these concepts from a course. I built each one until it broke, figured out why, and fixed it.

📂 Full build log + all 13 phases documented: github.com/vijayanan6/mcp-project

If you're trying to get into AI engineering — build something. The concepts only stick when something is actually running.

#AIEngineering #LLM #Claude #Anthropic #Python #BuildInPublic #MachineLearning #CareerChange #SoftwareEngineering

---
