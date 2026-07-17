"""
M4 end-to-end smoke test: escalation ladder + needs_review flag.

Drives `WidgetAssessmentService` directly (no HTTP, no templates) against the
real database, against the seeded M2 test lesson (2 outcomes × 3 concepts).
Covers the M4 exit criteria from PLAN_v3.md §12 plus the §9/§11 decisions
confirmed with the user:

  Ladder (step down at 2, cap at 3):
  1. Wrong #1 on a concept → re_teach + regenerated FULL-form MCQ on the same
     concept (remediation.step_down is False).
  2. Wrong #2 → re_teach + regenerated STEPPED-DOWN MCQ (exactly 2 options,
     enforced by the judge) on the same concept (remediation.step_down True).
  3. A correct answer on the stepped-down form covers the concept and advances.
  4. Wrong #3 (at the stepped-down rung) → escalation cap: no regeneration,
     concept flagged needs_review (persisted audit row), learner advances.

  Terminal needs_review behavior ("advance with a persistent flag"):
  5. needs_review is derivable from the DB (load_needs_review_concepts) and
     appears in build_concept_tracking's per-outcome `flagged` list.
  6. The flagged concept stays uncovered (not-mastered) — never silently
     marked learned, and the loop terminates (no infinite regeneration).

  Judge enforcement:
  7. RulesValidator rejects a payload whose option count does not match
     JudgeContext.expected_option_count (the step-down is not advisory).

Requires:
- scripts/migrate_m2_widget_payload.py applied
- scripts/seed_m2_widget_lesson.py run (creates the test lesson)
- OPENROUTER_API_KEY / OPENAI_API_KEY in .env, OR the StubGenerator fallback
  (assertions are provider-independent: option COUNT is judge-enforced, and
  only stems are asserted to differ).

Run: uv run python scripts/test_m4_escalation.py
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
from app.services.widgets.schema import (
    GenerationContext,
    JudgeContext,
    MCQPayload,
    MCQOption,
)
from app.services.widgets.generator import StubGenerator
from app.services.widget_assessment import (
    WidgetAssessmentService,
    build_concept_tracking,
    load_needs_review_concepts,
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


def _pick_wrong_option(payload: MCQPayload) -> str:
    wrong = [o for o in payload.options if not o.is_correct]
    if not wrong:
        raise AssertionError("MCQ payload has no wrong options to pick")
    return wrong[0].id


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


def main():
    print("M4 escalation smoke test")
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
        print(f"Lesson id={lesson.id}, outcomes={len(outcomes)}")
        print(f"Step-down threshold = {WidgetAssessmentService.STEP_DOWN_THRESHOLD}, "
              f"cap K = {WidgetAssessmentService.MAX_FAILED_ATTEMPTS_PER_CONCEPT}")

        learner = session.exec(select(User)).first()
        learner_id = learner.id if learner else 1

        # --------------------------------------------------------------
        # Phase A — ladder: full form -> step-down at threshold -> correct
        # --------------------------------------------------------------
        sid = _new_assessment(session, lesson.id, learner_id)
        print(f"\n[Phase A] assessment id={sid}")

        service = WidgetAssessmentService(session, judge=None)
        start = service.start_assessment(sid)
        p0: MCQPayload = start["payload"]
        concept = p0.concept_tested
        check("A: start emits MCQ", isinstance(p0, MCQPayload))
        print(f"  concept='{concept}'  options={len(p0.options)}")

        # Wrong #1 — full-form regen, no step-down yet.
        r1 = service.process_answer(sid, _pick_wrong_option(p0))
        p1: MCQPayload = r1["next_payload"]
        check("A: wrong #1 scored wrong", r1["score_result"].is_correct is False)
        check("A: wrong #1 remediation present", r1.get("remediation") is not None)
        check("A: wrong #1 step_down False",
              r1.get("remediation", {}).get("step_down") is False,
              f"got {r1.get('remediation', {}).get('step_down')}")
        check("A: wrong #1 not capped", r1.get("escalation_capped") is False)
        check("A: wrong #1 stays on concept",
              p1 is not None and p1.concept_tested == concept)
        check("A: wrong #1 new stem", p1 is not None and p1.stem != p0.stem)
        print(f"  wrong #1 -> regen options={len(p1.options)}")

        # Wrong #2 — step-down rung: exactly 2 options (judge-enforced).
        r2 = service.process_answer(sid, _pick_wrong_option(p1))
        p2: MCQPayload = r2["next_payload"]
        check("A: wrong #2 scored wrong", r2["score_result"].is_correct is False)
        check("A: wrong #2 step_down True",
              r2.get("remediation", {}).get("step_down") is True,
              f"got {r2.get('remediation', {}).get('step_down')}")
        check("A: wrong #2 not capped", r2.get("escalation_capped") is False)
        check("A: wrong #2 stays on concept",
              p2 is not None and p2.concept_tested == concept)
        check("A: stepped-down MCQ has exactly 2 options",
              p2 is not None and len(p2.options) == 2,
              f"got {len(p2.options) if p2 else None}")
        check("A: stepped-down stem differs",
              p2 is not None and p2.stem not in {p0.stem, p1.stem})
        print(f"  wrong #2 -> stepped-down options={len(p2.options)}")

        # Correct on the stepped-down form — concept covered, advance.
        r3 = service.process_answer(sid, p2.correct_option.id)
        check("A: correct on stepped-down scored correct",
              r3["score_result"].is_correct is True)
        check("A: no remediation on correct", r3.get("remediation") is None)
        check("A: advances to a DIFFERENT concept",
              r3["next_payload"] is not None
              and r3["next_payload"].concept_tested != concept,
              f"got {r3['next_payload'].concept_tested if r3['next_payload'] else None}")

        # No needs_review flag for a concept eventually answered correctly.
        check("A: no needs_review rows after eventual correct",
              load_needs_review_concepts(session, session.get(AssessmentSession, sid)) == [])

        # The re_teach audit rows record the step_down decision per turn.
        teach_rows = session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == sid)
            .where(QuestionAnswer.event_type == "re_teach")
            .order_by(QuestionAnswer.asked_at)
        ).all()
        import json as _json
        teach_payloads = [
            _json.loads(r.question_payload) for r in teach_rows if r.question_payload
        ]
        check("A: two re_teach rows persisted", len(teach_payloads) == 2,
              f"got {len(teach_payloads)}")
        check("A: audit rows record step_down False then True",
              [t.get("step_down") for t in teach_payloads] == [False, True],
              f"got {[t.get('step_down') for t in teach_payloads]}")

        _cleanup_session(session, sid)
        print("\n[Phase A] passed ✓")

        # --------------------------------------------------------------
        # Phase B — cap: 3 wrong -> needs_review flag -> advance, terminates
        # --------------------------------------------------------------
        sid = _new_assessment(session, lesson.id, learner_id)
        k = WidgetAssessmentService.MAX_FAILED_ATTEMPTS_PER_CONCEPT
        print(f"\n[Phase B] assessment id={sid}  (K={k})")

        service = WidgetAssessmentService(session, judge=None)
        start = service.start_assessment(sid)
        payload: MCQPayload = start["payload"]
        target_concept = payload.concept_tested
        seen_stems = {payload.stem}
        print(f"  target concept='{target_concept}'")

        capped_seen = False
        wrong_turns = 0
        max_turns = k + 3  # safety valve

        while wrong_turns < max_turns:
            wrong_turns += 1
            res = service.process_answer(sid, _pick_wrong_option(payload))
            check(f"B: turn {wrong_turns} scored wrong",
                  res["score_result"].is_correct is False)
            next_p: MCQPayload = res["next_payload"]

            if wrong_turns < k:
                check(f"B: turn {wrong_turns} not capped",
                      res.get("escalation_capped") is False)
                check(f"B: turn {wrong_turns} stays on concept",
                      next_p is not None
                      and next_p.concept_tested == target_concept)
                check(f"B: turn {wrong_turns} new stem",
                      next_p.stem not in seen_stems,
                      f"stem reused: {next_p.stem!r}")
                # Ladder shape: the FINAL rung before the cap is the
                # stepped-down 2-option form.
                if wrong_turns >= WidgetAssessmentService.STEP_DOWN_THRESHOLD:
                    check(f"B: turn {wrong_turns} stepped down to 2 options",
                          len(next_p.options) == 2,
                          f"got {len(next_p.options)}")
                seen_stems.add(next_p.stem)
                payload = next_p
            else:
                capped_seen = True
                check(f"B: turn {wrong_turns} escalation_capped=True",
                      res.get("escalation_capped") is True,
                      f"got {res.get('escalation_capped')}")
                check(f"B: turn {wrong_turns} capped_concept named",
                      res.get("capped_concept") == target_concept,
                      f"got {res.get('capped_concept')}")
                check(f"B: turn {wrong_turns} no remediation at cap",
                      res.get("remediation") is None)
                if next_p is not None:
                    check(f"B: turn {wrong_turns} advances off capped concept",
                          next_p.concept_tested != target_concept,
                          f"stayed on {target_concept}")
                else:
                    check(f"B: turn {wrong_turns} completes when nothing pending",
                          res["status"] == "completed")
                break

        check("B: cap observed", capped_seen, "loop exited before cap")
        check("B: terminates at exactly K wrong attempts",
              wrong_turns == k, f"turns={wrong_turns} expected={k}")

        # Terminal flag: persisted, derivable, and reflected in tracking.
        assessment = session.get(AssessmentSession, sid)
        flagged = load_needs_review_concepts(session, assessment)
        check("B: needs_review derivable from DB",
              flagged == [target_concept], f"got {flagged}")

        review_rows = session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == sid)
            .where(QuestionAnswer.event_type == "needs_review")
        ).all()
        check("B: exactly one needs_review audit row",
              len(review_rows) == 1, f"got {len(review_rows)}")
        check("B: needs_review row invisible to MCQ loaders",
              all(r.widget_type is None and r.answer is None for r in review_rows))

        tracking = build_concept_tracking(session, assessment, list(outcomes))
        outcome_of_concept = next(
            o for o in outcomes if target_concept in _parse_safe(o)
        )
        check("B: concept in sidebar flagged list",
              target_concept in tracking[outcome_of_concept.id]["flagged"],
              f"got {tracking[outcome_of_concept.id]['flagged']}")
        check("B: concept NOT in covered list",
              target_concept not in tracking[outcome_of_concept.id]["covered"])

        progress = session.exec(
            select(OutcomeProgress)
            .where(OutcomeProgress.session_id == sid)
            .where(OutcomeProgress.learning_outcome_id == outcome_of_concept.id)
        ).first()
        check("B: outcome not mastered with flagged concept",
              progress is not None and progress.is_mastered is False,
              f"mastery={progress.mastery_level if progress else None}")

        _cleanup_session(session, sid)
        print("\n[Phase B] passed ✓")

        # --------------------------------------------------------------
        # Phase C — judge enforcement + stub directive (provider-independent)
        # --------------------------------------------------------------
        print("\n[Phase C] rules enforcement of expected_option_count")
        rules = RulesValidator()
        base_ctx = JudgeContext(
            outcome_key="T1", valid_concepts=["soil"], expected_option_count=2
        )
        two_opt = MCQPayload(
            concept_tested="soil",
            stem="Which of these best describes healthy soil?",
            options=[
                MCQOption(id="a", text="Dark, crumbly, rich in organic matter", is_correct=True),
                MCQOption(id="b", text="Bright blue and smells of ammonia", is_correct=False),
            ],
        )
        three_opt = MCQPayload(
            concept_tested="soil",
            stem="Which of these best describes healthy soil?",
            options=[
                MCQOption(id="a", text="Dark, crumbly, rich in organic matter", is_correct=True),
                MCQOption(id="b", text="Bright blue and smells of ammonia", is_correct=False),
                MCQOption(id="c", text="Glows in the dark", is_correct=False),
            ],
        )
        check("C: 2-option payload passes when 2 expected",
              rules.validate(two_opt, base_ctx).valid,
              f"{rules.validate(two_opt, base_ctx).issues}")
        v = rules.validate(three_opt, base_ctx)
        check("C: 3-option payload rejected when 2 expected",
              not v.valid and any("exactly 2" in i for i in v.issues),
              f"{v.issues}")
        open_ctx = JudgeContext(outcome_key="T1", valid_concepts=["soil"])
        check("C: 3-option payload passes when no expectation set",
              rules.validate(three_opt, open_ctx).valid)

        stub = StubGenerator()
        stepped = stub(GenerationContext(
            topic="t", outcome_description="d", outcome_key="T1",
            key_concepts=["soil"], targeted_concept="soil",
            target_option_count=2,
        ))
        check("C: StubGenerator honors target_option_count=2",
              len(stepped.options) == 2 and stepped.difficulty == "easy")
        full = stub(GenerationContext(
            topic="t", outcome_description="d", outcome_key="T1",
            key_concepts=["soil"], targeted_concept="soil",
        ))
        check("C: StubGenerator default stays full-form",
              len(full.options) >= 3)

    print("=" * 60)
    print(f"Passed: {len(_passes)}")
    print(f"Failed: {len(_failures)}")
    if _failures:
        print("\nFailures:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("\nAll M4 escalation smoke checks passed.")
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
