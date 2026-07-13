"""
M2 end-to-end smoke test for the widget assessment service.

Drives WidgetAssessmentService directly (no HTTP, no templates) against the
real database. Boots a fresh session for the seeded M2 test lesson, plays the
full loop with correct answers, and asserts:
- a session status transitions to "completed" once every concept is attempted
- each QuestionAnswer row carries a structured question_payload + response_payload
- concept coverage on OutcomeProgress reflects correct answers
- re-invocation stability: process_answer raises cleanly when no open question

Requires:
- scripts/migrate_m2_widget_payload.py has been applied
- scripts/seed_m2_widget_lesson.py has been run (creates the test lesson)
- OPENROUTER_API_KEY / OPENAI_API_KEY set in .env, OR the StubGenerator
  fallback path is exercised (this script uses whichever make_generator picks)

Run: uv run python scripts/test_m2_widget_assessment.py
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
)
from app.services.widgets.llm import llm_available, provider_name
from app.services.widgets.schema import MCQPayload, WidgetType
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


def main():
    print("M2 widget assessment smoke test")
    print("=" * 60)
    load_dotenv()
    print(f"LLM provider: {provider_name() or 'stub (no key)'}")

    with Session(engine) as session:
        from app.models import Lesson
        lesson = session.exec(
            select(Lesson).where(Lesson.title == LESSON_TITLE)
        ).first()
        if not lesson:
            print("Test lesson not found. Run scripts/seed_m2_widget_lesson.py first.")
            return 1
        if not lesson.use_widget_assessment:
            print("Lesson exists but use_widget_assessment is False.")
            return 1

        outcomes = session.exec(
            select(LearningOutcome)
            .where(LearningOutcome.lesson_id == lesson.id)
            .where(LearningOutcome.is_active == True)
            .order_by(LearningOutcome.order)
        ).all()
        total_concepts = sum(len(_parse_safe(o)) for o in outcomes)
        print(f"Lesson id={lesson.id}, outcomes={len(outcomes)}, concepts={total_concepts}")

        # Create a fresh assessment session for this run.
        learner_id = 1  # admin@aims.com by convention; fine for the smoke test.
        from app.models import User
        learner = session.exec(select(User).where(User.role.name == "ADMIN")).first()
        if learner is None:
            learner = session.exec(select(User)).first()
        if learner is not None:
            learner_id = learner.id

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
        print(f"Created assessment id={sid}")

        service = WidgetAssessmentService(session, judge=None)

        print("\n[1] start_assessment emits first MCQ")
        start = service.start_assessment(sid)
        check("start returned a payload", start.get("payload") is not None)
        check("start status in_progress", start.get("status") == "in_progress",
              f"status={start.get('status')}")
        first_payload: MCQPayload = start["payload"]
        check("start payload is MCQ", isinstance(first_payload, MCQPayload))
        check("start payload has one correct option",
              sum(1 for o in first_payload.options if o.is_correct) == 1)
        print(f"  stem: {first_payload.stem}")

        # Walk the full loop. On each turn, pick the correct option id and submit.
        turns = 0
        max_turns = total_concepts + 5  # safety valve
        current_payload = first_payload
        current_status = start["status"]
        while current_status == "in_progress" and turns < max_turns:
            turns += 1
            correct_id = next(o.id for o in current_payload.options if o.is_correct)
            print(f"\n[{turns+1}] submit correct option {correct_id} "
                  f"for concept '{current_payload.concept_tested}'")
            result = service.process_answer(sid, correct_id)
            check(f"turn {turns} scored correct",
                  result["score_result"].is_correct, f"got {result['score_result'].is_correct}")
            result_payload = result["next_payload"]
            current_status = result["status"]
            current_payload = result_payload
            if result_payload is not None:
                check(f"turn {turns} next payload is MCQ",
                      isinstance(result_payload, MCQPayload))
                print(f"  next stem: {result_payload.stem}")
            else:
                print("  no next payload (assessment complete?)")

        print(f"\n[final] status={current_status}, turns={turns}")
        check("status is completed", current_status == "completed",
              f"status={current_status}")
        check("turns == total concepts", turns == total_concepts,
              f"turns={turns} expected={total_concepts}")

        print("\n[persist] verify QuestionAnswer rows carry structured data")
        qas = session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == sid)
        ).all()
        check("one QA per concept", len(qas) == total_concepts,
              f"got {len(qas)} expected {total_concepts}")
        check("all QAs are mcq_single",
              all(q.widget_type == WidgetType.MCQ_SINGLE.value for q in qas))
        check("all QAs have question_payload",
              all(q.question_payload is not None for q in qas))
        check("all QAs have response_payload",
              all(q.response_payload is not None for q in qas))
        check("all QAs answered",
              all(q.answer is not None for q in qas))
        check("all QAs correct",
              all(q.is_correct for q in qas))

        print("\n[progress] verify OutcomeProgress")
        progress_rows = session.exec(
            select(OutcomeProgress).where(OutcomeProgress.session_id == sid)
        ).all()
        check("progress rows per outcome",
              len(progress_rows) == len(outcomes),
              f"got {len(progress_rows)}")
        check("all outcomes mastered (all correct)",
              all(p.is_mastered for p in progress_rows))
        for p in progress_rows:
            o = next(o for o in outcomes if o.id == p.learning_outcome_id)
            print(f"  outcome_id={p.learning_outcome_id}: "
                  f"mastery={p.mastery_level:.2f} mastered={p.is_mastered} "
                  f"attempts={p.attempts}")

        print("\n[idempotent] no open question -> next submit raises")
        try:
            service.process_answer(sid, "a")
            check("raises when no open question",
                  False, "no error raised")
        except WidgetAssessmentError as e:
            check("raises when no open question", "open question" in str(e).lower()
                  or "no open" in str(e).lower(), str(e))

        # Cleanup: remove the test session so reruns are clean.
        for q in qas:
            session.delete(q)
        for p in progress_rows:
            session.delete(p)
        session.delete(assessment)
        session.commit()

    print("=" * 60)
    print(f"Passed: {len(_passes)}")
    print(f"Failed: {len(_failures)}")
    if _failures:
        print("\nFailures:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("\nAll M2 widget assessment smoke checks passed.")
    return 0


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