# AIMS v3: Interactive Adaptive Assessment — Planning Doc

> Status: Draft. Living document — update as decisions are made during the build.

## 1. Vision & Principles

AIMS v3 shifts the assessment experience from conversational free-text chat to
**AI-generated interactive widgets** targeted at the learner's identified concept
gaps. The original AIMS premise is preserved and strengthened:

- **Mastery before advancement.** A concept is not considered mastered until the
  learner demonstrates understanding at the configured threshold (default 80%).
- **Wrong answer → remediate → regenerate → re-ask.** After a wrong answer the
  system re-teaches (fundamental gap) or rephrases/scaffolds (close but missed),
  then re-asks. The learner never advances on a gap.
- **Regeneration defeats memorization.** Re-asked questions test the *same
  concept via a different angle/surface*, not merely shuffled distractors. The
  generator is aware of previously asked stems and distractor sets per concept
  and must avoid reuse.
- **Remediation is content, not a question.** Re-teaching renders as a short
  content panel (grounded in existing `LearningContent` chunks) that the learner
  reads *before* being re-queried. The teaching moment and the assessment moment
  are separated.
- **Escalation valve.** Repeated failure on a concept steps down to an easier
  widget type, and after a cap the concept is flagged for review rather than
  looping forever.
- **Free-text is first-class, not abandoned.** Outcomes explicitly marked as
  explanation or coding stay on a free-text path judged by the LLM. Not every
  concept fits a widget.

## 2. Current State (what exists, what changes)

### Keep
- Data model: `Course / Lesson / LearningOutcome / LearningContent /
  AssessmentSession / OutcomeProgress / QuestionAnswer` (`app/models.py`).
- LangGraph orchestration + `PostgresSaver` checkpointer for session continuity
  (`app/services/graph.py`).
- Auth (cookie-based, role-based: Admin / Content Manager / Learner).
- Content management dashboard and SQLAdmin.
- Frontend stack: Jinja2 + HTMX + Alpine.js + custom CSS.
- `pgvector` embeddings on `LearningContent` (modeled but not yet wired up —
  v3 finally uses them, see §6/M6).

### Change
- **`LessonState`** (`app/services/graph.py:17`) is string-based
  (`last_question: str`, `last_response: str`). Needs structured
  `question_payload`, `learner_response_payload`, and a new `questions_asked`
  field per concept to support regeneration without repetition.
- **Graph nodes** — `re_teach` and `rephrase` were collapsed into
  `generate_question` in the v2 simplification. Restore them as distinct nodes;
  add `judge` and `select_widget_type` nodes.
- **`QuestionAnswer` model** (`app/models.py:169`) — `question: str` cannot
  carry a structured payload. Add JSON payload columns (see §9).
- **`assessment.html` + `partials/`** — chat renderer is replaced by per-type
  widget renderers plus a remediation content panel.
- **`assessment.js`** — answer submission changes from free-text to
  widget-state-to-payload serialization.

## 3. Architecture: the new graph

Proposed nodes and edges (to be validated against the v1 implementation):

1. **`choose_outcome`** — unchanged in spirit; pick first outcome < 0.8 mastery.
2. **`select_widget_type`** *(new)* — given concept + outcome type + attempt
   count + prior widget types used, pick the next widget type (MCQ / true-false /
   matching / ordering / categorization / fill-in / free-text). Owns the
   escalation logic.
3. **`generate_question`** — emits a **structured payload** (schema per widget
   type) instead of prose. Grounded in `LearningContent` via RAG when chunks
   exist (see §6).
4. **`judge`** *(new, load-bearing)* — hybrid: deterministic
   schema/correct-answer/distractor-uniqueness checks first, then LLM judge only
   on payloads that pass rules. Can reject → regenerate (capped at N=3).
5. **`render`** — backend renders the payload to HTML via a per-type Jinja
   partial; HTMX swaps it into the page.
6. **`assess_answer`** — deterministic scoring against the payload's known
   correct answer; maps result to targeted concept(s); updates
   `concepts_covered` and mastery.
7. **`route_after_assess`** *(new router)* — if wrong: decide re-teach vs
   rephrase based on score band + which concept was missed. If right but
   outcome not mastered: next concept. If outcome mastered: next outcome. If
   attempts exhausted: escalate or flag.
8. **`re_teach`** *(restored)* — renders a content panel from `LearningContent`
   chunks (RAG) for the missed concept. Then loops back to
   `select_widget_type` (regenerate, never reuse).
9. **`rephrase`** *(restored)* — lighter-touch scaffold for "close but missed";
   also loops back to regenerate.

## 4. Widget types — v1 scope

**Proposed v1: single-answer MCQ only, end-to-end**, to prove the loop
(generator → judge → payload → renderer → scorer → remediation → regeneration).
Then add types in order of value and implementation cost:

1. Single-answer MCQ *(v1)*
2. True/False
3. Matching pairs
4. Drag-and-drop ordering
5. Drag-and-drop categorization
6. Fill-in-the-blank
7. Free-text / coding tasks *(already partially exists as the v2 chat path)*

This sequencing is a recommendation; the user's selections may reorder it. No
parallel widget work — one type at a time, milestone-gated.

## 5. Judge design

**Hybrid: rules first, LLM judge second.**

Deterministic rules (run on every generated payload):
- Schema valid for the widget type.
- Exactly one correct answer marked (for MCQ/true-false).
- Distractors unique; no distractor duplicates the correct answer.
- Stem is non-empty and not a duplicate of a previously asked stem for this
  concept.
- Concept keyword(s) present in stem or correct option (concept alignment
  smoke test).

LLM judge (runs only on payloads that pass rules):
- Checks for ambiguity, misleading stems, plausible-but-arguably-correct
  distractors, and whether the question actually tests the targeted concept.
- Can reject; rejection triggers regeneration up to N=3.
- After N=3 rejections: fall back to the last passing payload with a warning
  logged, rather than blocking the learner indefinitely.

Rationale: rules catch the cheap, common errors without token cost; the LLM
judge catches semantic errors rules can't. This is load-bearing — a bad MCQ
teaches the wrong thing and the learner can't argue.

## 6. Scoring

- **Objective widgets (MCQ, true-false, matching, ordering, categorization,
  fill-in):** deterministic exact/partial match against the payload's known
  correct answer. Result maps to the targeted concept(s) and updates mastery
  directly. No LLM call for scoring.
- **Free-text / coding:** LLM-scored (as in v2), with the structured concept
  mapping preserved.
- **Feedback copy (optional):** LLM may be used to generate the
  encouraging/explanatory message shown after scoring, *separate* from the
  score itself. Decision deferred — deterministic templated feedback may be
  sufficient for v1.

## 7. Content sourcing

**RAG-grounded generation when `LearningContent` chunks exist; outcome-only
fallback otherwise.**

- Retrieve relevant chunks for the targeted concept via the existing pgvector
  embeddings (finally wiring up the unused column on `LearningContent`).
- Ground question generation in retrieved chunks to reduce hallucination and
  keep questions aligned with what was actually taught.
- If no chunks exist for a concept, fall back to generating from the learning
  outcome description + key concepts alone.

This uses infrastructure already modeled but not yet exercised, and meaningfully
improves question quality.

## 8. Rendering approach

**Per-type Jinja partials server-side, with Alpine.js handling in-widget
interaction state.**

- Backend receives the structured payload, selects the matching Jinja partial
  (e.g. `partials/widgets/mcq.html`), renders HTML, HTMX swaps it in.
- Alpine handles client-side interaction state (option selection, drag events,
  live validation) and posts a structured answer payload back via HTMX.
- Remediation content renders through its own partial
  (e.g. `partials/remediation/teach_panel.html`), separate from widget
  partials.

No new JS framework. Matches the existing stack.

## 9. Remediation & escalation flow

### Score-band routing
- **< 20%** → `re_teach` (content panel grounded in `LearningContent`) →
  regenerate question → re-ask.
- **20–80%** → `rephrase` (scaffold: acknowledge what was right, hint at what's
  missing) → regenerate question → re-ask.
- **≥ 80%** → mastery achieved; advance to next concept or outcome.

### Regeneration constraint
The generator receives `questions_asked[concept]` — a list of
`{ stem, widget_type, distractors }` — and must produce a question that avoids
reusing prior stems or distractor sets. The intent is to vary the *angle*, not
shuffle options.

### Escalation
After **K** failed attempts on the *same widget type* for a concept:
1. Step down to an easier widget type (e.g. MCQ → true/false, or MCQ with fewer
   options).
2. After the escalation cap is reached, flag the concept as "needs review"
   rather than looping indefinitely.

Open: what the terminal "needs review" state does — block advancement, allow
advance with a flag, or notify a teacher. To be decided during M4.

## 10. Data model changes

### `LessonState` (TypedDict in `app/services/graph.py`)
Add:
- `question_payload: dict` — the structured question (schema per widget type).
- `learner_response: dict` — the learner's structured answer.
- `questions_asked: dict[str, list[dict]]` — per concept, history of
  `{ stem, widget_type, distractors }` to drive non-repeating regeneration.
- `widget_history: dict[str, list[str]]` — per concept, widget types already
  used (drives escalation).
- `attempt_count_per_concept: dict[str, int]` — drives the escalation valve.

### `QuestionAnswer` (SQLModel in `app/models.py`)
Add:
- `question_payload: Optional[str]` — JSON-serialized structured question.
- `response_payload: Optional[str]` — JSON-serialized learner response.
- `widget_type: Optional[str]` — the widget type used for this turn.

Keep `question` / `answer` as denormalized text for admin and history
readability (e.g. `question` becomes the stem for MCQ, `answer` becomes the
selected option label).

### `LearningOutcome`
Consider:
- `assessable_as: Optional[str]` — marks outcomes that should stay on the
  free-text path (e.g. `"explanation"`, `"coding"`). Default null = widget.

## 11. Open questions

Still to be confirmed by the user (captured here so the doc is self-contained):
- **Widget types for v1** — recommendation is single-answer MCQ only.
- **Judge design** — recommendation is hybrid rules + LLM judge (§5).
- **Scoring model** — recommendation is deterministic for objective widgets,
  LLM for free-text (§6).
- **Rendering approach** — recommendation is server-side Jinja partials +
  Alpine for interaction state (§8).
- **Fate of existing chat path** — recommendation is keep as fallback for
  explanation/coding outcomes.
- **Content sourcing** — recommendation is RAG when chunks exist, outcome-only
  fallback (§7).
- **Terminal "needs review" state behavior** (§9).

## 12. Sequencing / milestones

- **M1 — Structured payload schema for MCQ + judge + deterministic scorer.**
  No UI yet; prove the contract via tests. Exit criteria: a test can call
  `generate_question` → `judge` → `assess_answer` and assert a correct and
  incorrect answer score correctly.
- **M2 — MCQ renderer partial + HTMX round-trip + new `LessonState` wired
  end-to-end**, replacing the chat path for one test lesson. Exit criteria: a
  learner can complete a full MCQ-based assessment for a single lesson in the
  browser.
- **M3 — Restore `re_teach` / `rephrase` as real nodes** with regeneration
  driven by `questions_asked` tracking. Exit criteria: a wrong answer triggers
  a teach panel then a *different* MCQ on the same concept.
- **M4 — Escalation valve + attempt caps.** Exit criteria: after K failures on
  MCQ, the system steps down to an easier type; after the cap, the concept is
  flagged.
- **M5 — Second widget type** (whichever the user picks) — validate the pattern
  generalizes. Exit criteria: two widget types coexist in one assessment,
  selected by `select_widget_type`.
- **M6 — RAG grounding into `LearningContent`** — wire up the unused pgvector
  embeddings. Exit criteria: generated questions demonstrably reference
  stored content chunks.
- **M7 — Migrate remaining outcomes/lessons; retire or scope-down the old chat
  path** (kept as free-text fallback for explanation/coding outcomes).

No milestone starts before the previous one's exit criteria are met. No
parallel widget-type work.

## 13. Risks & mitigations

- **Judge false-negatives blocking valid questions** → cap regeneration at N=3;
  fall back to the last passing payload with a warning logged.
- **Token cost from regenerate loops** → hard cap; cache judged payloads by
  hash to avoid re-judging identical content.
- **Widget-type proliferation** → strict one-type-at-a-time milestones; no
  parallel widget work.
- **Learner frustration from escalation** → design the "needs review" terminal
  state carefully; don't silently trap the learner.
- **Migration of existing assessment sessions** → version the state schema;
  old sessions either complete on the v2 path or are marked read-only. Do not
  attempt live in-place migration.
- **README vs. code drift (pre-existing)** → update README as part of M2, not
  at the end, so the doc and the code don't diverge again.

---

**Guiding line:** AIMS v3 keeps the original promise — every learner reaches
mastery, one concept at a time — but changes the surface from "type to prove
it" to "interact to prove it," with a judge the system trusts enough to score
deterministically.
