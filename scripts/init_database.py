#!/usr/bin/env python3
"""
AIMS PostgreSQL Database Initialization Script
==============================================
This script initializes the PostgreSQL database with sample data including:
- Admin user
- Sample courses
- Lessons with learning outcomes

Usage:
    uv run python scripts/init_database.py
"""

import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.database import engine, create_db_and_tables
from app.models import (
    User, UserRole, Course, Lesson, LearningOutcome
)


def create_admin_user(session: Session):
    """Create default admin user."""
    # Check if admin exists
    existing = session.exec(
        select(User).where(User.email == "admin@aims.com")
    ).first()
    
    if existing:
        print("✅ Admin user already exists")
        return existing
    
    admin = User(
        email="admin@aims.com",
        username="admin",
        hashed_password=User.hash_password("admin123"),
        role=UserRole.ADMIN
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    
    print(f"✅ Created admin user: admin@aims.com / admin123")
    return admin


def create_sample_learner(session: Session):
    """Create sample learner user."""
    existing = session.exec(
        select(User).where(User.email == "learner@aims.com")
    ).first()
    
    if existing:
        print("✅ Sample learner already exists")
        return existing
    
    learner = User(
        email="learner@aims.com",
        username="demo_learner",
        hashed_password=User.hash_password("learner123"),
        role=UserRole.LEARNER
    )
    session.add(learner)
    session.commit()
    session.refresh(learner)
    
    print(f"✅ Created sample learner: learner@aims.com / learner123")
    return learner


def create_python_oop_course(session: Session):
    """Create Python OOP course with lessons."""
    # Check if course exists
    existing = session.exec(
        select(Course).where(Course.title == "Python Object-Oriented Programming")
    ).first()
    
    if existing:
        print("✅ Python OOP course already exists")
        return existing
    
    # Create course
    course = Course(
        title="Python Object-Oriented Programming",
        subject="Computer Science",
        description="Master the fundamentals of object-oriented programming in Python, including classes, objects, inheritance, and polymorphism.",
        difficulty_level="intermediate"
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    
    print(f"✅ Created course: {course.title}")
    
    # Create lesson
    lesson = Lesson(
        course_id=course.id,
        title="Python OOP Fundamentals",
        topic="Python OOP",
        description="Learn the core concepts of object-oriented programming in Python.",
        order=1,
        estimated_duration_minutes=120,
        mastery_threshold=0.8
    )
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    
    print(f"✅ Created lesson: {lesson.title}")
    
    # Create learning outcomes
    outcomes_data = [
        {
            "key": "class_definition",
            "description": "Understanding how to define and structure classes in Python with proper syntax and conventions",
            "order": 1,
            "key_concepts": "Class keyword, naming conventions, instance variables, class variables, __init__ method",
            "examples": "Creating basic classes with attributes and methods"
        },
        {
            "key": "methods_and_self",
            "description": "Understanding instance methods, the self parameter, and how objects interact with their methods",
            "order": 2,
            "key_concepts": "Instance methods, self parameter, method calls, accessing attributes",
            "examples": "Defining and calling methods on class instances"
        },
        {
            "key": "inheritance",
            "description": "Understanding class inheritance, parent-child relationships, and method overriding",
            "order": 3,
            "key_concepts": "Parent classes, child classes, super(), method overriding, isinstance()",
            "examples": "Creating subclasses that extend parent class functionality"
        },
        {
            "key": "encapsulation",
            "description": "Understanding data hiding, private attributes, and property decorators",
            "order": 4,
            "key_concepts": "Private attributes (_var, __var), @property decorator, getters/setters",
            "examples": "Protecting class data and providing controlled access"
        },
        {
            "key": "polymorphism",
            "description": "Understanding polymorphism, duck typing, and method overriding in Python",
            "order": 5,
            "key_concepts": "Duck typing, method overriding, abstract base classes, interface patterns",
            "examples": "Writing code that works with multiple object types"
        },
        {
            "key": "special_methods",
            "description": "Understanding Python special methods (dunder methods) like __str__, __repr__, __eq__",
            "order": 6,
            "key_concepts": "__str__, __repr__, __eq__, __len__, __add__, operator overloading",
            "examples": "Customizing object behavior and string representation"
        }
    ]
    
    for outcome_data in outcomes_data:
        outcome = LearningOutcome(
            lesson_id=lesson.id,
            **outcome_data
        )
        session.add(outcome)
    
    session.commit()
    print(f"✅ Created {len(outcomes_data)} learning outcomes")
    
    return course


def create_web_development_course(session: Session):
    """Create Web Development course."""
    existing = session.exec(
        select(Course).where(Course.title == "Modern Web Development")
    ).first()
    
    if existing:
        print("✅ Web Development course already exists")
        return existing
    
    course = Course(
        title="Modern Web Development",
        subject="Web Development",
        description="Learn modern web development with HTML, CSS, and JavaScript",
        difficulty_level="beginner"
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    
    print(f"✅ Created course: {course.title}")
    
    # HTML Fundamentals Lesson
    html_lesson = Lesson(
        course_id=course.id,
        title="HTML Fundamentals",
        topic="HTML",
        description="Master the building blocks of web pages",
        order=1,
        estimated_duration_minutes=90,
        mastery_threshold=0.8
    )
    session.add(html_lesson)
    session.commit()
    session.refresh(html_lesson)
    
    print(f"✅ Created lesson: {html_lesson.title}")
    
    # HTML Learning Outcomes
    html_outcomes = [
        {
            "key": "html_structure",
            "description": "Understanding HTML document structure and basic syntax",
            "order": 1,
            "key_concepts": "DOCTYPE, html, head, body, basic tags",
            "examples": "Creating a valid HTML document structure"
        },
        {
            "key": "semantic_html",
            "description": "Understanding semantic HTML elements and their proper usage",
            "order": 2,
            "key_concepts": "header, nav, main, article, section, footer, aside",
            "examples": "Using semantic tags to structure content meaningfully"
        },
        {
            "key": "forms_and_inputs",
            "description": "Understanding HTML forms and input elements",
            "order": 3,
            "key_concepts": "form, input, textarea, select, button, validation",
            "examples": "Creating interactive forms with proper input types"
        }
    ]
    
    for outcome_data in html_outcomes:
        outcome = LearningOutcome(
            lesson_id=html_lesson.id,
            **outcome_data
        )
        session.add(outcome)
    
    session.commit()
    print(f"✅ Created {len(html_outcomes)} HTML learning outcomes")
    
    return course


def main():
    """Main initialization function."""
    print("=" * 60)
    print("🚀 Initializing AIMS Database")
    print("=" * 60)
    
    # Create tables
    print("\n📊 Creating database tables...")
    create_db_and_tables()
    print("✅ Tables created")
    
    # Create data
    with Session(engine) as session:
        print("\n👤 Creating users...")
        create_admin_user(session)
        create_sample_learner(session)
        
        print("\n📚 Creating courses...")
        create_python_oop_course(session)
        create_web_development_course(session)
    
    print("\n" + "=" * 60)
    print("✅ Database initialization complete!")
    print("=" * 60)
    print("\n🔑 Login Credentials:")
    print("   Admin: admin@aims.com / admin123")
    print("   Learner: learner@aims.com / learner123")
    print("\n🌐 Access:")
    print("   Frontend: http://localhost:8000")
    print("   Admin Panel: http://localhost:8000/admin")
    print("   API Docs: http://localhost:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    main()
