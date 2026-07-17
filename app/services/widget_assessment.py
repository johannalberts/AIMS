"""
Widget-based assessment service — M2 + M3 remediation.

Per-lesson path for lessons with `use_widget_assessment = True`. Replaces the
v2 chat loop (AIMSGraph) with the M1 structured-payload pipeline:

    choose_outcome -> choose_concept -> generate QuestionPayload
        -> judge_or_regenerate -> persist QuestionAnswer(question_payload)
    on submit:
        score_answer -> persist QuestionAnswer(response_payload, score)
        -> (M3) route: wrong-uncapped → re_teach + regenerate on SAME concept
                  wrong-capped    → flag and advance
                  correct         → advance to next concept / outcome

State is reconstructed from the database on every turn; there is no in-memory
state to thread across requests and no LangGraph checkpointer involved.
Concept-level progress is derived from answered QuestionAnswer rows for the
session, so it stays correct across server restarts.

M2 completes a single full pass over all concepts per outcome. M3 restores the
remediation loop: a wrong answer (single MCQ → 0 % → re_teach band per
PLAN_v3.md §9) triggers a teach panel and a regenerated MCQ on the *same*
concept (driven by the M1 `questions_asked` dedup, now actually invoked). After
`MAX_FAILED_ATTEMPTS_PER_CONCEPT` wrong answers on the same concept, the
escalation cap fires: we stop regenerating, leave the concept uncovered (so
OutcomeProgress reflects not-mastered), and advance. The terminal "needs
review" UX is deferred to M4 (§11) — for M3 we simply advance.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from app.models import (
    AssessmentSession,
    LearningOutcome,
    OutcomeProgress,
    QuestionAnswer,
)
from app.services.widgets.schema import (
    GenerationContext,
    JudgeContext,
    MCQPayload,
    MCQResponse,
    MCQOption,
    QuestionPayload,
    ScoreResult,
    WidgetType,
)
from app.services.widgets.judge import Judge, judge_or_regenerate
from app.services.widgets.scorer import score_answer, ScoringError
from app.services.widgets.generator import (
    GeneratorError,
    StubGenerator,
    make_generator,
)
from app.services.widgets.llm import llm_available

logger = logging.getLogger(__name__)


class WidgetAssessmentError(RuntimeError):
    """Raised when a widget assessment turn cannot be completed."""


def _parse_key_concepts(outcome: LearningOutcome) -> List[str]:
    raw = outcome.key_concepts
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(c) for c in raw]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(c) for c in parsed]
    except (ValueError, TypeError):
        pass
    return [c.strip() for c in str(raw).split(",") if c.strip()]


def _payload_to_dict(payload: QuestionPayload) -> Dict[str, Any]:
    """Serialize a QuestionPayload to a JSON-safe dict for persistence."""
    return payload.model_dump(mode="json")


def _payload_from_dict(data: Dict[str, Any]) -> QuestionPayload:
    """Reconstruct a QuestionPayload subclass from a persisted dict."""
    wt = data.get("widget_type")
    if wt == WidgetType.MCQ_SINGLE.value or wt == WidgetType.MCQ_SINGLE:
        return MCQPayload.model_validate(data)
    raise WidgetAssessmentError(f"Unknown widget_type in persisted payload: {wt!r}")


class WidgetAssessmentService:
    """Stateless-per-request service for the M2 MCQ widget loop.

    Caller is responsible for owning the SQLModel `Session` (passed in via the
    FastAPI dependency) and for committing the transaction. The service logs
    on errors but does not swallow exceptions — the route layer surfaces them
    as HTTP 500s (or 4xx for client-side bugs like unknown option ids).
    """

    MAX_GENERATE_ATTEMPTS = 3

    # M3 (PLAN_v3.md §9 "Escalation"): after this many wrong answers on the
    # same concept, stop regenerating and advance with the concept flagged as
    # not-mastered. Surfaced as a named constant so it is easy to tune; the
    # terminal "needs review" UX is an open question (§11) and is deferred to
    # M4 — for M3 we simply advance and let OutcomeProgress reflect the gap.
    MAX_FAILED_ATTEMPTS_PER_CONCEPT = 3

    def __init__(self, db_session: Session, judge: Optional[Judge] = None):
        self.db_session = db_session
        self.judge = judge or Judge()

    # ------------------------------------------------------------------
    # Public turn API
    # ------------------------------------------------------------------

    def start_assessment(self, assessment_id: int) -> Dict[str, Any]:
        """Initialize a widget-based assessment and emit the first question."""
        assessment = self._load_assessment(assessment_id)
        outcomes = self._load_outcomes(assessment)
        self._ensure_progress_rows(assessment, outcomes)

        next_target = self._next_target(assessment, outcomes)
        if next_target is None:
            assessment.status = "completed"
            assessment.completed_at = datetime.utcnow()
            self.db_session.add(assessment)
            self.db_session.commit()
            return {"status": "completed", "payload": None, "outcome": None}

        payload = self._generate(assessment, outcomes, next_target)
        self._persist_question(assessment, outcomes, next_target, payload)
        assessment.current_outcome_key = next_target.outcome.key
        self.db_session.add(assessment)
        self.db_session.commit()
        return self._emit(assessment, outcomes, next_target, payload)

    def process_answer(
        self, assessment_id: int, selected_option_id: str
    ) -> Dict[str, Any]:
        """Score the learner's option, route, and return the next payload.

        M3 routing (PLAN_v3.md §3 / §9):
        - Correct → advance to the next pending concept/outcome (M2 behavior).
        - Wrong and below the escalation cap → render a teach panel, then
          regenerate a fresh MCQ on the *same* concept (different stem /
          distractors, driven by `questions_asked` dedup plumbing from M1).
        - Wrong and at/above the cap → stop regenerating, flag the concept as
          not-mastered (it stays uncovered in OutcomeProgress), and advance to
          the next pending concept/outcome. No infinite loop.
        """
        assessment = self._load_assessment(assessment_id)
        outcomes = self._load_outcomes(assessment)

        open_qa = self._load_open_question(assessment)
        if open_qa is None or open_qa.question_payload is None:
            raise WidgetAssessmentError(
                "No open question awaiting an answer for this session."
            )

        payload = _payload_from_dict(json.loads(open_qa.question_payload))
        response = MCQResponse(selected_option_id=selected_option_id)

        try:
            result = score_answer(payload, response)
        except ScoringError as e:
            raise WidgetAssessmentError(str(e)) from e

        self._record_answer(open_qa, response, result)

        answered_outcome = next(
            (o for o in outcomes if o.id == open_qa.learning_outcome_id), None
        )

        remediation: Optional[Dict[str, Any]] = None
        escalation_capped = False
        capped_concept: Optional[str] = None

        concept = open_qa.concept_tested or payload.concept_tested
        wrong_count = self._wrong_count_for_concept(
            assessment, open_qa.learning_outcome_id, concept
        )

        if result.is_correct:
            # M2 path: advance to the next pending concept/outcome.
            next_target = self._next_target(assessment, outcomes)
        else:
            # Wrong answer — single MCQ is binary, so this is the re_teach
            # band (< 20 % per PLAN_v3.md §9). rephrase (20–80 %) only becomes
            # relevant once partial-credit widget types land (M5+).
            if wrong_count < self.MAX_FAILED_ATTEMPTS_PER_CONCEPT:
                remediation = self._build_remediation(
                    answered_outcome, concept, payload
                )
                self._persist_re_teach(
                    assessment, open_qa.learning_outcome_id, concept, remediation
                )
                # Stay on the same concept — narrow target so the generator's
                # questions_asked dedup produces a genuinely different MCQ.
                if answered_outcome is None:
                    raise WidgetAssessmentError(
                        "Answered question's outcome could not be resolved; "
                        "cannot remediate."
                    )
                next_target = _Target(outcome=answered_outcome, concept=concept)
            else:
                # Escalation cap reached: stop regenerating, flag and advance.
                escalation_capped = True
                capped_concept = concept
                logger.info(
                    f"Escalation cap reached for concept '{concept}' "
                    f"(wrong_attempts={wrong_count}); advancing with concept "
                    f"flagged as not-mastered."
                )
                next_target = self._next_target(assessment, outcomes)

        next_payload: Optional[QuestionPayload] = None
        next_outcome: Optional[LearningOutcome] = None
        if next_target is None:
            assessment.status = "completed"
            assessment.completed_at = datetime.utcnow()
        else:
            next_payload = self._generate(assessment, outcomes, next_target)
            self._persist_question(assessment, outcomes, next_target, next_payload)
            next_outcome = next_target.outcome
            assessment.current_outcome_key = next_target.outcome.key

        self._sync_progress(assessment, outcomes)
        self.db_session.add(assessment)
        self.db_session.commit()

        return {
            "score_result": result,
            "answered_payload": payload,
            "answered_outcome": answered_outcome,
            "selected_option_id": selected_option_id,
            "next_payload": next_payload,
            "next_outcome": next_outcome,
            "status": assessment.status,
            "remediation": remediation,
            "escalation_capped": escalation_capped,
            "capped_concept": capped_concept,
        }

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _load_assessment(self, assessment_id: int) -> AssessmentSession:
        assessment = self.db_session.get(AssessmentSession, assessment_id)
        if not assessment:
            raise WidgetAssessmentError("Assessment session not found")
        lesson = assessment.lesson
        if lesson is None or not getattr(lesson, "use_widget_assessment", False):
            raise WidgetAssessmentError(
                "Lesson is not configured for widget assessment."
            )
        return assessment

    def _load_outcomes(self, assessment: AssessmentSession) -> List[LearningOutcome]:
        outcomes = self.db_session.exec(
            select(LearningOutcome)
            .where(LearningOutcome.lesson_id == assessment.lesson_id)
            .where(LearningOutcome.is_active == True)
            .order_by(LearningOutcome.order)
        ).all()
        if not outcomes:
            raise WidgetAssessmentError("No learning outcomes for this lesson")
        return list(outcomes)

    def _ensure_progress_rows(
        self, assessment: AssessmentSession, outcomes: List[LearningOutcome]
    ) -> None:
        existing = self.db_session.exec(
            select(OutcomeProgress).where(
                OutcomeProgress.session_id == assessment.id
            )
        ).all()
        have = {p.learning_outcome_id for p in existing}
        for outcome in outcomes:
            if outcome.id in have:
                continue
            self.db_session.add(
                OutcomeProgress(
                    session_id=assessment.id,
                    learning_outcome_id=outcome.id,
                    mastery_level=0.0,
                    is_mastered=False,
                    attempts=0,
                )
            )
        self.db_session.commit()

    def _load_open_question(
        self, assessment: AssessmentSession
    ) -> Optional[QuestionAnswer]:
        return self.db_session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == assessment.id)
            .where(QuestionAnswer.answer == None)
            .where(QuestionAnswer.widget_type == WidgetType.MCQ_SINGLE.value)
            .order_by(QuestionAnswer.asked_at.desc())
        ).first()

    def _persist_question(
        self,
        assessment: AssessmentSession,
        outcomes: List[LearningOutcome],
        target: "_Target",
        payload: QuestionPayload,
    ) -> QuestionAnswer:
        qa = QuestionAnswer(
            session_id=assessment.id,
            learning_outcome_id=target.outcome.id,
            question=payload.stem,
            event_type="question",
            widget_type=payload.widget_type.value,
            concept_tested=target.concept,
            question_payload=json.dumps(_payload_to_dict(payload)),
        )
        self.db_session.add(qa)
        self.db_session.commit()
        self.db_session.refresh(qa)
        return qa

    def _record_answer(
        self, qa: QuestionAnswer, response: MCQResponse, result: ScoreResult
    ) -> None:
        qa.answer = response.selected_option_id
        qa.response_payload = json.dumps(response.model_dump(mode="json"))
        qa.score = result.score
        qa.is_correct = result.is_correct
        qa.feedback = result.explanation
        qa.answered_at = datetime.utcnow()
        self.db_session.add(qa)
        self.db_session.commit()

    def _sync_progress(
        self, assessment: AssessmentSession, outcomes: List[LearningOutcome]
    ) -> None:
        """Recompute OutcomeProgress from answered QuestionAnswer rows."""
        progress_rows = self.db_session.exec(
            select(OutcomeProgress).where(
                OutcomeProgress.session_id == assessment.id
            )
        ).all()
        progress_by_outcome = {p.learning_outcome_id: p for p in progress_rows}

        qas = self.db_session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == assessment.id)
            .where(QuestionAnswer.answer != None)
            .where(QuestionAnswer.widget_type == WidgetType.MCQ_SINGLE.value)
        ).all()

        for outcome in outcomes:
            progress = progress_by_outcome.get(outcome.id)
            if progress is None:
                progress = OutcomeProgress(
                    session_id=assessment.id,
                    learning_outcome_id=outcome.id,
                    mastery_level=0.0,
                    is_mastered=False,
                    attempts=0,
                )
                self.db_session.add(progress)
                progress_by_outcome[outcome.id] = progress

            concepts = _parse_key_concepts(outcome)
            attempted: set[str] = set()
            covered: set[str] = set()
            for qa in qas:
                if qa.learning_outcome_id != outcome.id:
                    continue
                if qa.concept_tested:
                    attempted.add(qa.concept_tested)
                    if qa.is_correct:
                        covered.add(qa.concept_tested)
            # attempts on the outcome = number of answered QAs for it
            outcome_qas = [q for q in qas if q.learning_outcome_id == outcome.id]
            progress.attempts = len(outcome_qas)
            if concepts:
                progress.mastery_level = len(covered) / len(concepts)
            else:
                progress.mastery_level = 1.0 if outcome_qas else 0.0
            threshold = (assessment.lesson.mastery_threshold or 0.8)
            progress.is_mastered = progress.mastery_level >= threshold
            if progress.is_mastered and not progress.mastered_at:
                progress.mastered_at = datetime.utcnow()
            self.db_session.add(progress)

    # ------------------------------------------------------------------
    # Concept routing
    # ------------------------------------------------------------------

    def _next_target(
        self, assessment: AssessmentSession, outcomes: List[LearningOutcome]
    ) -> Optional["_Target"]:
        """Find the next (outcome, concept) to MCQ about, or None if done.

        M3 routing (PLAN_v3.md §3 / §9): a concept is "pending" if it is not
        yet covered AND its wrong-answer count is below the escalation cap.
        Wrong-but-uncapped concepts are prioritised ahead of unattempted ones
        so a wrong answer is re-asked on the *same* concept before the loop
        moves on. A concept at/above the cap is no longer pending → skipped,
        which advances the learner with the concept flagged as not-mastered.
        """
        qas = self.db_session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == assessment.id)
            .where(QuestionAnswer.widget_type == WidgetType.MCQ_SINGLE.value)
        ).all()

        # Per-outcome: attempted set, covered (correct) set, wrong counts.
        per_outcome: Dict[int, Dict[str, Any]] = {}
        for qa in qas:
            bucket = per_outcome.setdefault(
                qa.learning_outcome_id,
                {"attempted": set(), "covered": set(), "wrong": {}},
            )
            if qa.answer is None or not qa.concept_tested:
                continue
            bucket["attempted"].add(qa.concept_tested)
            if qa.is_correct:
                bucket["covered"].add(qa.concept_tested)
            else:
                bucket["wrong"][qa.concept_tested] = (
                    bucket["wrong"].get(qa.concept_tested, 0) + 1
                )

        cap = self.MAX_FAILED_ATTEMPTS_PER_CONCEPT
        for outcome in outcomes:
            concepts = _parse_key_concepts(outcome)
            if not concepts:
                continue
            state = per_outcome.get(
                outcome.id, {"attempted": set(), "covered": set(), "wrong": {}}
            )
            covered = state["covered"]
            wrong = state["wrong"]
            attempted = state["attempted"]
            # Wrong-but-uncapped concepts first — these are the in-progress
            # re-asks. Preserve the outcome's declared concept order.
            wrong_uncapped = [
                c for c in concepts
                if c in wrong and c not in covered and wrong[c] < cap
            ]
            if wrong_uncapped:
                return _Target(outcome=outcome, concept=wrong_uncapped[0])
            unattempted = [c for c in concepts if c not in attempted]
            if unattempted:
                return _Target(outcome=outcome, concept=unattempted[0])
        # All outcomes have all concepts covered or capped: assessment is done.
        return None

    def _wrong_count_for_concept(
        self,
        assessment: AssessmentSession,
        outcome_id: int,
        concept: Optional[str],
    ) -> int:
        """Count wrong MCQ answers for a (outcome, concept) so far this session.

        Includes the answer just recorded (caller invokes this after
        `_record_answer`), so the returned count is the total wrong attempts
        on this concept up to and including the current turn.
        """
        if not concept:
            return 0
        rows = self.db_session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == assessment.id)
            .where(QuestionAnswer.learning_outcome_id == outcome_id)
            .where(QuestionAnswer.concept_tested == concept)
            .where(QuestionAnswer.widget_type == WidgetType.MCQ_SINGLE.value)
            .where(QuestionAnswer.answer != None)
            .where(QuestionAnswer.is_correct == False)
        ).all()
        return len(list(rows))

    def _build_remediation(
        self,
        outcome: Optional[LearningOutcome],
        concept: str,
        scored_payload: QuestionPayload,
    ) -> Dict[str, Any]:
        """Build the teach-panel payload for a wrong answer.

        M3 fallback (PLAN_v3.md §8 / §9): the teach panel is grounded in the
        scored payload's explanation field (already on MCQPayload) plus a
        templated hint. RAG retrieval into LearningContent is M6 — not built
        here.
        """
        explanation = getattr(scored_payload, "explanation", None) or ""
        outcome_desc = outcome.description if outcome else ""
        return {
            "concept": concept,
            "outcome_key": outcome.key if outcome else "",
            "outcome_description": outcome_desc,
            "explanation": explanation,
            "hint": (
                f"Take another look at '{concept}' — focus on why the correct "
                f"option is the one that demonstrably tests this concept, "
                f"then try a fresh question from a different angle."
            ),
        }

    def _persist_re_teach(
        self,
        assessment: AssessmentSession,
        outcome_id: int,
        concept: str,
        remediation: Dict[str, Any],
    ) -> QuestionAnswer:
        """Persist a non-interactive `re_teach` event row for the audit trail.

        Stored with `event_type="re_teach"`, `widget_type=None`, `answer=None`
        so it is never mistaken for an open MCQ by `_load_open_question` /
        `_next_target` (both filter on `widget_type == mcq_single` or
        `answer != None`). The rendered teach-panel content is serialized into
        `question_payload` so the page can be reconstructed on reload.
        """
        qa = QuestionAnswer(
            session_id=assessment.id,
            learning_outcome_id=outcome_id,
            question=f"Re-teach: {concept}",
            event_type="re_teach",
            widget_type=None,
            concept_tested=concept,
            question_payload=json.dumps(remediation),
        )
        self.db_session.add(qa)
        self.db_session.commit()
        self.db_session.refresh(qa)
        return qa

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate(
        self,
        assessment: AssessmentSession,
        outcomes: List[LearningOutcome],
        target: "_Target",
    ) -> QuestionPayload:
        # Build the GenerationContext with the questions already asked for
        # this concept (so the generator avoids reuse).
        asked_refs = self._asked_refs_for(assessment, target.outcome, target.concept)

        # Reuse OutcomeProgress' attempts count for the failed_attempts hint;
        # it's a coarse signal but enough for M2.
        progress = self.db_session.exec(
            select(OutcomeProgress).where(
                OutcomeProgress.session_id == assessment.id
            ).where(OutcomeProgress.learning_outcome_id == target.outcome.id)
        ).first()
        failed = progress.attempts if progress else 0

        ctx = GenerationContext(
            topic=assessment.lesson.topic,
            outcome_description=target.outcome.description,
            outcome_key=target.outcome.key,
            key_concepts=_parse_key_concepts(target.outcome),
            targeted_concept=target.concept,
            concepts_covered=[],
            questions_asked=asked_refs,
            failed_attempts=failed,
            widget_history=[],
        )

        gen_fn = make_generator(ctx)
        judge_ctx = JudgeContext(
            outcome_key=target.outcome.key,
            valid_concepts=_parse_key_concepts(target.outcome),
            questions_asked=asked_refs,
        )
        try:
            payload, verdict, _attempts = judge_or_regenerate(
                gen_fn, judge_ctx, self.judge, max_attempts=self.MAX_GENERATE_ATTEMPTS
            )
        except ValueError as e:
            raise WidgetAssessmentError(
                f"Could not generate a valid MCQ for concept '{target.concept}': {e}"
            ) from e
        except GeneratorError as e:
            # No LLM key and no stub fallback? Surface a clear error.
            raise WidgetAssessmentError(str(e)) from e

        if not verdict.valid:
            logger.warning(
                "judge_or_regenerate fell back to an imperfect payload for "
                f"concept '{target.concept}': {verdict.issues}"
            )
        return payload

    def _asked_refs_for(
        self,
        assessment: AssessmentSession,
        outcome: LearningOutcome,
        concept: str,
    ) -> List:
        from app.services.widgets.schema import AskedQuestionRef

        rows = self.db_session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == assessment.id)
            .where(QuestionAnswer.learning_outcome_id == outcome.id)
            .where(QuestionAnswer.concept_tested == concept)
            .where(QuestionAnswer.widget_type == WidgetType.MCQ_SINGLE.value)
            .order_by(QuestionAnswer.asked_at)
        ).all()
        refs: List[AskedQuestionRef] = []
        for qa in rows:
            if not qa.question_payload:
                continue
            try:
                payload = _payload_from_dict(json.loads(qa.question_payload))
            except Exception:
                continue
            refs.append(
                AskedQuestionRef(
                    widget_type=payload.widget_type,
                    stem=payload.stem,
                    option_texts=getattr(payload, "option_texts", []),
                )
            )
        return refs

    # ------------------------------------------------------------------
    # Result shaping (returned to route layer)
    # ------------------------------------------------------------------

    def _emit(
        self,
        assessment: AssessmentSession,
        outcomes: List[LearningOutcome],
        target: "_Target",
        payload: QuestionPayload,
    ) -> Dict[str, Any]:
        self._sync_progress(assessment, outcomes)
        self.db_session.add(assessment)
        self.db_session.commit()
        return {
            "status": assessment.status,
            "payload": payload,
            "outcome": target.outcome,
            "concept_tested": target.concept,
        }


class _Target:
    __slots__ = ("outcome", "concept")

    def __init__(self, outcome: LearningOutcome, concept: str):
        self.outcome = outcome
        self.concept = concept


def _answered_qas(db_session: Session, assessment: AssessmentSession) -> List[QuestionAnswer]:
    return db_session.exec(
        select(QuestionAnswer)
        .where(QuestionAnswer.session_id == assessment.id)
        .where(QuestionAnswer.answer != None)
        .where(QuestionAnswer.widget_type == WidgetType.MCQ_SINGLE.value)
        .order_by(QuestionAnswer.asked_at)
    ).all()


def build_concept_tracking(
    db_session: Session, assessment: AssessmentSession, outcomes: List[LearningOutcome]
) -> Dict[int, Dict[str, List[str]]]:
    """Sidebar helper: build the same dict shape main.py already passes to the
    sidebar template — per outcome {all, covered, remaining} key concepts."""
    qas = _answered_qas(db_session, assessment)
    covered_by_outcome: Dict[int, set[str]] = {}
    for qa in qas:
        if not qa.concept_tested:
            continue
        covered_by_outcome.setdefault(qa.learning_outcome_id, set())
        if qa.is_correct:
            covered_by_outcome[qa.learning_outcome_id].add(qa.concept_tested)

    tracking: Dict[int, Dict[str, List[str]]] = {}
    for outcome in outcomes:
        all_concepts = _parse_key_concepts(outcome)
        covered = covered_by_outcome.get(outcome.id, set())
        remaining = [c for c in all_concepts if c not in covered]
        tracking[outcome.id] = {
            "all": all_concepts,
            "covered": sorted(covered),
            "remaining": remaining,
        }
    return tracking