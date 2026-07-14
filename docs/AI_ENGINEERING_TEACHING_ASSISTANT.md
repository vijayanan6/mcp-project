# AI Engineering Teaching Assistant — Design Doc

A living design document for a future product, separate from the MCP Learning Project itself
but built entirely from what that project produced. This file is meant to be revisited and
improved over time as the idea develops — not a frozen spec.

---

## The Idea

Everything learned and captured while building the MCP Learning Project — the phases, the
mistakes, the fixes, the mentoring style — becomes the curriculum for a Claude Code plugin
that teaches a *different* developer AI engineering, through Claude, while they build their
own project.

Not a generic tutorial. Not a chatbot. A mentor that lives inside Claude Code, follows a real
phase-based curriculum, and reviews the learner's own code against the same enterprise
patterns and standards this project was held to.

---

## Why a Plugin, Not a Standalone App

Learning here happens **through building**, not through reading. A Claude Code plugin operates
inside the actual coding session — it can see real code, real errors, real git state — and
teach the way this project's own mentoring worked: the `.env` UTF-8 BOM bug wasn't explained in
the abstract, it was caught live and taught in context. A standalone app or chatbot loses that.

This is also not a new direction — it's the natural conclusion of the "Final Phase — Claude
Code Skill / Plugin" already planned in `LEARNING_PLAN.md`, just now with a concrete design.

---

## Product Shape

The learner builds **their own project** — not a copy of this one — but guided within the same
phase structure this project followed. The plugin acts as a mentor overlay: it knows where the
learner should be in the curriculum, and it can surface a relevant pattern or mistake from this
project's real journey when it applies, regardless of the learner's specific tech stack.

---

## Prerequisites for Onboarding

Skill-based only, never background-based — this plugin doesn't gate on what field a learner is
coming from (a lesson already learned in this project: being able to learn isn't determined by
starting background). What it *does* need is a concrete technical floor, since the curriculum
assumes it from Phase 1 onward:

- **Claude Code installed and working** — hard requirement, this is the plugin's host environment
- **Basic programming literacy** in at least one language — functions, control flow, basic data
  structures. Doesn't have to be Python; the reference examples are Python because that's what
  this project used
- **Comfort with a terminal/command line** — the curriculum is built around running commands,
  not clicking through a GUI
- **Basic Git** — clone, commit, push. Progress tracking assumes the learner has their own repo
- **Able to obtain an Anthropic API key** — the whole curriculum is building features that call
  Claude, so this isn't optional

**Onboarding check, not a new tool:** rather than adding a 7th MCP tool just for this, fold it
into `get_current_phase` — when there's no existing progress record for a learner, it returns a
short setup check (Claude Code confirmed by definition, but verify Git and an API key are
in place) before recommending Phase 1, instead of assuming the floor is already met.

---

## Architecture

### 1. Content layer (source of truth)

- **Curriculum structure** — derived from `LEARNING_PLAN.md`'s phases, generalized to be
  stack-agnostic ("add persistence," "add semantic search" — not "use SQLite specifically")
- **Lesson records** — structured YAML/JSON, one per concept/mistake/pattern, derived from
  `LEARNING_JOURNEY.md` + `INSIGHTS.md`. Each record splits into:
  - `principle` — the generalized, stack-agnostic lesson (e.g. "invisible encoding bugs break
    silent auth; diagnose structurally, never by exposing the secret")
  - `example` — the concrete illustration from this project (e.g. the actual `.env` BOM fix)
  - fields: `phase`, `concept`, `mistake`, `fix`, `enterprise_pattern`, `tags`

### 2. Storage layer

Reuses this project's existing architecture — nothing new to learn:
- **SQLite** — per-learner progress (`learner_id`, `current_phase`, `completed_concepts`,
  timestamps) — same shape as `database.py`
- **ChromaDB** — embedded lesson records for semantic retrieval — same shape as `rag.py`

### 3. MCP server (new) — tools

| Tool | Purpose |
|---|---|
| `get_current_phase` | Where is this learner, what does mastery of this phase look like |
| `search_curriculum` | Semantic search over lesson records — surfaces a relevant pattern even if the learner's stack differs |
| `record_progress` | Mark a concept/phase complete |
| `review_against_standards` | Review the learner's own code against documented enterprise patterns (caching, routing, security-after-every-change) |
| `suggest_next_build` | Given current phase + what's been built, propose a concrete next step |
| `assess_skills` | Score the learner's actual project against the curriculum's phase "Success check" criteria — a re-runnable checkpoint, not a one-time final exam, always returning a ranked "fix these next" list, never just a number |

**`assess_skills` in detail** — this exists because it's already been validated informally in
this exact project: partway through, the learner asked to be rated 1–10, "sincere and blunt,"
and that honest mid-journey checkpoint was more useful than a vague "you're doing great" would
have been. This tool formalizes that moment instead of leaving it to chance:

- **Callable anytime**, not gated to "end of curriculum" — early on it sets a realistic
  baseline, mid-journey it shows real movement, pre-interview it's a final gut check
- **Evidence-based, not vibes-based** — scores against the actual "Success check:" line
  already written on almost every phase in `LEARNING_PLAN.md`. That rubric already exists; this
  tool is what puts it to use
- **Never ends in just a score** — every run produces a ranked list of the 2–3 highest-leverage
  gaps to close next (mirroring "pytest, Docker, one cloud deploy — get those three done and
  you're at 6.5," not generic encouragement)
- **Stores each run in SQLite** (same progress-tracking table) so a learner can see their score
  move over time, not just get a single snapshot

### 4. Delivery layer — the plugin

- Bundles the MCP server locally — no external hosting needed to start
- Skills as friendly wrappers: `/ai-teacher:where-am-i`, `/ai-teacher:review`, `/ai-teacher:next`, `/ai-teacher:progress`, `/ai-teacher:assess`
- Teaching persona baked into skill instructions — practical, enterprise-first, question-driven,
  calls out deviations. This persona isn't invented — it's this project's own
  `feedback_teaching_approach` mentoring memory, generalized into the plugin.

### 5. Frontend

**Deliberately none, by default.** The interface is Claude Code itself — the mentor
conversation and skills happen in the chat the learner is already using.

For progress visualization, generate it **on demand as an Artifact** (not a persistent server)
— when the learner asks "show my progress," `get_current_phase`'s data renders into a visual
page on the spot. A real standalone dashboard (like `usage.html`) is only worth the extra
infrastructure if progress needs to be checkable outside a Claude Code session entirely.

---

## The Deliverable

A real, installable Claude Code plugin — a GitHub repo installable via
`/plugin marketplace add <owner>/<repo>` and `/plugin install ai-teacher@<repo>`, containing:

- `.claude-plugin/plugin.json` + `marketplace.json`
- `skills/*/SKILL.md` — the four skills above
- A dedicated MCP server with the 6 tools, backed by SQLite + ChromaDB
- Curriculum data — structured lesson records generalized from this project's docs
- README — install instructions, what it teaches, how it works

Not a demo — something a stranger installs in under 5 minutes and gets mentored through
building their own AI project, the same way this project's own build was mentored. This is
also the exact success check already written in `LEARNING_PLAN.md`'s Final Phase — now with a
name and a concrete tool design behind it.

---

## Open Questions / Not Yet Decided

- Exact schema for a lesson record (first candidate example: the `.env` BOM bug)
- How much of `LEARNING_JOURNEY.md`/`INSIGHTS.md` needs to be rewritten (principle/example
  split) vs. can be lifted close to as-is
- Whether this lives in its own new GitHub repo, or as a subdirectory of `mcp-project` initially
- Whether `review_against_standards` needs its own small ruleset file, or reads directly from
  the same `enterprise_pattern` field on lesson records
- Cross-session persistence beyond progress (e.g. streaks, time-per-phase) — deferred until
  there's a reason to need it
- **Naming inconsistency to resolve:** this doc uses `/ai-teacher:*` for skills, but
  `LEARNING_PLAN.md`'s Final Phase section (written earlier, describing what is effectively the
  same plugin) uses `/ai-engineer:*` (`/ai-engineer:setup`, `/ai-engineer:eval`, etc.). Needs one
  canonical prefix before any code gets written.

---

## Status

**Design stage — no code written yet.** This document exists to hold the shape of the idea
between sessions so nothing gets lost. Next concrete step (not yet started): define one full
lesson record end-to-end, using the `.env` BOM bug as the worked example.

**Sequencing decision (locked in):** Vijay finishes `LEARNING_PLAN.md` himself — genuinely, not
just checking boxes — before this plugin ships to teach anyone else. Lesson capture (rule 12,
principle + example per learning moment) stays continuous throughout, and design/scaffolding
work on this doc can continue anytime. What's explicitly gated on completion is the plugin
*going out to mentor another learner* — because the whole value of this product is teaching
from lived mistakes, not documentation, and that credibility only exists once Vijay has
actually been through the phases the plugin would be teaching. Do not suggest shipping or
onboarding real users to this plugin before `LEARNING_PLAN.md` is substantially complete.
