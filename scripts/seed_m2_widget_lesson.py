#!/usr/bin/env python3
"""
Seed a small test course/lesson with `use_widget_assessment = True` so the M2
MCQ widget pipeline can be exercised end-to-end in the browser.

Idempotent: skips creation if the course/lesson already exist.

Run: uv run python scripts/seed_m2_widget_lesson.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select

from app.database import engine
from app.models import (
    AssessmentSession,
    Course,
    Lesson,
    LearningOutcome,
    QuestionAnswer,
    OutcomeProgress,
    User,
)

COURSE_TITLE = "M2 Widget Test Course"
LESSON_TITLE = "Vegetable Gardening — Widget Assessment"


def _seed():
    with Session(engine) as session:
        course = session.exec(
            select(Course).where(Course.title == COURSE_TITLE)
        ).first()
        if not course:
            course = Course(
                title=COURSE_TITLE,
                subject="Gardening",
                description="Small course for validating the M2 widget assessment path.",
                difficulty_level="beginner",
            )
            session.add(course)
            session.commit()
            session.refresh(course)
            print(f"✓ created course id={course.id}")

        lesson = session.exec(
            select(Lesson).where(Lesson.title == LESSON_TITLE)
        ).first()
        if not lesson:
            lesson = Lesson(
                course_id=course.id,
                title=LESSON_TITLE,
                topic="Vegetable Gardening",
                description="Two outcomes, three concepts each — enough to see widget routing.",
                order=0,
                estimated_duration_minutes=15,
                mastery_threshold=0.8,
                use_widget_assessment=True,
            )
            session.add(lesson)
            session.commit()
            session.refresh(lesson)
            print(f"✓ created lesson id={lesson.id} (use_widget_assessment=True)")
        else:
            if not lesson.use_widget_assessment:
                lesson.use_widget_assessment = True
                session.add(lesson)
                session.commit()
                print(f"✓ enabled use_widget_assessment on lesson id={lesson.id}")
            else:
                print(f"✓ lesson already configured (id={lesson.id})")

        outcomes_data = [
            {
                "key": "garden_benefits",
                "description": "Understand the benefits and types of home vegetable gardens",
                "concepts": ["benefits", "types", "sustainability"],
            },
            {
                "key": "soil_basics",
                "description": "Understand soil preparation and the role of compost",
                "concepts": ["soil preparation", "composting", "drainage"],
            },
        ]
        existing_outcomes = session.exec(
            select(LearningOutcome).where(LearningOutcome.lesson_id == lesson.id)
        ).all()
        if existing_outcomes:
            print(f"✓ lesson already has {len(existing_outcomes)} outcomes")
        else:
            for idx, o in enumerate(outcomes_data):
                session.add(
                    LearningOutcome(
                        lesson_id=lesson.id,
                        key=o["key"],
                        description=o["description"],
                        order=idx,
                        key_concepts=json.dumps(o["concepts"]),
                    )
                )
            session.commit()
            print(f"✓ created {len(outcomes_data)} outcomes")

        learner = session.exec(
            select(User).where(User.email == "learner@aims.com")
        ).first()
        if not learner:
            print("⚠️  learner@aims.com does not exist. Run scripts/init_database.py first.")
        else:
            print(f"  learner: {learner.username} (id={learner.id})")

        print()
        print("Next steps:")
        print(f"  1. uv run python scripts/migrate_m2_widget_payload.py  (if not run yet)")
        print(f"  2. uv run uvicorn app.main:app --reload")
        print(f"  3. Login as learner@aims.com, browse course id={course.id}, start the lesson.")


if __name__ == "__main__":
    _seed()