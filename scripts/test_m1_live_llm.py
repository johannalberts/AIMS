"""
Live LLM smoke test for AIMS v3 M1 MCQ pipeline.

End-to-end exercise of the real provider path (OpenRouter or OpenAI) configured
in .env, complementing the offline contract tests in test_m1_mcq_contract.py.

This script:
- loads .env so OPENROUTER_API_KEY / OPENAI_API_KEY are picked up
- uses make_generator + judge_or_regenerate through the LIVE MCQGenerator
- validates the produced payload with the rules Judge
- scores both the correct option and a distractor with the deterministic Scorer
- prints the generated question and a summary

Run: uv run python scripts/test_m1_live_llm.py
Exit 0 = pass. Exit 1 = fail (or no provider configured).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.services.widgets.schema import (
    GenerationContext,
    JudgeContext,
    MCQResponse,
    WidgetType,
)
from app.services.widgets.judge import Judge, judge_or_regenerate
from app.services.widgets.scorer import score_answer, ScoringError
from app.services.widgets.generator import make_generator
from app.services.widgets.llm import llm_available, provider_name

TARGETED = "benefits"

_failures = []
_passes = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        _passes.append(name)
    else:
        _failures.append(f"{name}: {detail}" if detail else name)
        print(f"  FAIL: {name}: {detail}")


def gen_ctx(targeted: str = TARGETED) -> GenerationContext:
    return GenerationContext(
        topic="Vegetable Gardening",
        outcome_description="Understand the benefits and types of home vegetable gardens",
        outcome_key="garden_benefits",
        key_concepts=["benefits", "types", "sustainability"],
        targeted_concept=targeted,
        concepts_covered=[],
        questions_asked=[],
        failed_attempts=0,
        widget_history=[],
    )


def run() -> int:
    print("M1 live LLM smoke test")
    print("=" * 60)

    if not llm_available():
        print("No LLM provider configured (set OPENROUTER_API_KEY or OPENAI_API_KEY in .env).")
        return 1

    print(f"Provider: {provider_name()}")
    if os.getenv("OPENROUTER_API_KEY"):
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    else:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    print(f"Model:    {model}")
    print("-" * 60)

    ctx = gen_ctx()
    gen_fn = make_generator(ctx)
    judge = Judge()

    print("[1] generate -> judge (rules only)")
    payload, verdict, attempts = judge_or_regenerate(
        gen_fn, JudgeContext(outcome_key="garden_benefits",
                              valid_concepts=["benefits", "types", "sustainability"]),
        judge, max_attempts=3)
    check("returned a payload", payload is not None)
    check("verdict valid", verdict.valid, str(verdict.issues))
    check("used <= 3 attempts", attempts <= 3, f"attempts={attempts}")

    print()
    print(f"Stem:   {payload.stem}")
    print(f"Concept tested: {payload.concept_tested}")
    print("Options:")
    correct_id = None
    for o in payload.options:
        mark = "*" if o.is_correct else " "
        print(f"  [{mark}] {o.id}: {o.text}")
        if o.is_correct:
            correct_id = o.id
    if payload.explanation:
        print(f"Explanation: {payload.explanation}")

    print()
    print("[2] score correct answer")
    result = score_answer(payload, MCQResponse(selected_option_id=correct_id))
    print(f"  score={result.score} is_correct={result.is_correct} "
          f"concepts={result.concepts_addressed}")
    check("correct scores 1.0", result.score == 1.0, f"score={result.score}")
    check("concepts mapped to targeted",
          result.concepts_addressed == [TARGETED],
          f"got {result.concepts_addressed}")
    check("correct_option_id returned", result.correct_option_id == correct_id)

    print()
    print("[3] score wrong answer")
    wrong_id = next(o.id for o in payload.options if not o.is_correct)
    result_wrong = score_answer(payload, MCQResponse(selected_option_id=wrong_id))
    print(f"  score={result_wrong.score} is_correct={result_wrong.is_correct} "
          f"concepts={result_wrong.concepts_addressed}")
    check("wrong scores 0.0", result_wrong.score == 0.0, f"score={result_wrong.score}")
    check("wrong maps no concepts",
          result_wrong.concepts_addressed == [],
          f"got {result_wrong.concepts_addressed}")

    print()
    print("[4] schema fields")
    check("widget_type is mcq_single", payload.widget_type == WidgetType.MCQ_SINGLE,
          f"got {payload.widget_type}")
    check("exactly one correct option",
          sum(1 for o in payload.options if o.is_correct) == 1)
    check("3-4 options", 3 <= len(payload.options) <= 4,
          f"got {len(payload.options)}")
    check("ids are a/b/c/d",
          [o.id for o in payload.options] == ["a", "b", "c", "d"]
          or [o.id for o in payload.options] == ["a", "b", "c"],
          f"got {[o.id for o in payload.options]}")

    print("=" * 60)
    print(f"Passed: {len(_passes)}")
    print(f"Failed: {len(_failures)}")
    if _failures:
        print("\nFailures:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("\nAll live LLM smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run())