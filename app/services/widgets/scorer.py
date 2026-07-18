"""
Deterministic scorer for AIMS v3 interactive widgets.

Objective widget types are scored by exact match against the payload's known
correct answer — no LLM call. The result maps to the concept(s) targeted by
the question so the assessment layer can update LessonState.concepts_covered
and recompute outcome mastery as covered/total (same coverage model as v2,
see PLAN_v3.md §6).

Free-text / coding scoring (LLM-based) lands in a later milestone and will
live in a separate module; this one stays deterministic-only.
"""
from __future__ import annotations


from app.services.widgets.schema import (
    MCQPayload,
    MCQResponse,
    QuestionPayload,
    LearnerResponse,
    ScoreResult,
    TrueFalsePayload,
    TrueFalseResponse,
    WidgetType,
)


class ScoringError(ValueError):
    """Raised when a response cannot be scored against its payload.

    Typically means the response's widget_type doesn't match the payload's,
    or the selected option id doesn't exist on the payload (a client bug).
    """


def score_answer(payload: QuestionPayload, response: LearnerResponse) -> ScoreResult:
    """Dispatch scoring by widget_type. Deterministic for all current types."""
    if payload.widget_type != response.widget_type:
        raise ScoringError(
            f"widget_type mismatch: payload={payload.widget_type} "
            f"response={response.widget_type}"
        )
    if payload.widget_type == WidgetType.MCQ_SINGLE:
        if not isinstance(response, MCQResponse):
            raise ScoringError(
                f"response for mcq_single must be MCQResponse, got {type(response).__name__}"
            )
        return _score_mcq(payload, response)
    if payload.widget_type == WidgetType.TRUE_FALSE:
        if not isinstance(response, TrueFalseResponse):
            raise ScoringError(
                f"response for true_false must be TrueFalseResponse, got {type(response).__name__}"
            )
        return _score_true_false(payload, response)
    raise ScoringError(f"No scorer for widget_type={payload.widget_type}")


def _score_mcq(payload: MCQPayload, response: MCQResponse) -> ScoreResult:
    correct = payload.correct_option
    # Validate the selected id exists; a non-existent id is a client bug,
    # not a wrong answer — surface it loudly rather than silently scoring 0.
    if not any(o.id == response.selected_option_id for o in payload.options):
        raise ScoringError(
            f"selected_option_id '{response.selected_option_id}' not in payload options "
            f"{[o.id for o in payload.options]}"
        )
    is_correct = response.selected_option_id == correct.id
    return ScoreResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        # A correct MCQ answer demonstrates understanding of the one concept
        # the question targeted. A wrong answer covers no new concepts.
        concepts_addressed=[payload.concept_tested] if is_correct else [],
        correct_option_id=correct.id,
        explanation=payload.explanation,
    )


def _score_true_false(payload: TrueFalsePayload, response: TrueFalseResponse) -> ScoreResult:
    is_correct = response.answer == payload.is_true
    return ScoreResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        concepts_addressed=[payload.concept_tested] if is_correct else [],
        # "true"/"false" doubles as the option id in the TF templates, keeping
        # the feedback/highlight contract identical to MCQ.
        correct_option_id="true" if payload.is_true else "false",
        explanation=payload.explanation,
    )
