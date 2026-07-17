"""
Question generator for AIMS v3 interactive widgets.

Produces structured QuestionPayload objects (not prose) targeted at a specific
concept gap. The generator is aware of previously asked questions for the
concept (via GenerationContext.questions_asked) and is instructed to avoid
reusing stems or distractor sets — this is what defeats memorization on
re-asks after remediation (PLAN_v3.md §9).

Two implementations:
- `MCQGenerator` — uses ChatOpenAI.with_structured_output(MCQPayload) so the
  LLM's output is Pydantic-validated on construction. Grounding in
  LearningContent via RAG lands in M6; M1 generates from outcome + concepts.
- `StubGenerator` — returns a hand-crafted payload, for tests that need to
  exercise the judge/scorer contract without an API key.

The generator only produces a payload; judging and the regenerate-on-reject
loop live in judge.judge_or_regenerate, which wraps any generator callable.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.services.widgets.schema import (
    GenerationContext,
    MCQOption,
    MCQPayload,
    QuestionPayload,
)
from app.services.widgets.llm import build_llm, llm_available, LLMConfigError

logger = logging.getLogger(__name__)


class GeneratorError(RuntimeError):
    """Raised when a generator cannot produce a valid payload."""


class StubGenerator:
    """Deterministic generator for tests. Ignores context except concept_tested.

    Produces a valid, varied MCQ payload. When `fail_rules_n_times` is set,
    the first N calls return a deliberately invalid payload (e.g. two correct
    options, duplicate distractors) so tests can exercise the
    judge_or_regenerate loop.
    """

    def __init__(self, fail_rules_n_times: int = 0):
        self._fail_remaining = fail_rules_n_times
        self._call_count = 0

    def __call__(self, context: GenerationContext) -> QuestionPayload:
        self._call_count += 1
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            # Invalid: two correct options — Pydantic validator will reject at
            # construction, so build via model_construct to bypass and let the
            # rules validator catch it. Actually our schema's field_validator
            # runs on construction; to return an invalid payload we must bypass.
            return MCQPayload.model_construct(
                widget_type="mcq_single",
                concept_tested=context.targeted_concept,
                stem=f"Stub question {self._call_count} about {context.targeted_concept}?",
                options=[
                    MCQOption(id="a", text="Option A", is_correct=True),
                    MCQOption(id="b", text="Option B", is_correct=True),  # invalid
                    MCQOption(id="c", text="Option C", is_correct=False),
                ],
                explanation=None,
                difficulty=None,
            )
        # Valid payload, varied by call count so dedup rules see fresh stems.
        # M4: honor the escalation step-down directive — produce the easier
        # 2-option form when the context requests it.
        if context.target_option_count == 2:
            return MCQPayload(
                concept_tested=context.targeted_concept,
                stem=f"Stub question {self._call_count} (easier): which best describes '{context.targeted_concept}'?",
                options=[
                    MCQOption(id="a", text=f"Correct description of {context.targeted_concept} (v{self._call_count})", is_correct=True),
                    MCQOption(id="b", text=f"A clearly wrong distractor (v{self._call_count})", is_correct=False),
                ],
                explanation=f"{context.targeted_concept} is a key concept of {context.outcome_description}.",
                difficulty="easy",
            )
        return MCQPayload(
            concept_tested=context.targeted_concept,
            stem=f"Stub question {self._call_count}: which best describes '{context.targeted_concept}'?",
            options=[
                MCQOption(id="a", text=f"Correct description of {context.targeted_concept}", is_correct=True),
                MCQOption(id="b", text="A plausible but incorrect distractor", is_correct=False),
                MCQOption(id="c", text="Another unrelated distractor", is_correct=False),
                MCQOption(id="d", text="A clearly wrong distractor", is_correct=False),
            ],
            explanation=f"{context.targeted_concept} is a key concept of {context.outcome_description}.",
            difficulty="medium",
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class MCQGenerator:
    """LLM-driven generator for single-answer MCQ payloads.

    Uses ChatOpenAI.with_structured_output so the model's response is parsed
    directly into an MCQPayload; schema violations surface as Pydantic
    ValidationError, which judge_or_regenerate treats as a failed attempt.
    """

    # Shared requirements for every MCQ. Option-count and id-lettering rules
    # are NOT here — they vary with the escalation rung and are added by
    # _system_prompt() so the prompt never contradicts itself (a contradictory
    # prompt makes models follow the first rule and ignore the override).
    BASE_PROMPT = (
        "You are an expert assessment designer. Generate a single multiple-choice "
        "question that tests the SPECIFIC targeted concept. Requirements:\n"
        "- Exactly one correct option.\n"
        "- Distractors must be plausible but unambiguously wrong.\n"
        "- The stem must be clear and self-contained.\n"
        "- Do NOT reuse any previously asked stem or option text (provided below).\n"
        "- The question must genuinely test the targeted concept, not adjacent ones.\n"
        "- Provide a brief explanation of why the correct answer is correct.\n"
        "- Vary the angle/surface of the question from any prior attempts; do not "
        "just rephrase the same question.\n"
    )

    FULL_FORM_RULES = (
        "- 3-4 options total (including the correct one).\n"
        "- Option ids must be 'a','b','c','d'.\n"
    )

    # M4 escalation step-down (PLAN_v3.md §9): used when the context requests
    # the easier 2-option form after repeated failure.
    STEP_DOWN_RULES = (
        "- ESCALATION STEP-DOWN: this learner has repeatedly struggled with this "
        "concept, so generate the EASIER form.\n"
        "- Exactly 2 options total (one correct, one distractor). Option ids 'a','b'.\n"
        "- Test simple recognition of the concept, not nuanced discrimination.\n"
        "- The distractor must be clearly wrong to a learner who grasped the basics.\n"
        "- Set difficulty to 'easy'.\n"
    )

    @staticmethod
    def _system_prompt(context: GenerationContext) -> str:
        if context.target_option_count == 2:
            return MCQGenerator.BASE_PROMPT + MCQGenerator.STEP_DOWN_RULES
        return MCQGenerator.BASE_PROMPT + MCQGenerator.FULL_FORM_RULES

    def __init__(self, llm=None):
        if llm is None:
            try:
                llm = build_llm(temperature=0.7)
            except LLMConfigError as e:
                raise GeneratorError(str(e)) from e
        self.llm = llm

    def __call__(self, context: GenerationContext) -> QuestionPayload:
        prior_block = "None yet"
        if context.questions_asked:
            prior_block = "\n".join(
                f"- stem: '{q.stem}' | options: {q.option_texts}"
                for q in context.questions_asked
            )
        human = (
            f"Topic: {context.topic}\n"
            f"Learning outcome: {context.outcome_description}\n"
            f"Targeted concept: {context.targeted_concept}\n"
            f"All key concepts for this outcome: {context.key_concepts}\n"
            f"Previously asked questions (DO NOT REUSE these stems or options):\n{prior_block}\n"
            f"Failed attempts so far: {context.failed_attempts}\n\n"
            f"Generate a fresh multiple-choice question targeting '{context.targeted_concept}'."
        )
        try:
            structured = self.llm.with_structured_output(MCQPayload)
            payload = structured.invoke([
                ("system", self._system_prompt(context)),
                ("human", human),
            ])
        except Exception as e:
            logger.warning(f"MCQGenerator LLM call failed: {e}")
            raise GeneratorError(str(e)) from e
        return self._enforce_option_count(payload, context.target_option_count)

    @staticmethod
    def _enforce_option_count(
        payload: QuestionPayload, target_option_count: Optional[int]
    ) -> QuestionPayload:
        """M4 safety net: trim an over-long MCQ down to the requested rung.

        Even with a non-contradictory prompt a model can miscount. Dropping
        surplus distractors keeps the payload valid (exactly-one-correct,
        uniqueness, etc. are re-checked by the judge afterwards), and is
        exactly what "MCQ with fewer options" means (PLAN_v3.md §9). Only
        ever trims — never invents options to pad.
        """
        if (
            target_option_count is None
            or not isinstance(payload, MCQPayload)
            or len(payload.options) <= target_option_count
        ):
            return payload
        correct = payload.correct_option
        distractors = [o for o in payload.options if not o.is_correct]
        kept = [correct] + distractors[: target_option_count - 1]
        letters = "abcdef"
        trimmed = [
            MCQOption(id=letters[i], text=o.text, is_correct=o.is_correct)
            for i, o in enumerate(kept)
        ]
        logger.info(
            f"Trimmed MCQ from {len(payload.options)} to {len(trimmed)} options "
            f"(escalation step-down)."
        )
        return payload.model_copy(update={"options": trimmed})


def make_generator(context: GenerationContext, llm=None) -> "callable":
    """Factory: returns a callable taking no args that produces a QuestionPayload.

    The returned callable closes over `context` so it matches the
    judge_or_regenerate(generate_fn, ...) signature.

    Provider selection: an explicit `llm` wins; otherwise if any LLM provider
    is configured via env (OpenRouter or OpenAI, see llm.py) the MCQGenerator
    is used; otherwise fall back to StubGenerator so tests run without a key.
    """
    if llm is not None:
        gen = MCQGenerator(llm=llm)
    elif llm_available():
        gen = MCQGenerator()
    else:
        gen = StubGenerator()
    def _generate() -> QuestionPayload:
        return gen(context)
    return _generate
