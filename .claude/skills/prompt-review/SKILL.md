---
name: prompt-review
description: Reviews a system prompt against prompt engineering best practices — role framing, XML structure, few-shot quality, chain-of-thought justification, prompt injection defense, caching correctness, model-routing compatibility, and current API compatibility. Use when explicitly asked to review, audit, or check a system prompt. Invoke explicitly via /prompt-review — does not run automatically.
disable-model-invocation: true
---

# /prompt-review

Reviews a system prompt for quality issues using the same rubric this project's own
`SYSTEM_PROMPT` was built and hardened against (see `LEARNING_JOURNEY.md` Phases 15 and 17,
and `INSIGHTS.md` #17, #22–24). **This skill only reports findings — it never edits the
target file.** If the user wants fixes applied, that's a separate, explicit ask after
reviewing the report.

## Target resolution

- If `$ARGUMENTS` names a file or path, review the system prompt defined there.
- Otherwise, default to this project's own system prompt: the `SYSTEM_PROMPT` list in
  `api.py`.
- If the target can't be found, say so and ask the user to point at the right file —
  don't guess at a different prompt.

## Before checking anything API-specific

Any check below that depends on current Anthropic API behavior — prompt caching syntax,
assistant-turn prefill, extended/adaptive thinking parameters, structured outputs,
model capabilities — must be verified against the `claude-api` skill or a live
`client.models.retrieve()` capability check, **not** asserted from memory. This project
already caught one stale claim this way (a learning-plan item describing response
prefilling as if it still worked, when it now 400s on this project's own routed model) —
treat that as the standing reason this rule exists, not a one-off.

## Read before reviewing

1. The full text of the target system prompt.
2. The code immediately around it: how it's passed to `messages.create()` /
   `tool_runner()` — specifically `cache_control` placement, which model(s) it's sent to,
   and what tools are declared alongside it.
3. Any eval suite in the project (e.g. `evals/dataset.json` here) — a rubric finding is
   more useful when you can point at whether an eval already covers it.

## Rubric

Walk every category below. For each, report one of: **✅ Present** (quote the exact
excerpt with file:line), **⚠️ Worth considering** (optional improvement, explain the
tradeoff), or **🔴 Missing / risk** (explain the concrete failure scenario this exposes,
not just "best practice says so").

**A — Role & persona**
Does the prompt define a scoped persona/job (not a generic "helpful assistant")? Does
that persona ever *contradict* another explicit rule elsewhere in the prompt? A role is a
bias, not an override — a conflicting role + rule pair produces unpredictable behavior,
not a clean resolution in the role's favor.

**B — XML tag structuring**
Are distinct sections (role, rules, examples, security) wrapped in semantically named
tags (`<role>`, `<tool_routing_rules>`, `<examples>`, `<security>`), or is it one
undifferentiated prose block? The tag *name* itself primes interpretation — flag generic
names like `<section1>` as a missed opportunity, not just absence of tags.

**C — Few-shot examples**
If examples are present, check every pair of examples (and every example against the
prompt's stated rules) for **lexical overlap that maps to different actions** — the
specific failure mode that regressed this project's own eval score from 12/12 to 10/12
(Phase 15). Don't just confirm examples "read sensibly in isolation"; look for shared
distinctive words/phrases across examples with different correct actions. If there's an
eval suite, note whether it has a case matching each risky overlap you find.

**D — Chain-of-thought**
If CoT is used, is the task complex enough to justify the added tokens/latency? If CoT is
absent, is that a deliberate, documented tradeoff (e.g. "not worth it for a simple routing
decision") or just never considered? Flag CoT applied to trivial classification/routing
as a cost/latency issue, not a quality one.

**E — Prompt injection defense**
This is the highest-priority category if the prompt's tools ever return retrieved or
external content (RAG search results, file reads, web fetches, third-party API
responses) into Claude's context. Check specifically:
- Does the prompt explicitly state that tool results are data, not instructions?
- Would a malicious string embedded in retrieved content (e.g. "ignore previous
  instructions...") be distinguishable from a real instruction under the current prompt?
- Indirect injection (hostile content the tool retrieves) is the realistic risk for a
  RAG-style tool; direct injection (user typing an override) only affects that user's own
  session — weight findings accordingly, don't treat them as equally severe.

**F — Prompt caching correctness**
- Is `cache_control: {"type": "ephemeral"}` applied to the stable, shared portion of the
  prompt?
- Does anything volatile get interpolated into the cached prefix — a timestamp, a
  session ID, a non-deterministic-order JSON dump — that would silently break caching
  (cache writes but never reads)? This is easy to miss because it doesn't error, it just
  quietly costs more on every request.
- Is the breakpoint at the *end* of the stable content, not mid-prompt?

**G — Model-routing compatibility**
If the prompt is sent to more than one model (e.g. a cheap/fast model for simple queries,
a stronger model for complex ones), does it work correctly across all of them — not
tuned only for whichever model was used while writing it? Verify the model IDs referenced
in the surrounding code are current (not deprecated/retired) and actually support any
capability the prompt assumes (thinking, structured outputs) — check live via the Models
API rather than from memory, per the rule above.

**H — Response-format currency**
Does the surrounding code rely on assistant-turn message prefilling to force a response
shape? Check whether that still works on every model this prompt is routed to — it 400s
on the current Opus 4.6+/Sonnet 4.6+/Fable 5 generation. If structured output is needed,
the current replacement is `output_config.format` or `client.messages.parse()` with a
Pydantic model, not prefilling.

**I — Context engineering hygiene** (adjacent to the prompt text, but load-bearing)
Even though these aren't prompt *wording* issues, flag them here since they're part of
the same discipline: is conversation history capped? Are tool outputs (RAG chunks, file
reads) size-bounded? Is there a documented reason for each cap's specific value, or was
it picked arbitrarily?

## Output

Write a plain Markdown report directly in the response — do not use a code-review
findings tool for this; it's a different domain (prompt quality, not code bugs). Structure:

1. One-line summary: how many ✅ / ⚠️ / 🔴 across the 9 categories.
2. The findings themselves, grouped by category, most severe first within each.
3. A **prioritized top-3 action list** at the end — the highest-leverage fixes, not
   every finding restated. This is a review, so stop there; don't edit the file unless
   the user asks for that as a separate next step.
