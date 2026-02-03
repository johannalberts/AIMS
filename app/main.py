"""
AIMS FastAPI Application
Adaptive Intelligent Mastery System
"""
import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Annotated

from fastapi import FastAPI, HTTPException, Depends, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from sqladmin import Admin, ModelView

from app.database import engine, get_session, create_db_and_tables
from app.models import (
    User, UserRole, Course, Lesson, LearningOutcome,
    AssessmentSession, QuestionAnswer, OutcomeProgress
)
from app.auth import (
    get_current_user, require_user, require_admin,
    authenticate_user, create_user, set_session_cookie, SESSION_COOKIE_NAME
)
from app.services.assessment import AssessmentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="AIMS API",
    description="Adaptive Intelligent Mastery System",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def on_startup():
    """Initialize database and create tables."""
    logger.info("🚀 Starting AIMS application...")
    create_db_and_tables()
    logger.info("✅ Database tables created/verified")


# ============================================================================
# Authentication Routes
# ============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: Session = Depends(get_session)
):
    """Handle login form submission."""
    user = authenticate_user(email, password, session)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create redirect response and set cookie on it
    if user.role == UserRole.ADMIN:
        redirect_url = "/admin"
    else:
        redirect_url = "/dashboard"
    
    response = RedirectResponse(redirect_url, status_code=303)
    set_session_cookie(response, user.id)
    
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Display registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register(
    response: Response,
    email: Annotated[str, Form()],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: Session = Depends(get_session)
):
    """Handle registration form submission."""
    try:
        user = create_user(email, username, password, UserRole.LEARNER, session)
        set_session_cookie(response, user.id)
        return RedirectResponse("/dashboard", status_code=303)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/logout")
async def logout(response: Response):
    """Handle logout."""
    response.delete_cookie(SESSION_COOKIE_NAME)
    return RedirectResponse("/login", status_code=303)


@app.get("/logout")
async def logout_get(response: Response):
    """Handle logout via GET for convenience."""
    response.delete_cookie(SESSION_COOKIE_NAME)
    return RedirectResponse("/login", status_code=303)


# ============================================================================
# Learner Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Root page - redirect to appropriate location."""
    if current_user:
        if current_user.role == UserRole.ADMIN:
            return RedirectResponse("/admin")
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session)
):
    """Learner dashboard - shows available courses and progress."""
    # Get all active courses
    courses = session.exec(
        select(Course).where(Course.is_active == True)
    ).all()
    
    # Get user's assessment sessions
    user_sessions = session.exec(
        select(AssessmentSession).where(AssessmentSession.user_id == current_user.id)
    ).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "courses": courses,
        "sessions": user_sessions
    })


@app.get("/course/{course_id}", response_class=HTMLResponse)
async def view_course(
    request: Request,
    course_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session)
):
    """View course details and lessons."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get lessons for this course
    lessons = session.exec(
        select(Lesson)
        .where(Lesson.course_id == course_id)
        .where(Lesson.is_active == True)
        .order_by(Lesson.order)
    ).all()
    
    return templates.TemplateResponse("course.html", {
        "request": request,
        "user": current_user,
        "course": course,
        "lessons": lessons
    })


@app.get("/lesson/{lesson_id}/start", response_class=HTMLResponse)
async def start_lesson(
    request: Request,
    lesson_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session)
):
    """Start a new assessment session for a lesson."""
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    # Create new assessment session
    session_id = str(uuid.uuid4())
    assessment_session = AssessmentSession(
        session_id=session_id,
        user_id=current_user.id,
        lesson_id=lesson_id,
        status="in_progress"
    )
    session.add(assessment_session)
    session.commit()
    session.refresh(assessment_session)
    
    # Initialize assessment service and get first question
    service = AssessmentService(session)
    result = service.start_assessment(assessment_session.id)
    
    return RedirectResponse(f"/assess/{session_id}", status_code=303)


@app.get("/assess/{session_id}", response_class=HTMLResponse)
async def assessment_interface(
    request: Request,
    session_id: str,
    current_user: User = Depends(require_user),
    db_session: Session = Depends(get_session)
):
    """Assessment chat interface."""
    # Get assessment session
    statement = select(AssessmentSession).where(
        AssessmentSession.session_id == session_id
    )
    assessment = db_session.exec(statement).first()
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    
    # Verify ownership
    if assessment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get lesson and learning outcomes
    lesson = db_session.get(Lesson, assessment.lesson_id)
    learning_outcomes = db_session.exec(
        select(LearningOutcome)
        .where(LearningOutcome.lesson_id == lesson.id)
        .order_by(LearningOutcome.order)
    ).all()
    
    # Get conversation history
    messages = db_session.exec(
        select(QuestionAnswer)
        .where(QuestionAnswer.session_id == assessment.id)
        .order_by(QuestionAnswer.asked_at)
    ).all()
    
    # Get progress
    progress = db_session.exec(
        select(OutcomeProgress)
        .where(OutcomeProgress.session_id == assessment.id)
    ).all()
    
    return templates.TemplateResponse("assessment.html", {
        "request": request,
        "user": current_user,
        "session": assessment,
        "lesson": lesson,
        "learning_outcomes": learning_outcomes,
        "messages": messages,
        "progress": progress
    })


@app.post("/assess/{session_id}/answer")
async def submit_answer(
    session_id: str,
    answer: Annotated[str, Form()],
    current_user: User = Depends(require_user),
    db_session: Session = Depends(get_session)
):
    """Submit an answer (returns HTML fragment via HTMX)."""
    # Get assessment session
    statement = select(AssessmentSession).where(
        AssessmentSession.session_id == session_id
    )
    assessment = db_session.exec(statement).first()
    
    if not assessment or assessment.user_id != current_user.id:
        raise HTTPException(status_code=404)
    
    # Process answer
    service = AssessmentService(db_session)
    result = service.process_answer(assessment.id, answer)
    
    # Return HTML fragment with feedback
    return templates.TemplateResponse("partials/feedback.html", {
        "request": {},
        "feedback": result["feedback"],
        "score": result.get("score"),
        "status": result["status"]
    })


# ============================================================================
# API Routes (for HTMX)
# ============================================================================

@app.get("/api/progress/{session_id}")
async def get_progress(
    session_id: str,
    current_user: User = Depends(require_user),
    db_session: Session = Depends(get_session)
):
    """Get current progress for a session."""
    statement = select(AssessmentSession).where(
        AssessmentSession.session_id == session_id
    )
    assessment = db_session.exec(statement).first()
    
    if not assessment or assessment.user_id != current_user.id:
        raise HTTPException(status_code=404)
    
    progress = db_session.exec(
        select(OutcomeProgress)
        .where(OutcomeProgress.session_id == assessment.id)
    ).all()
    
    return {
        "progress": [
            {
                "outcome_id": p.learning_outcome_id,
                "mastery_level": p.mastery_level,
                "is_mastered": p.is_mastered
            }
            for p in progress
        ]
    }


# ============================================================================
# SQLAdmin Setup
# ============================================================================

class UserAdmin(ModelView, model=User):
    """Admin view for User model."""
    column_list = [User.id, User.email, User.username, User.role, User.is_active, User.created_at]
    column_searchable_list = [User.email, User.username]
    column_sortable_list = [User.id, User.email, User.created_at]
    form_excluded_columns = [User.assessment_sessions, User.created_at, User.updated_at]


class CourseAdmin(ModelView, model=Course):
    """Admin view for Course model."""
    column_list = [Course.id, Course.title, Course.subject, Course.difficulty_level, Course.is_active]
    column_searchable_list = [Course.title, Course.subject]
    form_excluded_columns = [Course.lessons, Course.created_at, Course.updated_at]


class LessonAdmin(ModelView, model=Lesson):
    """Admin view for Lesson model."""
    column_list = [Lesson.id, Lesson.title, Lesson.course_id, Lesson.order, Lesson.mastery_threshold]
    column_searchable_list = [Lesson.title, Lesson.topic]
    form_excluded_columns = [Lesson.learning_outcomes, Lesson.assessment_sessions, Lesson.created_at, Lesson.updated_at]


class LearningOutcomeAdmin(ModelView, model=LearningOutcome):
    """Admin view for LearningOutcome model."""
    column_list = [LearningOutcome.id, LearningOutcome.key, LearningOutcome.lesson_id, LearningOutcome.order]
    column_searchable_list = [LearningOutcome.key, LearningOutcome.description]
    form_excluded_columns = [LearningOutcome.outcome_progress, LearningOutcome.created_at, LearningOutcome.updated_at]


class AssessmentSessionAdmin(ModelView, model=AssessmentSession):
    """Admin view for AssessmentSession model."""
    column_list = [AssessmentSession.id, AssessmentSession.session_id, AssessmentSession.user_id, AssessmentSession.lesson_id, AssessmentSession.status]
    can_create = False
    can_edit = False


# Initialize SQLAdmin
admin = Admin(app, engine, title="AIMS Admin")
admin.add_view(UserAdmin)
admin.add_view(CourseAdmin)
admin.add_view(LessonAdmin)
admin.add_view(LearningOutcomeAdmin)
admin.add_view(AssessmentSessionAdmin)

# ============================================================================
# Static Files (CSS, JS, images)
# ============================================================================

app.mount("/static", StaticFiles(directory="app/static"), name="static")
