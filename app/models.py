"""
SQLModel database models for AIMS platform.
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlmodel import SQLModel, Field, Relationship
import bcrypt

# No longer using passlib - using bcrypt directly


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    LEARNER = "learner"


class User(SQLModel, table=True):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole = Field(default=UserRole.LEARNER)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    assessment_sessions: List["AssessmentSession"] = Relationship(back_populates="user")
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        # Bcrypt has a 72-byte limit
        password_bytes = password.encode('utf-8')[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')


class Course(SQLModel, table=True):
    """Course model - top level organizational unit."""
    __tablename__ = "courses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    subject: str
    description: Optional[str] = None
    difficulty_level: Optional[str] = None  # beginner, intermediate, advanced
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    lessons: List["Lesson"] = Relationship(back_populates="course")


class Lesson(SQLModel, table=True):
    """Lesson model - contains learning outcomes to be assessed."""
    __tablename__ = "lessons"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id")
    title: str = Field(index=True)
    topic: str
    description: Optional[str] = None
    order: int = Field(default=0)  # Order within the course
    estimated_duration_minutes: Optional[int] = None
    mastery_threshold: float = Field(default=0.8)  # Default 80%
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    course: Course = Relationship(back_populates="lessons")
    learning_outcomes: List["LearningOutcome"] = Relationship(back_populates="lesson")
    assessment_sessions: List["AssessmentSession"] = Relationship(back_populates="lesson")


class LearningOutcome(SQLModel, table=True):
    """Learning outcome model - specific skills/knowledge to be mastered."""
    __tablename__ = "learning_outcomes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    lesson_id: int = Field(foreign_key="lessons.id")
    key: str = Field(index=True)  # Unique key within lesson (e.g., "class_definition")
    description: str
    order: int = Field(default=0)  # Order within the lesson
    key_concepts: Optional[str] = None  # JSON string or text
    examples: Optional[str] = None  # JSON string or text
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    lesson: Lesson = Relationship(back_populates="learning_outcomes")
    outcome_progress: List["OutcomeProgress"] = Relationship(back_populates="learning_outcome")


class AssessmentSession(SQLModel, table=True):
    """Assessment session model - tracks a learner's attempt at a lesson."""
    __tablename__ = "assessment_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(unique=True, index=True)  # UUID
    user_id: int = Field(foreign_key="users.id")
    lesson_id: int = Field(foreign_key="lessons.id")
    status: str = Field(default="in_progress")  # in_progress, completed, abandoned
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[int] = None
    
    # LangGraph state (serialized)
    current_outcome_key: Optional[str] = None
    last_question: Optional[str] = None
    failed_attempts: int = Field(default=0)
    
    # Relationships
    user: User = Relationship(back_populates="assessment_sessions")
    lesson: Lesson = Relationship(back_populates="assessment_sessions")
    question_answers: List["QuestionAnswer"] = Relationship(back_populates="session")
    outcome_progress: List["OutcomeProgress"] = Relationship(back_populates="session")


class QuestionAnswer(SQLModel, table=True):
    """Individual question-answer pair in an assessment session."""
    __tablename__ = "question_answers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="assessment_sessions.id")
    learning_outcome_id: int = Field(foreign_key="learning_outcomes.id")
    
    question: str
    answer: Optional[str] = None
    feedback: Optional[str] = None
    score: Optional[float] = None  # 0.0 to 1.0
    
    event_type: str = Field(default="question")  # question, rephrase, re_teach
    
    asked_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: Optional[datetime] = None
    time_spent_seconds: Optional[int] = None
    
    # Relationships
    session: AssessmentSession = Relationship(back_populates="question_answers")


class OutcomeProgress(SQLModel, table=True):
    """Tracks progress on individual learning outcomes within a session."""
    __tablename__ = "outcome_progress"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="assessment_sessions.id")
    learning_outcome_id: int = Field(foreign_key="learning_outcomes.id")
    
    mastery_level: float = Field(default=0.0)  # Current mastery (0.0 to 1.0)
    is_mastered: bool = Field(default=False)
    attempts: int = Field(default=0)
    
    started_at: datetime = Field(default_factory=datetime.utcnow)
    mastered_at: Optional[datetime] = None
    time_spent_seconds: Optional[int] = None
    
    # Relationships
    session: AssessmentSession = Relationship(back_populates="outcome_progress")
    learning_outcome: LearningOutcome = Relationship(back_populates="outcome_progress")
