"""
Assessment service - integrates LangGraph with database persistence.
"""
import logging
from datetime import datetime
from typing import Dict, Any
from sqlmodel import Session, select

from app.models import (
    AssessmentSession, LearningOutcome, QuestionAnswer, OutcomeProgress
)
from app.services.graph import AIMSGraph

logger = logging.getLogger(__name__)


class AssessmentService:
    """Service for managing assessment sessions with database persistence."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.graph = AIMSGraph()
    
    def start_assessment(self, assessment_id: int) -> Dict[str, Any]:
        """Start an assessment session and generate first question."""
        # Get assessment session
        assessment = self.db_session.get(AssessmentSession, assessment_id)
        if not assessment:
            raise ValueError("Assessment session not found")
        
        # Get learning outcomes for this lesson
        outcomes = self.db_session.exec(
            select(LearningOutcome)
            .where(LearningOutcome.lesson_id == assessment.lesson_id)
            .where(LearningOutcome.is_active == True)
            .order_by(LearningOutcome.order)
        ).all()
        
        if not outcomes:
            raise ValueError("No learning outcomes found for this lesson")
        
        # Get lesson
        from app.models import Lesson
        lesson = self.db_session.get(Lesson, assessment.lesson_id)
        
        # Initialize outcome progress records
        for outcome in outcomes:
            progress = OutcomeProgress(
                session_id=assessment.id,
                learning_outcome_id=outcome.id,
                mastery_level=0.0,
                is_mastered=False,
                attempts=0
            )
            self.db_session.add(progress)
        
        self.db_session.commit()
        
        # Build learning outcomes dict for LangGraph
        learning_outcomes_dict = {}
        for outcome in outcomes:
            learning_outcomes_dict[outcome.key] = {
                "description": outcome.description,
                "mastery_level": 0.0
            }
        
        # Create initial LangGraph state
        initial_state = AIMSGraph.create_initial_state(
            topic=lesson.topic,
            learning_outcomes=learning_outcomes_dict
        )
        
        # Generate first question
        result = self.graph.invoke(initial_state)
        
        # Update assessment session with current state
        assessment.current_outcome_key = result.get("current_outcome_key")
        assessment.last_question = result.get("last_question")
        assessment.failed_attempts = result.get("failed_attempts", 0)
        self.db_session.commit()
        
        # Create question record
        current_outcome = next(
            (o for o in outcomes if o.key == result.get("current_outcome_key")),
            None
        )
        
        if current_outcome:
            qa = QuestionAnswer(
                session_id=assessment.id,
                learning_outcome_id=current_outcome.id,
                question=result.get("last_question"),
                event_type="question"
            )
            self.db_session.add(qa)
            self.db_session.commit()
        
        return result
    
    def process_answer(self, assessment_id: int, answer: str) -> Dict[str, Any]:
        """Process a user's answer and get next question or feedback."""
        # Get assessment session
        assessment = self.db_session.get(AssessmentSession, assessment_id)
        if not assessment:
            raise ValueError("Assessment session not found")
        
        # Get learning outcomes
        outcomes = self.db_session.exec(
            select(LearningOutcome)
            .where(LearningOutcome.lesson_id == assessment.lesson_id)
            .where(LearningOutcome.is_active == True)
        ).all()
        
        # Get current progress
        progress_records = self.db_session.exec(
            select(OutcomeProgress)
            .where(OutcomeProgress.session_id == assessment.id)
        ).all()
        
        # Build current state from database
        learning_outcomes_dict = {}
        for outcome in outcomes:
            progress = next(
                (p for p in progress_records if p.learning_outcome_id == outcome.id),
                None
            )
            learning_outcomes_dict[outcome.key] = {
                "description": outcome.description,
                "mastery_level": progress.mastery_level if progress else 0.0
            }
        
        # Reconstruct LangGraph state
        current_state = {
            "topic": assessment.lesson.topic,
            "learning_outcomes": learning_outcomes_dict,
            "current_outcome_key": assessment.current_outcome_key,
            "last_question": assessment.last_question,
            "last_response": answer,
            "failed_attempts": assessment.failed_attempts,
            "feedback": ""
        }
        
        # Process through LangGraph
        result = self.graph.invoke(current_state)
        
        # Update the last question-answer record with the answer and feedback
        from sqlalchemy import desc
        last_qa = self.db_session.exec(
            select(QuestionAnswer)
            .where(QuestionAnswer.session_id == assessment.id)
            .where(QuestionAnswer.answer == None)
            .order_by(desc(QuestionAnswer.asked_at))
        ).first()
        
        if last_qa:
            last_qa.answer = answer
            last_qa.feedback = result.get("feedback")
            last_qa.answered_at = datetime.utcnow()
            
            # Extract score from feedback if available
            # This would need to be enhanced based on actual LangGraph output
            if "mastery_level" in result.get("learning_outcomes", {}).get(assessment.current_outcome_key, {}):
                last_qa.score = result["learning_outcomes"][assessment.current_outcome_key]["mastery_level"]
        
        # Update progress records
        for outcome_key, outcome_data in result.get("learning_outcomes", {}).items():
            outcome = next((o for o in outcomes if o.key == outcome_key), None)
            if outcome:
                progress = next(
                    (p for p in progress_records if p.learning_outcome_id == outcome.id),
                    None
                )
                if progress:
                    progress.mastery_level = outcome_data.get("mastery_level", 0.0)
                    progress.is_mastered = progress.mastery_level >= assessment.lesson.mastery_threshold
                    progress.attempts += 1
                    
                    if progress.is_mastered and not progress.mastered_at:
                        progress.mastered_at = datetime.utcnow()
        
        # Update assessment session
        assessment.current_outcome_key = result.get("current_outcome_key")
        assessment.last_question = result.get("last_question")
        assessment.failed_attempts = result.get("failed_attempts", 0)
        
        # Check if completed
        if result.get("current_outcome_key") == "all_mastered":
            assessment.status = "completed"
            assessment.completed_at = datetime.utcnow()
        
        self.db_session.commit()
        
        # If there's a new question, create a new QA record
        if result.get("last_question") and result.get("current_outcome_key") != "all_mastered":
            current_outcome = next(
                (o for o in outcomes if o.key == result.get("current_outcome_key")),
                None
            )
            
            if current_outcome:
                event_type = "question"
                # Determine event type based on feedback
                if "rephrase" in result.get("feedback", "").lower():
                    event_type = "rephrase"
                elif "re-teach" in result.get("feedback", "").lower() or "let me explain" in result.get("feedback", "").lower():
                    event_type = "re_teach"
                
                qa = QuestionAnswer(
                    session_id=assessment.id,
                    learning_outcome_id=current_outcome.id,
                    question=result.get("last_question"),
                    event_type=event_type
                )
                self.db_session.add(qa)
                self.db_session.commit()
        
        return {
            "feedback": result.get("feedback"),
            "score": last_qa.score if last_qa else None,
            "status": assessment.status,
            "current_outcome": result.get("current_outcome_key"),
            "next_question": result.get("last_question")
        }
