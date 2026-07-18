"""
M3 end-to-end smoke test: re_teach / regenerate on wrong answer.

Drives `WidgetAssessmentService` directly (no HTTP, no templates) against the
real database, against the seeded M2 test lesson (course id=3, lesson id=3,
2 outcomes × 3 concepts). Covers the three M3 exit criteria from
PLAN_v3.md §12:

  1. A wrong answer triggers a teach panel (remediation dict) then a DIFFERENT
     MCQ on the same concept (different stem, different distractors).
  2. A correct answer advances to the next concept as before (M2 behavior).
  3. After K wrong attempts on the same concept, the system stops regenerating
     and advances (escalation_capped=True), with no infinite loop.

Requires:
- scripts/migrate_m2_widget_payload.py applied
- scripts/seed_m2_widget_lesson.py run (creates the test lesson)
- OPENROUTER_API_KEY / OPENAI_API_KEY in .env, OR the StubGenerator fallback
  (this script uses whichever `make_generator` picks inside the service).

Run: uv run python scripts/test_m3_remediation.py
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
from app.services.widgets.schema import MCQPayload, TrueFalsePayload, WidgetType
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


def _pick_wrong_option(payload) -> str:
    """Return the form value that answers `payload` incorrectly — an MCQ
    option id, or "true"/"false" for the true/false rung (M5)."""
    if isinstance(payload, TrueFalsePayload):
        return "false" if payload.is_true else "true"
    wrong = [o for o in payload.options if not o.is_correct]
    if not wrong:
        raise AssertionError("MCQ payload has no wrong options to pick")
    return wrong[0].id


def _option_texts(payload: MCQPayload) -> list[str]:
    return [o.text for o in payload.options]


def main():
    print("M3 remediation smoke test")
    print("=" * 60)
    load_dotenv()
    print(f"LLM provider: {provider_name() or 'stub (no key)'}")

    with Session(engine) as session:
        from app.models import Lesson
        lesson = session.exec(
            select(Lesson).where(Lesson.title == LESSON_TITLE)
        ).first()
        if not lesson or not lesson.use_widget_assessment:
            print("Test lesson not found or not flagged. Run "
                  "scripts/seed_m2_widget_lesson.py first.")
            return 1

        outcomes = session.exec(
            select(LearningOutcome)
            .where(LearningOutcome.lesson_id == lesson.id)
            .where(LearningOutcome.is_active == True)
            .order_by(LearningOutcome.order)
        ).all()
        total_concepts = sum(len(_parse_safe(o)) for o in outcomes)
        print(f"Lesson id={lesson.id}, outcomes={len(outcomes)}, "
              f"concepts={total_concepts}")
        print(f"K (escalation cap) = "
              f"{WidgetAssessmentService.MAX_FAILED_ATTEMPTS_PER_CONCEPT}")

        learner = session.exec(select(User)).first()
        learner_id = learner.id if learner else 1

        # --------------------------------------------------------------
        # Phase A — wrong -> teach -> regenerate (new stem) -> correct -> advance
        # --------------------------------------------------------------
        assessment = AssessmentSession(
            session_id=str(uuid.uuid4()),
            user_id=learner_id,
            lesson_id=lesson.id,
            status="in_progress",
        )
        session.add(assessment)
        session.commit()
        session.refresh(assessment)
        sid = assessment.id
        print(f"\n[Phase A] assessment id={sid}")

        service = WidgetAssessmentService(session, judge=None)
        start = service.start_assessment(sid)
        first_payload: MCQPayload = start["payload"]
        check("A: start emits MCQ", isinstance(first_payload, MCQPayload))
        first_concept = first_payload.concept_tested
        first_stem = first_payload.stem
        first_texts = _option_texts(first_payload)
        print(f"  initial concept='{first_concept}'  stem='{first_stem[:60]}...'")

        # Submit a WRONG answer.
        wrong_id = _pick_wrong_option(first_payload)
        print(f"  submitting WRONG option {wrong_id}")
        r1 = service.process_answer(sid, wrong_id)
        check("A: wrong scored incorrect",
              r1["score_result"].is_correct is False)
        check("A: remediation returned",
              r1.get("remediation") is not None,
              f"got {r1.get('remediation')}")
        check("A: remediation has concept",
              r1.get("remediation", {}).get("concept") == first_concept,
              f"got {r1.get('remediation', {}).get('concept')}")
        check("A: remediation has hint",
              bool(r1.get("remediation", {}).get("hint")))
        check("A: not capped on first wrong",
              r1.get("escalation_capped") is False)

        new_payload: MCQPayload = r1["next_payload"]
        check("A: next payload present after wrong", new_payload is not None)
        check("A: next payload is MCQ", isinstance(new_payload, MCQPayload))
        check("A: re-asks SAME concept",
              new_payload.concept_tested == first_concept,
              f"got {new_payload.concept_tested} expected {first_concept}")
        check("A: new stem differs from first",
              new_payload.stem != first_stem,
              f"stems matched: {first_stem!r}")
        check("A: new distractor set differs",
              set(_option_texts(new_payload)) != set(first_texts),
              f"option sets matched: {first_texts}")
        check("A: status still in_progress", r1["status"] == "in_progress")
        print(f"  regenerated stem='{new_payload.stem[:60]}...'")

        # Submit a CORRECT answer for the regenerated MCQ — should advance.
        correct_id = next(o.id for o in new_payload.options if o.is_correct)
        print(f"  submitting CORRECT option {correct_id}")
        r2 = service.process_answer(sid, correct_id)
        check("A: correct scored correct",
              r2["score_result"].is_correct is True)
        check("A: no remediation on correct",
              r2.get("remediation") is None)
        check("A: not capped on correct",
              r2.get("escalation_capped") is False)
        check("A: advances to a DIFFERENT concept",
              r2["next_payload"] is not None
              and r2["next_payload"].concept_tested != first_concept,
              f"got {r2['next_payload'].concept_tested if r2['next_payload'] else None}")
        print(f"  advanced to concept='{r2['next_payload'].concept_tested}'")

        # Verify a re_teach event row was persisted for the wrong turn.
        re_teach_rows = session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == sid)
            .where(QuestionAnswer.event_type == "re_teach")
        ).all()
        check("A: one re_teach row persisted",
              len(re_teach_rows) == 1, f"got {len(re_teach_rows)}")
        check("A: re_teach row not counted as open MCQ",
              all(q.widget_type is None for q in re_teach_rows))

        # Cleanup Phase A.
        _cleanup_session(session, sid)
        print("\n[Phase A] passed ✓")

        # --------------------------------------------------------------
        # Phase B — K-cap escalation: K wrong attempts -> capped -> advance
        # --------------------------------------------------------------
        assessment = AssessmentSession(
            session_id=str(uuid.uuid4()),
            user_id=learner_id,
            lesson_id=lesson.id,
            status="in_progress",
        )
        session.add(assessment)
        session.commit()
        session.refresh(assessment)
        sid = assessment.id
        k = WidgetAssessmentService.MAX_FAILED_ATTEMPTS_PER_CONCEPT
        print(f"\n[Phase B] assessment id={sid}  (K={k})")

        service = WidgetAssessmentService(session, judge=None)
        start = service.start_assessment(sid)
        payload: MCQPayload = start["payload"]
        target_concept = payload.concept_tested
        seen_stems = {payload.stem}
        seen_option_sets = {tuple(sorted(_option_texts(payload)))}
        print(f"  target concept='{target_concept}'")

        capped_seen = False
        capped_advance_seen = False
        capped_advance_concept = None
        wrong_turns = 0
        max_turns = k + 3  # safety valve; must terminate well before this

        while wrong_turns < max_turns:
            wrong_id = _pick_wrong_option(payload)
            wrong_turns += 1
            print(f"  [{wrong_turns}] submit WRONG {wrong_id}")
            res = service.process_answer(sid, wrong_id)
            check(f"B: turn {wrong_turns} scored wrong",
                  res["score_result"].is_correct is False)
            next_p = res["next_payload"]

            if wrong_turns < k:
                check(f"B: turn {wrong_turns} not capped",
                      res.get("escalation_capped") is False)
                check(f"B: turn {wrong_turns} remediation present",
                      res.get("remediation") is not None)
                check(f"B: turn {wrong_turns} stays on same concept",
                      next_p is not None
                      and next_p.concept_tested == target_concept)
                # Each regeneration must differ in stem. MCQ regens must also
                # differ in distractor set; at the step-down rung (M5) the
                # regenerated payload is true/false, which is a different
                # question by construction.
                check(f"B: turn {wrong_turns} new stem",
                      next_p.stem not in seen_stems,
                      f"stem reused: {next_p.stem!r}")
                if isinstance(next_p, MCQPayload):
                    check(f"B: turn {wrong_turns} new distractor set",
                          tuple(sorted(_option_texts(next_p))) not in seen_option_sets)
                    seen_option_sets.add(tuple(sorted(_option_texts(next_p))))
                else:
                    check(f"B: turn {wrong_turns} steps down to true/false",
                          isinstance(next_p, TrueFalsePayload))
                seen_stems.add(next_p.stem)
                payload = next_p
            else:
                # K-th wrong (or beyond) — must cap and advance.
                capped_seen = True
                check(f"B: turn {wrong_turns} escalation_capped=True",
                      res.get("escalation_capped") is True,
                      f"got {res.get('escalation_capped')}")
                check(f"B: turn {wrong_turns} capped_concept named",
                      res.get("capped_concept") == target_concept,
                      f"got {res.get('capped_concept')}")
                if next_p is not None:
                    capped_advance_seen = True
                    capped_advance_concept = next_p.concept_tested
                    check(f"B: turn {wrong_turns} advances off capped concept",
                          next_p.concept_tested != target_concept,
                          f"stayed on {target_concept}")
                else:
                    check(f"B: turn {wrong_turns} status reflects completion "
                          "or no further pending concept",
                          res["status"] == "completed")
                break

        check("B: cap was reached and observed", capped_seen,
              "loop exited before cap")
        # No infinite loop: we exited after exactly K wrong attempts (the inner
        # break on the K-th turn) rather than continuing to regenerate forever.
        check("B: terminates at K wrong attempts (no infinite loop)",
              wrong_turns == k, f"turns={wrong_turns} expected={k}")
        if capped_advance_seen:
            print(f"  after cap -> advanced to concept='{capped_advance_concept}'")

        # The capped concept must NOT be marked as covered (it stays
        # not-mastered in OutcomeProgress).
        qas_correct_for_concept = session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == sid)
            .where(QuestionAnswer.concept_tested == target_concept)
            .where(QuestionAnswer.is_correct == True)
        ).first()
        check("B: capped concept has NO correct answer on record",
              qas_correct_for_concept is None)

        _cleanup_session(session, sid)
        print("\n[Phase B] passed ✓")

    print("=" * 60)
    print(f"Passed: {len(_passes)}")
    print(f"Failed: {len(_failures)}")
    if _failures:
        print("\nFailures:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("\nAll M3 remediation smoke checks passed.")
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


def _parse_safe(outcome):
    import json
    if not outcome.key_concepts:
        return []
    try:
        v = json.loads(outcome.key_concepts)
        if isinstance(v, list):
            return v
    except (ValueError, TypeError):
        pass
    return [c.strip() for c in outcome.key_concepts.split(",") if c.strip()]


if __name__ == "__main__":
    sys.exit(main())