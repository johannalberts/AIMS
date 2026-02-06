#!/usr/bin/env python3
"""
Create a test course for vegetable gardening with key concepts.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlmodel import Session, select
from app.models import Course, Lesson, LearningOutcome, User
from app.services.content import ContentService
import json

def create_vegetable_course():
    """Create a comprehensive vegetable gardening course with AI-generated structure."""
    with Session(engine) as session:
        # Get admin user
        admin = session.exec(select(User).where(User.username == "admin")).first()
        
        print("🌱 Generating AI course structure for vegetable gardening...")
        
        # Use ContentService to generate course structure
        content_service = ContentService(session)
        
        try:
            result = content_service.suggest_course_structure(
                course_title="Growing Your Own Vegetables",
                subject="Gardening & Agriculture",
                description="Learn the fundamentals of vegetable gardening, from soil preparation to harvest. Perfect for beginners who want to grow fresh, organic vegetables at home.",
                difficulty_level="beginner"
            )
            
            print(f"✓ Generated structure with {len(result['suggestion']['lessons'])} lessons")
            
            # Create the course
            course = Course(
                title=result["course_title"],
                subject=result["subject"],
                description=result["suggestion"]["course_overview"],
                difficulty_level=result["difficulty_level"]
            )
            session.add(course)
            session.flush()
            
            print(f"✓ Created course: {course.title} (ID: {course.id})")
            
            # Create lessons and learning outcomes
            for lesson_idx, lesson_data in enumerate(result["suggestion"]["lessons"]):
                lesson = Lesson(
                    course_id=course.id,
                    title=lesson_data["title"],
                    topic=lesson_data["topic"],
                    description=lesson_data.get("description", ""),
                    order=lesson_idx,
                    estimated_duration_minutes=lesson_data.get("estimated_duration_minutes", 60)
                )
                session.add(lesson)
                session.flush()
                
                print(f"  ✓ Lesson {lesson_idx + 1}: {lesson.title}")
                
                # Create learning outcomes
                for outcome_idx, outcome_data in enumerate(lesson_data.get("learning_outcomes", [])):
                    # Convert key_concepts array to JSON string
                    key_concepts = outcome_data.get("key_concepts", [])
                    if isinstance(key_concepts, list):
                        key_concepts_str = json.dumps(key_concepts)
                    else:
                        key_concepts_str = key_concepts
                    
                    outcome = LearningOutcome(
                        lesson_id=lesson.id,
                        key=outcome_data.get("key", f"outcome_{outcome_idx}"),
                        description=outcome_data.get("description", ""),
                        order=outcome_idx,
                        key_concepts=key_concepts_str,
                        examples=outcome_data.get("examples", "")
                    )
                    session.add(outcome)
                    
                    # Parse key concepts for display
                    concepts = json.loads(key_concepts_str) if key_concepts_str else []
                    concepts_str = ", ".join(concepts[:3])  # Show first 3
                    if len(concepts) > 3:
                        concepts_str += f" (+{len(concepts) - 3} more)"
                    
                    print(f"    → {outcome.key}: {concepts_str}")
            
            session.commit()
            
            print(f"\n✅ Course created successfully!")
            print(f"   Course ID: {course.id}")
            print(f"   Total Lessons: {len(result['suggestion']['lessons'])}")
            print(f"\n🎯 You can now test the assessment at:")
            print(f"   http://localhost:8000/course/{course.id}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            session.rollback()

if __name__ == "__main__":
    create_vegetable_course()
