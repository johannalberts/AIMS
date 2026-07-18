"""
Question judge for AIMS v3 interactive widgets.

Hybrid design (PLAN_v3.md §5):
1. Rules validator — deterministic, runs on every generated payload. Catches
   schema violations, missing/extra correct answers, duplicate distractors,
   stem reuse, concept-alignment smoke test. No token cost.
2. LLM judge — runs only on payloads that pass rules. Catches semantic issues
   rules can't: ambiguity, misleading stems, plausible-but-arguably-correct
   distractors, off-concept questions. Optional in tests.

The judge is load-bearing: a bad MCQ teaches the wrong thing and the learner
can't argue. The generator calls `judge_or_regenerate` which loops up to N
times, regenerating on rejection, falling back to the last passing payload
with a warning after the cap.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.services.widgets.schema import (
    JudgeContext,
    MCQPayload,
    QuestionPayload,
    TrueFalsePayload,
    WidgetType,
)

logger = logging.getLogger(__name__)

# Hard cap on regeneration attempts. After this, fall back to the last
# rules-passing payload (even if the LLM judge rejected it) so the learner is
# never blocked indefinitely.
MAX_REGENERATION_ATTEMPTS = 3


@dataclass
class JudgeVerdict:
    """Outcome of judging a single payload."""
    valid: bool
    issues: List[str] = field(default_factory=list)
    # "rules" = caught by deterministic rules; "llm" = caught by LLM judge;
    # "schema" = Pydantic validation failure.
    source: str = "rules"

    @property
    def ok(self) -> bool:
        return self.valid and not self.issues


class RulesValidator:
    """Deterministic per-widget-type rule checks.

    Each method returns a JudgeVerdict with source="rules". Rules are cheap
    and catch the common, objective errors. The LLM judge handles the rest.
    """

    def validate(self, payload: QuestionPayload, context: JudgeContext) -> JudgeVerdict:
        dispatch = {
            WidgetType.MCQ_SINGLE: self._validate_mcq,
            WidgetType.TRUE_FALSE: self._validate_true_false,
        }
        handler = dispatch.get(payload.widget_type)
        if handler is None:
            return JudgeVerdict(valid=False, issues=[f"No rules validator for widget_type={payload.widget_type}"], source="rules")
        return handler(payload, context)

    def _validate_mcq(self, payload: MCQPayload, context: JudgeContext) -> JudgeVerdict:
        issues: List[str] = []

        # Exactly one correct option (defense-in-depth: schema also enforces
        # this on construction, but model_construct bypasses validation, and
        # the rules layer must be self-sufficient).
        correct = [o for o in payload.options if o.is_correct]
        if len(correct) != 1:
            issues.append(f"MCQ must have exactly one correct option, got {len(correct)}")

        # Option count within a sensible range
        if not (2 <= len(payload.options) <= 6):
            issues.append(f"MCQ must have 2-6 options, got {len(payload.options)}")

        # Option ids unique
        ids = [o.id for o in payload.options]
        if len(ids) != len(set(ids)):
            issues.append("Duplicate option ids")

        # Option texts unique (no duplicate distractors / no distractor == correct)
        texts = [o.text.strip().lower() for o in payload.options]
        if len(texts) != len(set(texts)):
            issues.append("Duplicate option texts")

        # No option text equals the stem (catches "all of the above"-style leakage)
        stem_l = payload.stem.strip().lower()
        if any(t == stem_l for t in texts):
            issues.append("An option text duplicates the stem")

        self._check_stem_and_concept(payload, context, issues)
        return JudgeVerdict(valid=not issues, issues=issues, source="rules")

    def _validate_true_false(self, payload: TrueFalsePayload, context: JudgeContext) -> JudgeVerdict:
        issues: List[str] = []
        # Stem/statement quality, concept alignment, and dedup are shared.
        # `is_true` is a bool by schema construction, so there is nothing
        # further to check deterministically — statement ambiguity and
        # trivial giveaways are the LLM judge's job.
        self._check_stem_and_concept(payload, context, issues)
        return JudgeVerdict(valid=not issues, issues=issues, source="rules")

    def _check_stem_and_concept(
        self, payload: QuestionPayload, context: JudgeContext, issues: List[str]
    ) -> None:
        """Checks shared by all widget types: stem non-trivial, concept
        alignment (smoke test — the LLM judge does deeper alignment), and no
        stem reuse for this concept."""
        stem_l = payload.stem.strip().lower()

        # Stem non-trivial
        if len(stem_l) < 10:
            issues.append("Stem too short (<10 chars)")

        # Concept alignment: targeted concept must be one of the valid concepts
        # for this outcome.
        if context.valid_concepts:
            if payload.concept_tested not in context.valid_concepts:
                issues.append(
                    f"concept_tested '{payload.concept_tested}' not in valid concepts "
                    f"{context.valid_concepts}"
                )

        # Stem reuse: generator must not re-ask the same stem for the same concept.
        prior_stems = {
            q.stem.strip().lower() for q in context.questions_asked
        }
        if stem_l in prior_stems:
            issues.append("Stem duplicates a previously asked question for this concept")


class LLMJudge:
    """Optional LLM-based semantic judge.

    Runs only on payloads that pass rules. Returns a verdict on ambiguity,
    plausibility of distractors, and whether the question truly tests the
    targeted concept. The LLM judge is intentionally optional so tests can
    exercise the rules + scorer contract without an API key.

    The implementation uses ChatOpenAI via LangChain (consistent with the
    existing graph.py). It is only constructed when an LLM is supplied.
    """

    def __init__(self, llm):
        self.llm = llm

    def judge(self, payload: QuestionPayload, context: JudgeContext) -> JudgeVerdict:
        # Minimal, focused prompt. Structured output would be ideal but the
        # verdict is simple enough to parse from a constrained format.
        prompt = self._build_prompt(payload, context)
        try:
            response = self.llm.invoke([("human", prompt)])
            return self._parse_response(response.content)
        except Exception as e:
            logger.warning(f"LLM judge call failed: {e}. Treating as valid (fail-open).")
            return JudgeVerdict(valid=True, source="llm")

    def _build_prompt(self, payload: QuestionPayload, context: JudgeContext) -> str:
        if isinstance(payload, MCQPayload):
            options_block = "\n".join(
                f"- [{('CORRECT' if o.is_correct else 'distractor')}] {o.text}"
                for o in payload.options
            )
            return (
                "You are an assessment quality reviewer. Judge this multiple-choice "
                "question for correctness, clarity, and concept alignment.\n\n"
                f"Outcome: {context.outcome_key}\n"
                f"Targeted concept: {payload.concept_tested}\n"
                f"Stem: {payload.stem}\n"
                f"Options:\n{options_block}\n\n"
                "Respond EXACTLY in this format:\n"
                "VERDICT: VALID or INVALID\n"
                "ISSUES: [comma-separated list of problems, or 'none']\n"
            )
        if isinstance(payload, TrueFalsePayload):
            return (
                "You are an assessment quality reviewer. Judge this true/false "
                "question for correctness, clarity, and concept alignment. Reject "
                "statements that are ambiguous, opinion-based, or trivially "
                "guessable without understanding the concept.\n\n"
                f"Outcome: {context.outcome_key}\n"
                f"Targeted concept: {payload.concept_tested}\n"
                f"Statement: {payload.stem}\n"
                f"Correct answer: {'TRUE' if payload.is_true else 'FALSE'}\n\n"
                "Respond EXACTLY in this format:\n"
                "VERDICT: VALID or INVALID\n"
                "ISSUES: [comma-separated list of problems, or 'none']\n"
            )
        return "VERDICT: VALID\nISSUES: none\n"

    def _parse_response(self, content: str) -> JudgeVerdict:
        verdict_line = next(
            (ln for ln in content.splitlines() if ln.strip().upper().startswith("VERDICT:")),
            "",
        )
        issues_line = next(
            (ln for ln in content.splitlines() if ln.strip().upper().startswith("ISSUES:")),
            "",
        )
        verdict_text = verdict_line.split(":", 1)[-1].strip().upper()
        issues_text = issues_line.split(":", 1)[-1].strip()
        valid = verdict_text.startswith("VALID") and not verdict_text.startswith("INVALID")
        issues: List[str] = []
        if issues_text and issues_text.lower() != "none":
            issues = [i.strip() for i in issues_text.split(",") if i.strip()]
        # If verdict said INVALID but issues said none, record a generic issue
        if not valid and not issues:
            issues = ["LLM judge rejected without specifying issues"]
        return JudgeVerdict(valid=valid, issues=issues, source="llm")


class Judge:
    """Hybrid judge: rules first, LLM judge second.

    Usage:
        verdict = judge.validate(payload, context)            # rules only
        verdict = judge.full_judge(payload, context)          # rules + LLM
    """

    def __init__(self, llm_judge: Optional[LLMJudge] = None):
        self.rules = RulesValidator()
        self.llm_judge = llm_judge

    def validate(self, payload: QuestionPayload, context: JudgeContext) -> JudgeVerdict:
        """Rules-only validation. Cheap, deterministic."""
        return self.rules.validate(payload, context)

    def full_judge(self, payload: QuestionPayload, context: JudgeContext) -> JudgeVerdict:
        """Rules first; if rules pass and an LLM judge is configured, run it."""
        rules_verdict = self.rules.validate(payload, context)
        if not rules_verdict.valid:
            return rules_verdict
        if self.llm_judge is None:
            return rules_verdict
        return self.llm_judge.judge(payload, context)


def judge_or_regenerate(
    generate_fn: Callable[[], QuestionPayload],
    context: JudgeContext,
    judge: Judge,
    max_attempts: int = MAX_REGENERATION_ATTEMPTS,
) -> tuple[QuestionPayload, JudgeVerdict, int]:
    """Loop: generate → judge → regenerate on rejection, up to max_attempts.

    Falls back to the last rules-passing payload if the LLM judge keeps
    rejecting after the cap, so the learner is never blocked indefinitely.
    Returns (payload, final_verdict, attempts_used).

    `generate_fn` is called fresh each attempt so the generator can produce a
    different question (the generator receives questions_asked via its own
    GenerationContext and avoids reuse).
    """
    last_rules_passing: Optional[QuestionPayload] = None
    last_rules_verdict: Optional[JudgeVerdict] = None

    for attempt in range(1, max_attempts + 1):
        payload = generate_fn()
        rules_verdict = judge.validate(payload, context)
        if rules_verdict.valid:
            last_rules_passing = payload
            last_rules_verdict = rules_verdict
            if judge.llm_judge is None:
                return payload, rules_verdict, attempt
            llm_verdict = judge.llm_judge.judge(payload, context)
            if llm_verdict.valid:
                return payload, llm_verdict, attempt
            logger.info(f"LLM judge rejected (attempt {attempt}): {llm_verdict.issues}")
            continue
        logger.info(f"Rules rejected (attempt {attempt}): {rules_verdict.issues}")

    if last_rules_passing is not None:
        logger.warning(
            f"judge_or_regenerate exhausted {max_attempts} attempts; "
            f"falling back to last rules-passing payload."
        )
        return last_rules_passing, last_rules_verdict, max_attempts

    raise ValueError(
        f"judge_or_regenerate could not produce a valid payload in {max_attempts} attempts"
    )
