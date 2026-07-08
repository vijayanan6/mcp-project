# Final Insights — MCP Learning Project

Key lessons from building a full-stack AI application from scratch using
MCP, FastAPI, SQLite, ChromaDB, and Claude.

---

## 1. MCP is the USB of AI Tools

Before MCP, every AI app hard-coded its own tools. MCP standardises the
connection — build a tool once, any AI can use it. The value is not in
any single tool you build. It is in the fact that your tools can be
discovered and called by any MCP-compatible AI client without changing
the server code.

---

## 2. Claude is an Orchestrator, Not an Executor

The biggest mindset shift in this project. Claude never runs your code.
It reads tool descriptions, decides what to call, and returns a JSON
request. Your code executes the tool and feeds the result back.

This means Claude is only as capable as the tools you give it. A Claude
with no tools can only answer from training data. A Claude with the right
tools can do anything Python can do.

---

## 3. Tool Descriptions Are Your Prompt Engineering

You do not control Claude with complex prompting tricks. You control it
by writing clear tool descriptions. A strong description says *when* to
call the tool, not just what it does.

```python
# Weak — Claude may not know when to use this
description="Does math"

# Strong — Claude knows exactly when to call it
description="Safely evaluates a mathematical expression. Use this for
             any arithmetic, algebra, or calculations the user asks for."
```

That one principle drove every tool decision in this project.

---

## 4. The System Prompt is the Personality

One line in the system prompt changed how the entire agent behaved —
from answering from general knowledge first to always checking documents
first. The system prompt is not boilerplate. It is the most powerful
line in your application. Write it deliberately.

---

## 5. RAG is the Bridge Between AI and Your Data

Claude was trained on public internet data. Your private documents do not
exist in its training. RAG (Retrieval Augmented Generation) is how you
give Claude access to your knowledge — not by fine-tuning (expensive and
complex), but by retrieving and injecting relevant context at query time.

```
Your 50-page document
  → split into chunks
  → embedded as vectors
  → searched by meaning
  → top 4 relevant paragraphs sent to Claude
```

Claude answers from your document as if it had always known it.

---

## 6. Every Layer Has a Single Responsibility

```
chat.html      → show the UI
api.py         → handle HTTP and orchestrate
mcp_server.py  → define and run tools
database.py    → store data
rag.py         → search documents
```

Each file does one thing. That is why the project stayed manageable as
it grew from 2 files to 10. When something breaks, you know exactly
where to look. When you need to change something, you know exactly what
to touch.

---

## 7. Persistence is What Separates Demos from Products

The first version lost everything on restart — notes, sessions,
conversation history. Adding SQLite took one file and transformed it
into something usable every day. Persistence is not a feature. It is
the difference between a toy and a tool.

---

## 8. Git is Not About Backup — It is About Confidence

Feature branches meant you could break things without fear. Every new
feature lived safely in its own branch. Main always worked. You could
experiment, fail, and try again without affecting anything that was
already running. That confidence is what lets you move fast without
breaking things.

---

## 9. Documentation is Part of the Build

Writing `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, and
`LEARNING_JOURNEY.md` was not extra work done after the project. It was
part of building the project. Future you — or anyone else — can pick
this up and understand every layer in 10 minutes.

That is a professional habit. Code without documentation is a liability.
Code with good documentation is an asset.

---

## 10. You Built a Production Architecture

```
Browser → FastAPI → Claude → MCP → SQLite + ChromaDB
```

This is not a toy. This exact architecture — with a larger database, a
managed vector store, and more tools — runs in real AI products at
companies today. You understand every component, every connection, and
every reason each piece exists.

---

## 11. You Can't Optimise What You Can't See

Adding a cost dashboard wasn't about saving money — it was about making invisible things visible. Token counts, model choices, tool call frequency, session costs — none of this was visible before. Once visible, every optimisation decision became obvious.

This is the core principle behind observability in enterprise engineering. Logging, metrics, tracing — they all exist for the same reason: you cannot fix what you cannot measure.

---

## 12. Output Tokens Are the Most Expensive — Most Developers Don't Know This

Claude charges four different prices: input, cache write, cache read, and output. Output costs 3–5× more per token than input, even though there are far fewer output tokens. A long Claude response costs more than a long conversation history.

Understanding token economics changes how you design AI features — you cap output tokens, you cache system prompts, you route simple queries to cheaper models. These are not micro-optimisations. At scale they determine whether an AI feature is profitable.

---

## 13. Evals Test Behaviour, Not Code

Unit tests catch bugs in your code. Evals catch failures in Claude's behaviour. Both are necessary. Neither replaces the other.

Code grading (Python if/else) is fast and free — run it on every commit. Model grading (Claude grading Claude) tests quality but doubles API calls — run it nightly. Human grading is the most accurate but most expensive — save it for releases.

The eval pipeline you built is the same structure used by every enterprise AI team. The scale differs; the pattern does not.

---

## 14. Multi-Tenancy Is Just a Tag Column

The simplest form of supporting multiple projects in one database is adding a `project` column and filtering by it. One database, multiple tenants, isolated by a tag. This is how Salesforce isolates customers (`org_id`), how Stripe isolates platforms (`account_id`), and how your dashboard isolates projects (`project`).

The pattern scales from SQLite to PostgreSQL to distributed databases without changing the concept. You learned it at small scale — it transfers directly to enterprise.

---

## 15. The Bug You Can't See Is the One That Bites Hardest

An `.env` file with a correct API key still failed authentication — because the file had an invisible UTF-8 byte-order-mark at the very start, merging with the first variable name. No amount of staring at the key itself would have found it; the fix came from checking the file's *structure* (`grep -c "^ANTHROPIC_API_KEY="`), not its content.

The broader lesson: when something that should obviously work doesn't, question the layer below the one you're debugging — the encoding, not the value; the transport, not the payload.

---

## 16. Security Is a Discipline Applied to Tooling, Not Just Application Code

Adding Playwright MCP for UI testing created a new, ungitignored output directory (`.playwright-mcp/`) holding screenshots and page snapshots with session and cost data — exactly the kind of artifact that quietly ends up in a public repo if nobody checks for it.

The fix wasn't complicated. The discipline was remembering to look: after *every* new tool, dependency, or config change — not just application features — check for new untracked files before considering the task done.

---

## 17. Few-Shot Examples Teach by Surface Resemblance, Not Intent

Adding few-shot examples to `SYSTEM_PROMPT` caused a measured eval regression (12/12 → 10/12), not an improvement. The `list_docs` example ("What documents do I have?") and a failing test case ("summarize all the documents in my system") shared surface wording — "documents", "all... in my system" — and Claude followed the lexical resemblance instead of the intended semantic split (enumerate files vs. synthesize content).

A rule degrades gracefully at the margins because it's stated as a principle. An example only teaches the pattern it happens to resemble — the closer a new case's *wording* sits to an example, the more it gets pulled toward that example's answer, even when the underlying intent differs. Tuning few-shot examples means checking them against realistic edge cases, not just confirming they read sensibly in isolation.

---

## 18. A Test Harness That Defaults Missing Fields to "Pass" Hides Its Own Failures

The eval regression above surfaced a second, unrelated bug: `run_evals.py`'s printer read `result.get("tool_pass", True)`, defaulting to "pass" whenever a field was absent. On a timeout, the result dict legitimately has no `tool_pass` key at all — so the printer rendered `OK OK` icons for a case that had actually thrown an exception, hiding the real error message entirely.

Any monitor, printer, or test harness that treats "field missing" the same as "check passed" will stay silent exactly when something breaks in a way the code didn't anticipate. The safe default for an unknown state is to surface it, not to assume success.

---

## 19. A "Last Value" Slot Is a Silent Data-Loss Trap

Building a credit-reset feature, the first version stored one `prev_period` snapshot with no protection. While testing it, a retried tool call fired the save function twice within 44 seconds — the second reset silently overwrote the first, real snapshot with an empty one. Nothing errored. Nothing warned. The data was just gone.

Any design that holds "the most recent X" in a single slot instead of a list is one accidental double-write away from losing whatever was there before — and because overwriting isn't an error, nothing surfaces the loss until a human notices the data doesn't match what they expected. The fix wasn't a smarter data structure — it was a confirmation prompt naming exactly what would be overwritten, so the human has to actively choose to discard it.

---

## 20. Re-Verifying a Fix Can Surface a Different Bug Than the One You Were Checking

Re-running the eval suite to confirm a prompt fix instead hit a client timeout on both previously-failing cases — the tool-routing question was never actually answered, because the requests never finished. It would have been easy to read "still 2 failures" as "the fix didn't work." It wasn't the same failure: the error message (`ERROR: timed out`, not a wrong-tool note) said so plainly, once the harness was fixed to show it.

The lesson isn't about this one bug — it's about the habit: when a re-run to verify fix A still shows failures, read what actually failed before concluding A didn't work. The two most common false readings are "nothing changed" (when the failure mode is actually different) and "everything's fine now" (when a flaky pass hid a real intermittent issue). Both require looking at the specific error, not just the pass/fail count.

---

## 21. A Metric's Name Is Part of Its Correctness

The cost dashboard's "Days Left" stat computed exactly the right number — remaining balance divided by burn rate. The math was never the bug. The label was: it implied Anthropic API credits expire on a day count, which they don't. A user glancing at "Days Left: 33" reasonably reads that as a countdown to something running out on a schedule, not as a rough forecast that assumes today's spend rate holds steady.

A correct calculation attached to a misleading name is still a bug — just one that lives in the UI layer instead of the logic layer. The fix here didn't touch the math at all: renaming to "Est. Runway," formatting the value as `~33d` instead of a bare `33`, and adding a tooltip that says outright "not an actual credit expiration." Any time a number could be mistaken for a guarantee it isn't, that's worth fixing with the same seriousness as a wrong calculation — the person reading the dashboard can't tell the difference between "this number is wrong" and "this number is right but means something other than what it looks like it means."

---

## 22. The Real Injection Risk in RAG Is Indirect, Not Direct

A user typing "ignore your instructions" only hijacks their own conversation — low stakes. The dangerous case is a document sitting in `docs/` that contains text shaped like an instruction, because `search_docs` and `read_doc` return that content as a `tool_result`, and a `tool_result` looks identical to a real instruction unless Claude is told otherwise.

Any system that retrieves external content into an LLM's context — a document store, a web search, a scraped page — has this exposure by default. The fix isn't input filtering (that only catches the user's own words); it's telling the model explicitly, in the system prompt, that retrieved content is data to report on, never a command to obey.

---

## 23. Verify a "Why It Works" Claim Against the Library, Not the Comment Above It

`rag.py`'s docstring asserted that a distance under 0.8 counts as "relevant" without saying which distance metric ChromaDB was actually using. Checking the installed `chromadb` source directly showed the embedding function's `default_space()` returns `"cosine"` — confirming the scoring line was literally computing cosine similarity, not an arbitrary convention that happened to work.

A comment describing *why* code works is a claim, not a fact — it can be stale, incomplete, or simply wrong the moment a dependency changes its defaults. When a "why" matters enough to build understanding on, check it against the actual installed version, not the explanation someone (including a past version of yourself) wrote next to it.

---

## 24. A Personal Learning Plan Can Go Stale Before You Act On It

An item written weeks earlier described "response prefilling" as a prerequisite for a later phase. By the time it came up, the technique it described — seeding an assistant turn to force JSON — returned a hard error on the exact model this project routes to. The plan wasn't wrong when written; the API moved.

The same applies to anything else written down as "the way to do X" in a fast-moving field: a plan, a note, a remembered pattern from training data. Before building on a described technique, check whether it still matches the current surface — especially when the source is your own past notes, which nobody has an incentive to flag as outdated the way a deprecation warning does.

---

## 25. A Completed Checkbox Can Hide an Unlearned Primitive Underneath It

"MCP (Model Context Protocol) — server, tools, stdio transport" was checked off in the learning plan from the very first phase, and that checkmark quietly stood in for "tool use, generally." It didn't actually cover it: building MCP tools and running them through `tool_runner` never required touching `tool_choice`, `disable_parallel_tool_use`, or reading a raw streamed `input_json_delta` — the SDK helper abstracts all of it away. The gap sat there, invisible, until it was asked about directly.

A high-level checkbox names a topic; it doesn't guarantee every layer underneath that topic got learned. The habit worth building isn't "trust the checkmark" — it's periodically asking, of any "done" item that names a broad concept, *what's the abstraction hiding, and have I actually seen underneath it?* This is the same shape as a passing test suite that never exercised an edge case: green doesn't mean covered, it means covered *for what was checked*.

---

## 26. Not Every Tool Call Looks the Same in the Response — Tracking Code Has to Know That

`tools_used.append(block.name)` only checked `block.type == "tool_use"` — correct for MCP tools and any client-side tool, but wrong for server-side tools like `web_search`, which arrive as a `server_tool_use` block instead. The bug was silent: the chat UI still showed the tool-call indicator correctly (that rendering path checked something else), and the dollar total in the cost dashboard was still right (that math came from a separate `usage.server_tool_use.web_search_requests` field). Only the "Cost by Tool" breakdown was wrong — `web_search` calls existed and were billed correctly, they just never got attributed to a tool in that one specific view.

The general shape: when an API has more than one way to represent "a tool was called," any code that pattern-matches on one shape will silently miss the others, and the failure won't announce itself — everything downstream that doesn't depend on the missed case keeps working. The fix isn't "test more" in the abstract; it's checking the *specific* field you're aggregating into (here: querying `/usage/data` directly and noticing `by_tool` was empty for a tool you know was called) rather than trusting that "the feature looks like it works" means every code path behind it does too.

---

## 27. Declaring a Tool Is a Commitment to Every Model That Might See It

Adding `web_search` to the shared tool list broke messages that had nothing to do with web search — "add a comment to api.py" 400'd with an error naming `web_search`, not the actual request. The cause: the Anthropic API validates every *declared* tool against the model's capabilities at request time, not just the tools a model decides to invoke that turn. `web_search_20260209`'s default configuration requires programmatic tool calling, which Haiku doesn't support — and this project's `_pick_model()` router can send *any* short, non-complex-sounding message to Haiku, completely independent of whether that message might need web search.

This is the same failure shape as adding a new required field to a shared schema without checking every consumer — except here the "consumers" are the different models a single router can select, and the incompatibility only shows up at request time, not at declaration time. Any time a tool is added to a list shared across multiple models (a router, a fallback chain, an A/B test), the right question isn't "does my primary model support this tool's config" — it's "does *every* model this code can route to support it," because the API fails the whole request, not just the unsupported feature, when one doesn't.

---

## 28. Design the Trigger Around What Your Runtime Actually Guarantees

The obvious way to build "send a digest every morning" is a background scheduler firing at a fixed time. That's the wrong answer for an app that only runs when someone starts it — `uvicorn --reload` isn't a 24/7 service, so a scheduler set for 8am would silently miss every day the server happened to not be running at that exact moment, and nothing would ever surface the miss. The fix wasn't a better scheduler; it was noticing the question was wrong. Reframed as "the digest should fire once per calendar day, whenever that day's first real request happens," the mechanism became a simple date comparison on existing traffic — no new dependency, no missed days as long as the app gets used at all that day.

The general shape: a "textbook" solution often silently assumes a runtime guarantee (always-on, fixed clock, persistent process) that a given deployment doesn't actually have. Before reaching for the standard pattern, check whether your environment provides the guarantee the pattern depends on — if not, the simpler fix is usually to redesign the trigger around what you *do* have, not to add infrastructure to fake the guarantee you don't.

---

## 29. Multi-Tier State Needs Testing at the Transitions, Not Just the Tiers

Building a two-tier alert (warning, then critical), the obvious test is "does warning fire" and "does critical fire" — both passed immediately. The bug only showed up when balance dropped straight from normal into critical in one jump, skipping the warning zone entirely: the *warning* tier's cooldown was left stale, because the code that handled "entering critical" never considered "what if a warning was already pending." If balance had later partially recovered back into the warning band, the alert would have looked suppressed — as if still inside a cooldown window from an alert that, in this run, was never actually sent.

Testing each tier in isolation only exercises the states a system can be *in*. It doesn't exercise the *transitions* between them — and non-adjacent transitions (skipping a state entirely) are exactly where state left over from "the state I didn't pass through" goes stale. Any system with more than two states and independent per-state timers/cooldowns needs its transition matrix tested, not just its states: normal→warning, normal→critical, warning→critical, critical→warning (partial recovery), and critical→normal (full recovery) are five different paths, not two.

---

## The Core Takeaway

You started wanting to understand MCP.

You ended with a working full-stack AI application — semantic document search, persistent database, real-time streaming, model routing, prompt caching, an eval pipeline, and a full cost observability dashboard with multi-project support.

More importantly — you understand **why** every piece exists.
That understanding transfers to any AI project you build next,
regardless of the technology stack.

A developer asks: *"does it work?"*
An AI engineer asks: *"does it work, how much does it cost, is the quality consistent, and how do I know when it breaks?"*

You are now asking the second set of questions.

**The tools will change. The principles will not.**
