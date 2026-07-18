"""
M5 end-to-end smoke test: second widget type (true/false) + select_widget_type.

Covers the M5 exit criteria from PLAN_v3.md §12 — "two widget types coexist in
one assessment, selected by select_widget_type" — plus the §9 ladder decision
confirmed with the user: true/false REPLACES M4's interim 2-option-MCQ rung
(fresh + wrong #1 → full MCQ; wrong #2 → true/false; wrong #3 → needs_review
cap), and TF is escalation-only (never picked for a fresh concept).

  Phase A — TF contract (provider-independent, no DB):
    deterministic scorer (correct/wrong/type-mismatch), rules validator
    (valid/short/off-concept/stem-reuse), stub + factory type dispatch,
    select_widget_type thresholds, submission mapping.

  Phase B — coexistence end-to-end (DB + service):
    full MCQ → wrong → MCQ regen → wrong → TRUE/FALSE regen on the same
    concept (select_widget_type stepped down) → correct TF → concept covered
    → advance → fresh concept is a full MCQ again. The session's
    QuestionAnswer rows contain BOTH widget types — the exit criterion.

  Phase C — TF failure feeds the same cap:
    wrong MCQ, wrong MCQ (TF appears), wrong TF → escalation cap fires on the
    same concept (needs_review flagged, advance). The stepped-down rung is not
    a free pass.

Requires:
- scripts/migrate_m2_widget_payload.py applied
- scripts/seed_m2_widget_lesson.py run (creates the test lesson)
- OPENROUTER_API_KEY / OPENAI_API_KEY in .env, OR the StubGenerator fallback
  (assertions are provider-independent: types and stems only, never option sets).

Run: uv run python scripts/test_m5_true_false.py
Exit 0 = all checks passed.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    AssessmentSession,
    LearningOutcome,
    OutcomeProgress,
    QuestionAnswer,
    User,
)
from app.services.widgets.llm import provider_name
from app.services.widgets.judge import RulesValidator
from app.services.widgets.scorer import score_answer, ScoringError
from app.services.widgets.schema import (
    GenerationContext,
    JudgeContext,
    MCQPayload,
    MCQResponse,
    MCQOption,
    TrueFalsePayload,
    TrueFalseResponse,
    WidgetType,
)
from app.services.widgets.generator import StubGenerator, make_generator
from app.services.widget_assessment import (
    WidgetAssessmentError,
    WidgetAssessmentService,
)

LESSON_TITLE = "Vegetable Gardening — Widget Assessment"

_failures = []
_passes = []


def check(name, condition, detail=""):
    if condition:
        _passes.append(name)
    else:
        _failures.append(f"{name}: {detail}" if detail else name)
        print(f"  FAIL: {name}: {detail}")


def _submit_wrong(payload) -> str:
    """The form value that answers the given payload incorrectly."""
    if isinstance(payload, TrueFalsePayload):
        return "false" if payload.is_true else "true"
    wrong = [o for o in payload.options if not o.is_correct]
    if not wrong:
        raise AssertionError("MCQ payload has no wrong options to pick")
    return wrong[0].id


def _submit_correct(payload) -> str:
    if isinstance(payload, TrueFalsePayload):
        return "true" if payload.is_true else "false"
    return payload.correct_option.id


def _new_assessment(session, lesson_id, learner_id) -> int:
    assessment = AssessmentSession(
        session_id=str(uuid.uuid4()),
        user_id=learner_id,
        lesson_id=lesson_id,
        status="in_progress",
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return assessment.id


def _tf(stem="Compost improves soil structure.", is_true=True, concept="soil"):
    return TrueFalsePayload(concept_tested=concept, stem=stem, is_true=is_true)


def main():
    print("M5 true/false widget smoke test")
    print("=" * 60)
    load_dotenv()
    print(f"LLM provider: {provider_name() or 'stub (no key)'}")

    # ------------------------------------------------------------------
    # Phase A — TF contract (no DB, provider-independent)
    # ------------------------------------------------------------------
    print("\n[Phase A] true/false contract")

    # Scorer
    r = score_answer(_tf(is_true=True), TrueFalseResponse(answer=True))
    check("A: TF correct scores 1.0", r.is_correct and r.score == 1.0)
    check("A: TF correct maps concept", r.concepts_addressed == ["soil"])
    check("A: TF correct_option_id is 'true'", r.correct_option_id == "true")
    r = score_answer(_tf(is_true=False), TrueFalseResponse(answer=True))
    check("A: TF wrong scores 0.0", not r.is_correct and r.score == 0.0)
    check("A: TF wrong maps no concepts", r.concepts_addressed == [])
    check("A: TF correct_option_id is 'false'", r.correct_option_id == "false")
    try:
        score_answer(_tf(), MCQResponse(selected_option_id="a"))
        check("A: TF payload + MCQResponse raises", False)
    except ScoringError:
        check("A: TF payload + MCQResponse raises", True)
    try:
        score_answer(
            MCQPayload(
                concept_tested="soil",
                stem="Which best describes healthy garden soil?",
                options=[
                    MCQOption(id="a", text="Dark and crumbly", is_correct=True),
                    MCQOption(id="b", text="Blue and glowing", is_correct=False),
                ],
            ),
            TrueFalseResponse(answer=True),
        )
        check("A: MCQ payload + TrueFalseResponse raises", False)
    except ScoringError:
        check("A: MCQ payload + TrueFalseResponse raises", True)

    # Rules validator
    rules = RulesValidator()
    ctx = JudgeContext(outcome_key="T1", valid_concepts=["soil"])
    check("A: valid TF passes rules",
          rules.validate(_tf(), ctx).valid,
          f"{rules.validate(_tf(), ctx).issues}")
    check("A: short statement rejected",
          not rules.validate(_tf(stem="Soil."), ctx).valid)
    check("A: off-concept TF rejected",
          not rules.validate(_tf(concept="compost"), ctx).valid)
    from app.services.widgets.schema import AskedQuestionRef
    reuse_ctx = JudgeContext(
        outcome_key="T1", valid_concepts=["soil"],
        questions_asked=[AskedQuestionRef(
            widget_type=WidgetType.TRUE_FALSE,
            stem="Compost improves soil structure.",
        )],
    )
    check("A: statement reuse rejected",
          not rules.validate(_tf(), reuse_ctx).valid)

    # select_widget_type thresholds (escalation-only TF)
    swt = WidgetAssessmentService.select_widget_type
    k_step = WidgetAssessmentService.STEP_DOWN_THRESHOLD
    check("A: fresh concept -> MCQ", swt(0) == WidgetType.MCQ_SINGLE)
    check("A: one failure -> MCQ", swt(1) == WidgetType.MCQ_SINGLE)
    check("A: at threshold -> TF", swt(k_step) == WidgetType.TRUE_FALSE)
    check("A: above threshold -> TF", swt(k_step + 1) == WidgetType.TRUE_FALSE)

    # Stub + factory type dispatch
    stub = StubGenerator()
    tf_gen = make_generator(GenerationContext(
        topic="t", outcome_description="d", outcome_key="T1",
        key_concepts=["soil"], targeted_concept="soil",
        target_widget_type=WidgetType.TRUE_FALSE,
    ))
    # make_generator may return LLM or stub depending on env; force stub for
    # the deterministic shape check.
    stub_tf = stub(GenerationContext(
        topic="t", outcome_description="d", outcome_key="T1",
        key_concepts=["soil"], targeted_concept="soil",
        target_widget_type=WidgetType.TRUE_FALSE,
    ))
    check("A: stub honors TF directive",
          isinstance(stub_tf, TrueFalsePayload) and stub_tf.difficulty == "easy")
    produced = tf_gen()
    check("A: factory produces TF payloads when directed",
          isinstance(produced, TrueFalsePayload),
          f"got {type(produced).__name__}")
    stub_mcq = stub(GenerationContext(
        topic="t", outcome_description="d", outcome_key="T1",
        key_concepts=["soil"], targeted_concept="soil",
    ))
    check("A: stub default stays MCQ", isinstance(stub_mcq, MCQPayload))

    # Submission mapping
    resp = WidgetAssessmentService._response_from_submission(_tf(), "true")
    check("A: 'true' maps to TrueFalseResponse(True)",
          isinstance(resp, TrueFalseResponse) and resp.answer is True)
    resp = WidgetAssessmentService._response_from_submission(_tf(), "False")
    check("A: 'False' (case-insensitive) maps to False",
          isinstance(resp, TrueFalseResponse) and resp.answer is False)
    try:
        WidgetAssessmentService._response_from_submission(_tf(), "banana")
        check("A: invalid TF submission raises", False)
    except WidgetAssessmentError:
        check("A: invalid TF submission raises", True)
    mcq_p = MCQPayload(
        concept_tested="soil", stem="Which best describes healthy garden soil?",
        options=[
            MCQOption(id="a", text="Dark and crumbly", is_correct=True),
            MCQOption(id="b", text="Blue and glowing", is_correct=False),
        ],
    )
    resp = WidgetAssessmentService._response_from_submission(mcq_p, "b")
    check("A: MCQ submission still maps to MCQResponse",
          isinstance(resp, MCQResponse) and resp.selected_option_id == "b")

    print("[Phase A] done")

    # ------------------------------------------------------------------
    # Phase B/C — end-to-end against the real database
    # ------------------------------------------------------------------
    with Session(engine) as session:
        from app.models import Lesson
        lesson = session.exec(
            select(Lesson).where(Lesson.title == LESSON_TITLE)
        ).first()
        if not lesson or not lesson.use_widget_assessment:
            print("Test lesson not found or not flagged. Run "
                  "scripts/seed_m2_widget_lesson.py first.")
            return 1
        learner = session.exec(select(User)).first()
        learner_id = learner.id if learner else 1

        # ----------------------------------------------------------
        # Phase B — coexistence: MCQ -> MCQ -> TF (correct) -> MCQ
        # ----------------------------------------------------------
        sid = _new_assessment(session, lesson.id, learner_id)
        print(f"\n[Phase B] assessment id={sid}")

        service = WidgetAssessmentService(session, judge=None)
        start = service.start_assessment(sid)
        p0 = start["payload"]
        concept = p0.concept_tested
        check("B: fresh concept starts on full MCQ", isinstance(p0, MCQPayload),
              f"got {type(p0).__name__}")
        print(f"  concept='{concept}'  type={p0.widget_type.value}")

        r1 = service.process_answer(sid, _submit_wrong(p0))
        p1 = r1["next_payload"]
        check("B: wrong #1 -> MCQ regen on same concept",
              isinstance(p1, MCQPayload) and p1.concept_tested == concept,
              f"got {type(p1).__name__}")
        check("B: wrong #1 stem differs", p1.stem != p0.stem)
        print(f"  wrong #1 -> {p1.widget_type.value}")

        r2 = service.process_answer(sid, _submit_wrong(p1))
        p2 = r2["next_payload"]
        check("B: wrong #2 -> TRUE/FALSE on same concept (stepped down)",
              isinstance(p2, TrueFalsePayload) and p2.concept_tested == concept,
              f"got {type(p2).__name__}")
        check("B: wrong #2 step_down flag set",
              r2.get("remediation", {}).get("step_down") is True)
        check("B: TF statement differs from prior stems",
              p2.stem not in {p0.stem, p1.stem})
        print(f"  wrong #2 -> {p2.widget_type.value}: '{p2.stem[:60]}'")

        r3 = service.process_answer(sid, _submit_correct(p2))
        check("B: correct TF scored correct",
              r3["score_result"].is_correct is True)
        check("B: TF score maps the concept",
              r3["score_result"].concepts_addressed == [concept])
        p3 = r3["next_payload"]
        check("B: advance -> fresh concept is full MCQ again",
              isinstance(p3, MCQPayload) and p3.concept_tested != concept,
              f"got {type(p3).__name__} on {getattr(p3, 'concept_tested', None)}")

        # THE exit criterion: both widget types coexist in one assessment.
        types_seen = {
            row.widget_type for row in session.exec(
                select(QuestionAnswer).where(QuestionAnswer.session_id == sid)
            ).all() if row.widget_type
        }
        check("B: both widget types coexist in one session",
              types_seen == {WidgetType.MCQ_SINGLE.value, WidgetType.TRUE_FALSE.value},
              f"got {types_seen}")

        _cleanup_session(session, sid)
        print("[Phase B] passed ✓")

        # ----------------------------------------------------------
        # Phase C — TF wrong at the rung feeds the same cap
        # ----------------------------------------------------------
        sid = _new_assessment(session, lesson.id, learner_id)
        k = WidgetAssessmentService.MAX_FAILED_ATTEMPTS_PER_CONCEPT
        print(f"\n[Phase C] assessment id={sid}  (K={k})")

        service = WidgetAssessmentService(session, judge=None)
        start = service.start_assessment(sid)
        payload = start["payload"]
        target_concept = payload.concept_tested
        print(f"  target concept='{target_concept}'")

        saw_tf = False
        capped = None
        for turn in range(1, k + 1):
            res = service.process_answer(sid, _submit_wrong(payload))
            nxt = res["next_payload"]
            print(f"  [{turn}] wrong on {payload.widget_type.value}"
                  + (f" -> {nxt.widget_type.value}" if nxt else " -> (cap)"))
            if isinstance(payload, TrueFalsePayload):
                saw_tf = True
            if turn < k:
                check(f"C: turn {turn} not capped",
                      res.get("escalation_capped") is False)
                check(f"C: turn {turn} stays on concept",
                      nxt is not None and nxt.concept_tested == target_concept)
                payload = nxt
            else:
                capped = res

        check("C: the TF rung was exercised before the cap", saw_tf)
        check("C: cap fires at exactly K (TF failure counts)",
              capped is not None and capped.get("escalation_capped") is True)
        check("C: capped concept named",
              capped is not None and capped.get("capped_concept") == target_concept)
        review_rows = session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == sid)
            .where(QuestionAnswer.event_type == "needs_review")
        ).all()
        check("C: needs_review row persisted",
              len(review_rows) == 1, f"got {len(review_rows)}")

        _cleanup_session(session, sid)
        print("[Phase C] passed ✓")

    print("=" * 60)
    print(f"Passed: {len(_passes)}")
    print(f"Failed: {len(_failures)}")
    if _failures:
        print("\nFailures:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("\nAll M5 true/false smoke checks passed.")
    return 0


def _cleanup_session(session: Session, sid: int) -> None:
    qas = session.exec(
        select(QuestionAnswer).where(QuestionAnswer.session_id == sid)
    ).all()
    for q in qas:
        session.delete(q)
    progress = session.exec(
        select(OutcomeProgress).where(OutcomeProgress.session_id == sid)
    ).all()
    for p in progress:
        session.delete(p)
    assessment = session.get(AssessmentSession, sid)
    if assessment:
        session.delete(assessment)
    session.commit()


if __name__ == "__main__":
    sys.exit(main())
