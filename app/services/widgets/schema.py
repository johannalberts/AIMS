"""
Structured payload schemas for interactive assessment widgets.

Each widget type defines:
- A QuestionPayload subclass (what the generator produces and the judge validates)
- A LearnerResponse subclass (what the learner submits via the UI)

All payloads carry a `widget_type` discriminator so the judge, scorer, and
renderer can dispatch by type. Payloads are Pydantic models so the LLM's
structured output is validated on construction.

M1 implements single-answer MCQ. The base classes and the discriminated-union
pattern are designed so additional widget types slot in without changing the
judge/scorer/generator contracts.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WidgetType(str, Enum):
    """Discriminator for widget payload types. New types added in later milestones."""
    MCQ_SINGLE = "mcq_single"
    # Reserved for later milestones:
    # TRUE_FALSE = "true_false"
    # MATCHING = "matching"
    # ORDERING = "ordering"
    # CATEGORIZATION = "categorization"
    # FILL_IN = "fill_in"
    # FREE_TEXT = "free_text"


# ---------------------------------------------------------------------------
# Shared context models (passed to generator and judge, not persisted as payload)
# ---------------------------------------------------------------------------

class GenerationContext(BaseModel):
    """Context handed to the question generator for one generation call.

    Captures everything the generator needs to produce a gap-targeted question
    that avoids repeating previously asked stems/distractors (defeats
    memorization, see PLAN_v3.md §9).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    topic: str
    outcome_description: str
    outcome_key: str
    key_concepts: List[str]
    targeted_concept: str
    # Concepts already covered for this outcome (exclude from targeting):
    concepts_covered: List[str] = Field(default_factory=list)
    # Previously asked questions for this concept — generator must avoid reuse:
    questions_asked: List["AskedQuestionRef"] = Field(default_factory=list)
    # How many times the learner has failed this concept (drives difficulty):
    failed_attempts: int = 0
    # Widget types already used for this concept (drives escalation):
    widget_history: List[WidgetType] = Field(default_factory=list)


class AskedQuestionRef(BaseModel):
    """Lightweight reference to a previously asked question, for dedup.

    Only the surface details the generator needs to avoid repetition are kept;
    the full payload lives in LessonState.questions_asked and in QuestionAnswer
    rows.
    """
    widget_type: WidgetType
    stem: str
    option_texts: List[str] = Field(default_factory=list)


class JudgeContext(BaseModel):
    """Context handed to the judge alongside a payload.

    Carries the signal the rules layer needs (e.g. valid concepts to align
    against, previously asked stems for dedup) without coupling the judge to
    LessonState.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    outcome_key: str
    valid_concepts: List[str]
    questions_asked: List[AskedQuestionRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Base payload / response
# ---------------------------------------------------------------------------

class QuestionPayload(BaseModel):
    """Base for all widget question payloads. Subclasses set widget_type."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    widget_type: WidgetType
    # Which key concept this question targets (drives concept-coverage mapping):
    concept_tested: str
    # Short human label for admin/history views (denormalized from payload):
    stem: str
    # Optional explanation shown after answering (for feedback/teach panel):
    explanation: Optional[str] = None
    # Difficulty hint, may be adjusted by escalation logic:
    difficulty: Optional[str] = None


class LearnerResponse(BaseModel):
    """Base for all widget learner responses. Subclasses set widget_type."""
    widget_type: WidgetType


# ---------------------------------------------------------------------------
# MCQ (single answer) — M1
# ---------------------------------------------------------------------------

class MCQOption(BaseModel):
    """One option in a single-answer MCQ."""
    id: str = Field(description="Stable option id, e.g. 'a','b','c','d'")
    text: str
    is_correct: bool = False


class MCQPayload(QuestionPayload):
    """Structured payload for a single-answer multiple-choice question."""
    widget_type: Literal[WidgetType.MCQ_SINGLE] = WidgetType.MCQ_SINGLE
    options: List[MCQOption] = Field(min_length=2, max_length=6)

    @field_validator("options")
    @classmethod
    def _exactly_one_correct(cls, v: List[MCQOption]) -> List[MCQOption]:
        correct = [o for o in v if o.is_correct]
        if len(correct) != 1:
            raise ValueError(
                f"MCQ must have exactly one correct option, got {len(correct)}"
            )
        return v

    @property
    def correct_option(self) -> MCQOption:
        return next(o for o in self.options if o.is_correct)

    @property
    def option_texts(self) -> List[str]:
        return [o.text for o in self.options]


class MCQResponse(LearnerResponse):
    """Learner's response to an MCQ — the id of the selected option."""
    widget_type: Literal[WidgetType.MCQ_SINGLE] = WidgetType.MCQ_SINGLE
    selected_option_id: str


# ---------------------------------------------------------------------------
# Discriminated unions for dispatch
# ---------------------------------------------------------------------------

# Annotated unions let the judge/scorer dispatch on widget_type. New widget
# types are appended here when their schemas land.
QuestionPayloadUnion = Annotated[
    Union[MCQPayload],
    Field(discriminator="widget_type"),
]
LearnerResponseUnion = Annotated[
    Union[MCQResponse],
    Field(discriminator="widget_type"),
]


# ---------------------------------------------------------------------------
# Score result
# ---------------------------------------------------------------------------

class ScoreResult(BaseModel):
    """Result of deterministically scoring a learner response.

    `score` is 0.0-1.0 for this single question. `concepts_addressed` lists
    the concept(s) the learner demonstrated understanding of by answering
    correctly — for MCQ this is either [concept_tested] on a correct answer
    or [] on a wrong one. The assessment layer folds this into
    LessonState.concepts_covered and recomputes outcome mastery as
    covered/total concepts (same coverage model as v2).
    """
    is_correct: bool
    score: float
    concepts_addressed: List[str] = Field(default_factory=list)
    # The id of the correct option (for feedback / highlight in the UI):
    correct_option_id: Optional[str] = None
    # Optional explanation echoed back from the payload for the teach panel:
    explanation: Optional[str] = None


# Forward-ref resolution for GenerationContext / JudgeContext
GenerationContext.model_rebuild()
JudgeContext.model_rebuild()
