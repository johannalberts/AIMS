"""
Widget-based assessment primitives for AIMS v3.

This package contains the structured question payload schemas, judge,
deterministic scorer, and LLM-driven generator for interactive assessment
widgets. Each widget type (MCQ, true/false, matching, etc.) has its own
schema and scoring logic; the judge and generator dispatch by widget_type.

v1 (M1) implements single-answer MCQ only. Additional types are added in
later milestones without modifying the dispatch contracts.
"""
from app.services.widgets.schema import (
    WidgetType,
    QuestionPayload,
    LearnerResponse,
    MCQOption,
    MCQPayload,
    MCQResponse,
    ScoreResult,
    GenerationContext,
    JudgeContext,
)
from app.services.widgets.llm import build_llm, llm_available, provider_name, LLMConfigError

__all__ = [
    "WidgetType",
    "QuestionPayload",
    "LearnerResponse",
    "MCQOption",
    "MCQPayload",
    "MCQResponse",
    "ScoreResult",
    "GenerationContext",
    "JudgeContext",
    "build_llm",
    "llm_available",
    "provider_name",
    "LLMConfigError",
]
