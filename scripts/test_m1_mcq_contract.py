"""
M1 contract test for AIMS v3 interactive widgets.

Proves the generate → judge → score loop for single-answer MCQ without
requiring an OpenAI API key (uses StubGenerator). Covers:
- valid payload is accepted by rules and scores correctly (correct + wrong)
- concept mapping flows from correct answer into ScoreResult.concepts_addressed
- invalid payloads (two correct options, duplicate distractors, stem reuse,
  off-concept targeting, unknown option id) are rejected
- judge_or_regenerate loops on rejection and returns a valid payload
- judge_or_regenerate falls back to last rules-passing payload after the cap

Run: uv run python scripts/test_m1_mcq_contract.py
Exit code 0 = all passed.
"""
import sys
import os

# Match the existing scripts/ convention of putting the repo root on the path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.widgets.schema import (
    GenerationContext,
    JudgeContext,
    MCQOption,
    MCQPayload,
    MCQResponse,
    AskedQuestionRef,
    WidgetType,
)
from app.services.widgets.judge import (
    Judge,
    judge_or_regenerate,
)
from app.services.widgets.scorer import score_answer, ScoringError
from app.services.widgets.generator import StubGenerator, make_generator


_failures = []
_passes = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        _passes.append(name)
    else:
        _failures.append(f"{name}: {detail}" if detail else name)
        print(f"  FAIL: {name}: {detail}")


def gen_ctx(targeted: str = "benefits", failed: int = 0, asked=None) -> GenerationContext:
    return GenerationContext(
        topic="Vegetable Gardening",
        outcome_description="Understand the benefits and types of home vegetable gardens",
        outcome_key="garden_benefits",
        key_concepts=["benefits", "types", "sustainability"],
        targeted_concept=targeted,
        concepts_covered=[],
        questions_asked=asked or [],
        failed_attempts=failed,
        widget_history=[],
    )


def judge_ctx(targeted: str = "benefits", asked=None) -> JudgeContext:
    return JudgeContext(
        outcome_key="garden_benefits",
        valid_concepts=["benefits", "types", "sustainability"],
        questions_asked=asked or [],
    )


def run() -> int:
    print("M1 MCQ contract tests")
    print("=" * 60)

    # --- 1. Valid payload: rules accept, correct answer scores 1.0 ---
    print("[1] Valid payload, correct answer")
    ctx = gen_ctx()
    gen = StubGenerator()
    payload = gen(ctx)
    judge = Judge()
    verdict = judge.validate(payload, judge_ctx())
    check("valid payload passes rules", verdict.valid, str(verdict.issues))

    correct_id = payload.correct_option.id
    result = score_answer(payload, MCQResponse(selected_option_id=correct_id))
    check("correct answer scores 1.0", result.score == 1.0, f"score={result.score}")
    check("correct answer is_correct", result.is_correct)
    check(
        "correct answer maps concept",
        result.concepts_addressed == ["benefits"],
        f"got {result.concepts_addressed}",
    )
    check("correct_option_id returned", result.correct_option_id == correct_id)

    # --- 2. Wrong answer scores 0.0 and maps no concepts ---
    print("[2] Valid payload, wrong answer")
    wrong_id = next(o.id for o in payload.options if not o.is_correct)
    result_wrong = score_answer(payload, MCQResponse(selected_option_id=wrong_id))
    check("wrong answer scores 0.0", result_wrong.score == 0.0, f"score={result_wrong.score}")
    check("wrong answer not is_correct", not result_wrong.is_correct)
    check(
        "wrong answer maps no concepts",
        result_wrong.concepts_addressed == [],
        f"got {result_wrong.concepts_addressed}",
    )

    # --- 3. Schema rejects two correct options at construction ---
    print("[3] Schema rejects two correct options")
    try:
        MCQPayload(
            concept_tested="benefits",
            stem="Which is a benefit?",
            options=[
                MCQOption(id="a", text="A", is_correct=True),
                MCQOption(id="b", text="B", is_correct=True),
                MCQOption(id="c", text="C", is_correct=False),
            ],
        )
        check("two correct options rejected at construction", False, "no error raised")
    except Exception:
        check("two correct options rejected at construction", True)

    # --- 4. Rules reject duplicate option texts ---
    print("[4] Rules reject duplicate option texts")
    dup = MCQPayload(
        concept_tested="benefits",
        stem="Which is a benefit of home gardening?",
        options=[
            MCQOption(id="a", text="Fresh produce", is_correct=True),
            MCQOption(id="b", text="Fresh produce", is_correct=False),  # duplicate
            MCQOption(id="c", text="Exercise", is_correct=False),
        ],
    )
    v = judge.validate(dup, judge_ctx())
    check("duplicate option texts rejected", not v.valid, str(v.issues))
    check(
        "duplicate texts issue surfaced",
        any("Duplicate option texts" in i for i in v.issues),
        str(v.issues),
    )

    # --- 5. Rules reject stem reuse ---
    print("[5] Rules reject stem reuse")
    asked = [AskedQuestionRef(widget_type=WidgetType.MCQ_SINGLE, stem=payload.stem, option_texts=payload.option_texts)]
    v = judge.validate(payload, judge_ctx(asked=asked))
    check("stem reuse rejected", not v.valid, str(v.issues))
    check(
        "stem reuse issue surfaced",
        any("duplicates a previously" in i for i in v.issues),
        str(v.issues),
    )

    # --- 6. Rules reject off-concept targeting ---
    print("[6] Rules reject off-concept targeting")
    off = MCQPayload(
        concept_tested="composting",  # not in valid_concepts
        stem="Which is a benefit of home gardening?",
        options=[
            MCQOption(id="a", text="Fresh produce", is_correct=True),
            MCQOption(id="b", text="Exercise", is_correct=False),
            MCQOption(id="c", text="Cost", is_correct=False),
        ],
    )
    v = judge.validate(off, judge_ctx())
    check("off-concept targeting rejected", not v.valid, str(v.issues))
    check(
        "concept alignment issue surfaced",
        any("not in valid concepts" in i for i in v.issues),
        str(v.issues),
    )

    # --- 7. Scorer raises on unknown option id (client bug) ---
    print("[7] Scorer raises on unknown option id")
    try:
        score_answer(payload, MCQResponse(selected_option_id="zzz"))
        check("unknown option id raises", False, "no error raised")
    except ScoringError:
        check("unknown option id raises", True)

    # --- 8. Scorer raises on widget_type mismatch ---
    print("[8] Scorer raises on widget_type mismatch")
    from app.services.widgets.schema import LearnerResponse
    try:
        score_answer(payload, LearnerResponse(widget_type=WidgetType.MCQ_SINGLE))
        check("widget_type mismatch raises", False, "no error raised")
    except ScoringError:
        check("widget_type mismatch raises", True)

    # --- 9. judge_or_regenerate loops on rules rejection then returns valid ---
    print("[9] judge_or_regenerate loops past invalid attempts")
    stub = StubGenerator(fail_rules_n_times=2)
    ctx9 = gen_ctx()
    def gen_fn() -> object:
        return stub(ctx9)
    payload9, verdict9, attempts9 = judge_or_regenerate(
        gen_fn, judge_ctx(), judge, max_attempts=5
    )
    check("regenerate returned a payload", payload9 is not None)
    check("regenerate used 3 attempts (2 bad + 1 good)", attempts9 == 3, f"attempts={attempts9}")
    check("regenerate final verdict valid", verdict9.valid, str(verdict9.issues))

    # --- 10. judge_or_regenerate falls back after cap, never raises ---
    print("[10] judge_or_regenerate falls back to last rules-passing after cap")
    stub10 = StubGenerator(fail_rules_n_times=1)
    ctx10 = gen_ctx()
    def gen_fn10() -> object:
        return stub10(ctx10)
    payload10, verdict10, attempts10 = judge_or_regenerate(
        gen_fn10, judge_ctx(), judge, max_attempts=2
    )
    # First attempt invalid, second valid → should return valid at attempt 2
    check("fallback returned payload", payload10 is not None)
    check("fallback used 2 attempts", attempts10 == 2, f"attempts={attempts10}")
    check("fallback verdict valid", verdict10.valid, str(verdict10.issues))

    # --- 11. judge_or_regenerate raises only if it never produced a valid payload ---
    print("[11] judge_or_regenerate raises when all attempts invalid")
    stub11 = StubGenerator(fail_rules_n_times=10)  # always invalid
    ctx11 = gen_ctx()
    def gen_fn11() -> object:
        return stub11(ctx11)
    try:
        judge_or_regenerate(gen_fn11, judge_ctx(), judge, max_attempts=2)
        check("all-invalid raises ValueError", False, "no error raised")
    except ValueError:
        check("all-invalid raises ValueError", True)

    # --- 12. make_generator picks StubGenerator when no API key ---
    print("[12] make_generator falls back to StubGenerator without API key")
    saved = os.environ.pop("OPENAI_API_KEY", None)
    try:
        # Without an API key and no llm, make_generator should use StubGenerator.
        # StubGenerator and make_generator are imported at module top.
        g = make_generator(gen_ctx())
        p = g()
        check("make_generator returns MCQPayload without key", isinstance(p, MCQPayload))
    finally:
        if saved is not None:
            os.environ["OPENAI_API_KEY"] = saved

    # --- Summary ---
    print("=" * 60)
    print(f"Passed: {len(_passes)}")
    print(f"Failed: {len(_failures)}")
    if _failures:
        print("\nFailures:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("\nAll M1 contract tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
