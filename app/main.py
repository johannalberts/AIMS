"""
AIMS FastAPI Application
Adaptive Intelligent Mastery System
"""
import os
import uuid
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Annotated

from fastapi import FastAPI, HTTPException, Depends, Request, Response, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from sqladmin import Admin, ModelView

from app.database import engine, get_session, create_db_and_tables
from app.models import (
    User, UserRole, Course, Lesson, LearningOutcome,
    AssessmentSession, QuestionAnswer, OutcomeProgress, LearningContent
)
from app.auth import (
    get_current_user, require_user, require_admin, require_content_access,
    authenticate_user, create_user, set_session_cookie, SESSION_COOKIE_NAME
)
from app.services.assessment import AssessmentService
from app.services.content import ContentService
from app.services.transcription import get_transcription_service

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
    
    # Initialize Whisper model
    try:
        logger.info("🎤 Initializing Whisper transcription service...")
        get_transcription_service()
        logger.info("✅ Whisper service ready")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Whisper service: {e}")
        logger.warning("⚠️ Voice transcription will not be available")


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


@app.get("/outcome/{outcome_id}/content", response_class=HTMLResponse)
async def outcome_content_page(
    request: Request,
    outcome_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Learning outcome content management page (Admin only)."""
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    lesson = session.get(Lesson, outcome.lesson_id)
    course = session.get(Course, lesson.course_id)
    
    return templates.TemplateResponse("outcome_content.html", {
        "request": request,
        "user": current_user,
        "outcome": outcome,
        "lesson": lesson,
        "course": course
    })


@app.get("/content-management", response_class=HTMLResponse)
async def content_management_page(
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Comprehensive content management page (Admin and Content Manager)."""
    return templates.TemplateResponse("content_management.html", {
        "request": request,
        "user": current_user
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
    
    # Build concept tracking for each outcome FIRST (before enriching messages)
    # Try to get from LangGraph state if available
    from langgraph.checkpoint.postgres import PostgresSaver
    import json
    import os
    
    concept_tracking = {}
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://aims_user:aims_password@postgres:5432/aims_db")
        with PostgresSaver.from_conn_string(db_url) as checkpointer:
            config = {"configurable": {"thread_id": str(assessment.session_id)}}
            checkpoint = checkpointer.get(config)
            
            if checkpoint and checkpoint.get("channel_values"):
                state = checkpoint["channel_values"]
                concepts_covered_state = state.get("concepts_covered", {})
                
                # Build tracking for each outcome
                for outcome in learning_outcomes:
                    # Parse key concepts
                    key_concepts = outcome.key_concepts
                    if key_concepts and isinstance(key_concepts, str):
                        try:
                            key_concepts = json.loads(key_concepts)
                        except:
                            key_concepts = [k.strip() for k in key_concepts.split(',') if k.strip()]
                    elif not key_concepts:
                        key_concepts = []
                    
                    covered = concepts_covered_state.get(outcome.key, [])
                    concept_tracking[outcome.id] = {
                        "all": key_concepts,
                        "covered": covered,
                        "remaining": [c for c in key_concepts if c not in covered]
                    }
    except Exception as e:
        # If checkpoint retrieval fails, build from outcome data
        import logging
        logging.warning(f"Could not retrieve checkpoint for concept tracking: {e}")
        for outcome in learning_outcomes:
            key_concepts = outcome.key_concepts
            if key_concepts and isinstance(key_concepts, str):
                try:
                    key_concepts = json.loads(key_concepts)
                except:
                    key_concepts = [k.strip() for k in key_concepts.split(',') if k.strip()]
            elif not key_concepts:
                key_concepts = []
            
            concept_tracking[outcome.id] = {
                "all": key_concepts,
                "covered": [],
                "remaining": key_concepts
            }
    
    # Now enrich messages (simplified - no concept_info in chat)
    enriched_messages = []
    for msg in messages:
        msg_dict = {
            "id": msg.id,
            "question": msg.question,
            "answer": msg.answer,
            "feedback": msg.feedback,
            "score": msg.score,
            "asked_at": msg.asked_at,
            "answered_at": msg.answered_at,
            "event_type": msg.event_type
        }
        enriched_messages.append(msg_dict)
    
    return templates.TemplateResponse("assessment.html", {
        "request": request,
        "user": current_user,
        "session": assessment,
        "lesson": lesson,
        "learning_outcomes": learning_outcomes,
        "messages": enriched_messages,
        "progress": progress,
        "concept_tracking": concept_tracking
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
    
    # Return HTML fragment with feedback and next question
    return templates.TemplateResponse("partials/feedback.html", {
        "request": {},
        "user_answer": answer,
        "feedback": result["feedback"],
        "score": result.get("score"),
        "status": result["status"],
        "next_question": result.get("next_question"),
        "current_outcome": result.get("current_outcome")
    })


@app.post("/assess/{session_id}/sidebar")
async def update_sidebar(
    session_id: str,
    current_user: User = Depends(require_user),
    db_session: Session = Depends(get_session)
):
    """Return updated sidebar HTML fragment via HTMX."""
    # Get assessment session
    statement = select(AssessmentSession).where(
        AssessmentSession.session_id == session_id
    )
    assessment = db_session.exec(statement).first()
    
    if not assessment or assessment.user_id != current_user.id:
        raise HTTPException(status_code=404)
    
    # Get lesson and learning outcomes
    lesson = db_session.get(Lesson, assessment.lesson_id)
    learning_outcomes = db_session.exec(
        select(LearningOutcome)
        .where(LearningOutcome.lesson_id == lesson.id)
        .order_by(LearningOutcome.order)
    ).all()
    
    # Get progress
    progress = db_session.exec(
        select(OutcomeProgress)
        .where(OutcomeProgress.session_id == assessment.id)
    ).all()
    
    # Build concept tracking from LangGraph state
    from langgraph.checkpoint.postgres import PostgresSaver
    import json
    import os
    
    concept_tracking = {}
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://aims_user:aims_password@postgres:5432/aims_db")
        with PostgresSaver.from_conn_string(db_url) as checkpointer:
            config = {"configurable": {"thread_id": str(assessment.session_id)}}
            checkpoint = checkpointer.get(config)
            
            if checkpoint and checkpoint.get("channel_values"):
                state = checkpoint["channel_values"]
                concepts_covered_state = state.get("concepts_covered", {})
                
                # Build tracking for each outcome
                for outcome in learning_outcomes:
                    # Parse key concepts
                    key_concepts = outcome.key_concepts
                    if key_concepts and isinstance(key_concepts, str):
                        try:
                            key_concepts = json.loads(key_concepts)
                        except:
                            key_concepts = [k.strip() for k in key_concepts.split(',') if k.strip()]
                    elif not key_concepts:
                        key_concepts = []
                    
                    covered = concepts_covered_state.get(outcome.key, [])
                    concept_tracking[outcome.id] = {
                        "all": key_concepts,
                        "covered": covered,
                        "remaining": [c for c in key_concepts if c not in covered]
                    }
    except Exception as e:
        import logging
        logging.warning(f"Could not retrieve checkpoint for sidebar: {e}")
        for outcome in learning_outcomes:
            key_concepts = outcome.key_concepts
            if key_concepts and isinstance(key_concepts, str):
                try:
                    key_concepts = json.loads(key_concepts)
                except:
                    key_concepts = [k.strip() for k in key_concepts.split(',') if k.strip()]
            elif not key_concepts:
                key_concepts = []
            
            concept_tracking[outcome.id] = {
                "all": key_concepts,
                "covered": [],
                "remaining": key_concepts
            }
    
    # Return sidebar partial
    return templates.TemplateResponse("partials/sidebar.html", {
        "request": {},
        "learning_outcomes": learning_outcomes,
        "progress": progress,
        "concept_tracking": concept_tracking
    })


@app.post("/assess/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(require_user)
):
    """
    Transcribe audio file to text using faster-whisper.
    Returns JSON with transcript text.
    """
    temp_file = None
    
    try:
        # Validate file
        if not audio.content_type or not audio.content_type.startswith("audio/"):
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid file type. Please upload an audio file."}
            )
        
        # Check file size (max 10MB)
        content = await audio.read()
        if len(content) > 10 * 1024 * 1024:
            return JSONResponse(
                status_code=400,
                content={"error": "File too large. Maximum size is 10MB."}
            )
        
        # Save to temporary file
        suffix = Path(audio.filename).suffix if audio.filename else ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        logger.info(f"Transcribing audio from user {current_user.username}: {audio.filename}")
        
        # Transcribe
        transcription_service = get_transcription_service()
        result = transcription_service.transcribe_audio(temp_path)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        # Check for errors
        if "error" in result:
            return JSONResponse(
                status_code=400,
                content={"error": result["error"]}
            )
        
        logger.info(f"✅ Transcription successful: {len(result['text'])} chars")
        
        return JSONResponse(content={
            "transcript": result["text"],
            "language": result["language"]
        })
        
    except Exception as e:
        # Clean up temp file if it exists
        if temp_file and os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        
        logger.error(f"❌ Transcription failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Transcription failed: {str(e)}"}
        )


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


@app.delete("/api/assessment/{session_id}")
async def delete_assessment_session(
    session_id: str,
    current_user: User = Depends(require_user),
    db_session: Session = Depends(get_session)
):
    """Delete an assessment session and all related data."""
    statement = select(AssessmentSession).where(
        AssessmentSession.session_id == session_id
    )
    assessment = db_session.exec(statement).first()
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    
    if assessment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this assessment")
    
    # Delete related data (SQLModel will handle cascade if configured, but let's be explicit)
    # Delete all question answers
    db_session.exec(
        select(QuestionAnswer).where(QuestionAnswer.session_id == assessment.id)
    ).all()
    for qa in db_session.exec(
        select(QuestionAnswer).where(QuestionAnswer.session_id == assessment.id)
    ).all():
        db_session.delete(qa)
    
    # Delete all outcome progress
    for progress in db_session.exec(
        select(OutcomeProgress).where(OutcomeProgress.session_id == assessment.id)
    ).all():
        db_session.delete(progress)
    
    # Delete the session itself
    db_session.delete(assessment)
    db_session.commit()
    
    return {"message": "Assessment session deleted successfully"}


# ============================================================================
# Learning Content Management API
# ============================================================================

# ---------- Course CRUD ----------

@app.post("/api/courses")
async def create_course(
    title: Annotated[str, Form()],
    subject: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    difficulty_level: Annotated[str, Form()] = "beginner",
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Create a new course."""
    course = Course(
        title=title,
        subject=subject,
        description=description,
        difficulty_level=difficulty_level
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    
    return {
        "id": course.id,
        "title": course.title,
        "subject": course.subject,
        "description": course.description,
        "difficulty_level": course.difficulty_level
    }


@app.put("/api/courses/{course_id}")
async def update_course(
    course_id: int,
    title: Annotated[str, Form()],
    subject: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    difficulty_level: Annotated[str, Form()] = "beginner",
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Update a course."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course.title = title
    course.subject = subject
    course.description = description
    course.difficulty_level = difficulty_level
    course.updated_at = datetime.utcnow()
    
    session.add(course)
    session.commit()
    session.refresh(course)
    
    return {
        "id": course.id,
        "title": course.title,
        "subject": course.subject,
        "description": course.description,
        "difficulty_level": course.difficulty_level
    }


@app.delete("/api/courses/{course_id}")
async def delete_course(
    course_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Delete a course (soft delete)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course.is_active = False
    course.updated_at = datetime.utcnow()
    session.add(course)
    session.commit()
    
    return {"success": True}


# ---------- Lesson CRUD ----------

@app.post("/api/courses/{course_id}/lessons")
async def create_lesson(
    course_id: int,
    title: Annotated[str, Form()],
    topic: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    estimated_duration_minutes: Annotated[int, Form()] = 60,
    mastery_threshold: Annotated[float, Form()] = 0.8,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Create a new lesson for a course."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get the next order number
    existing_lessons = session.exec(
        select(Lesson).where(Lesson.course_id == course_id)
    ).all()
    next_order = max([l.order for l in existing_lessons], default=-1) + 1
    
    lesson = Lesson(
        course_id=course_id,
        title=title,
        topic=topic,
        description=description,
        order=next_order,
        estimated_duration_minutes=estimated_duration_minutes,
        mastery_threshold=mastery_threshold
    )
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    
    return {
        "id": lesson.id,
        "course_id": lesson.course_id,
        "title": lesson.title,
        "topic": lesson.topic,
        "description": lesson.description,
        "order": lesson.order,
        "estimated_duration_minutes": lesson.estimated_duration_minutes,
        "mastery_threshold": lesson.mastery_threshold
    }


@app.put("/api/lessons/{lesson_id}")
async def update_lesson(
    lesson_id: int,
    title: Annotated[str, Form()],
    topic: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    estimated_duration_minutes: Annotated[int, Form()] = 60,
    mastery_threshold: Annotated[float, Form()] = 0.8,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Update a lesson."""
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    lesson.title = title
    lesson.topic = topic
    lesson.description = description
    lesson.estimated_duration_minutes = estimated_duration_minutes
    lesson.mastery_threshold = mastery_threshold
    lesson.updated_at = datetime.utcnow()
    
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    
    return {
        "id": lesson.id,
        "course_id": lesson.course_id,
        "title": lesson.title,
        "topic": lesson.topic,
        "description": lesson.description,
        "estimated_duration_minutes": lesson.estimated_duration_minutes,
        "mastery_threshold": lesson.mastery_threshold
    }


@app.delete("/api/lessons/{lesson_id}")
async def delete_lesson(
    lesson_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Delete a lesson (soft delete)."""
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    lesson.is_active = False
    lesson.updated_at = datetime.utcnow()
    session.add(lesson)
    session.commit()
    
    return {"success": True}


# ---------- Learning Outcome CRUD ----------

@app.post("/api/lessons/{lesson_id}/outcomes")
async def create_learning_outcome(
    lesson_id: int,
    key: Annotated[str, Form()],
    description: Annotated[str, Form()],
    key_concepts: Annotated[str, Form()] = "",
    examples: Annotated[str, Form()] = "",
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Create a new learning outcome for a lesson."""
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    # Get the next order number
    existing_outcomes = session.exec(
        select(LearningOutcome).where(LearningOutcome.lesson_id == lesson_id)
    ).all()
    next_order = max([o.order for o in existing_outcomes], default=-1) + 1
    
    outcome = LearningOutcome(
        lesson_id=lesson_id,
        key=key,
        description=description,
        order=next_order,
        key_concepts=key_concepts if key_concepts else None,
        examples=examples if examples else None
    )
    session.add(outcome)
    session.commit()
    session.refresh(outcome)
    
    return {
        "id": outcome.id,
        "lesson_id": outcome.lesson_id,
        "key": outcome.key,
        "description": outcome.description,
        "order": outcome.order,
        "key_concepts": outcome.key_concepts,
        "examples": outcome.examples
    }


@app.put("/api/outcomes/{outcome_id}")
async def update_learning_outcome(
    outcome_id: int,
    key: Annotated[str, Form()],
    description: Annotated[str, Form()],
    key_concepts: Annotated[str, Form()] = "",
    examples: Annotated[str, Form()] = "",
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Update a learning outcome."""
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    outcome.key = key
    outcome.description = description
    outcome.key_concepts = key_concepts if key_concepts else None
    outcome.examples = examples if examples else None
    outcome.updated_at = datetime.utcnow()
    
    session.add(outcome)
    session.commit()
    session.refresh(outcome)
    
    return {
        "id": outcome.id,
        "lesson_id": outcome.lesson_id,
        "key": outcome.key,
        "description": outcome.description,
        "key_concepts": outcome.key_concepts,
        "examples": outcome.examples
    }


@app.delete("/api/outcomes/{outcome_id}")
async def delete_learning_outcome(
    outcome_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Delete a learning outcome (soft delete)."""
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    outcome.is_active = False
    outcome.updated_at = datetime.utcnow()
    session.add(outcome)
    session.commit()
    
    return {"success": True}


@app.get("/api/content-management/all")
async def get_all_content(
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Get all courses with lessons, outcomes, and content for management interface."""
    # Get all active courses
    courses = session.exec(
        select(Course).where(Course.is_active == True).order_by(Course.id)
    ).all()
    
    result = {"courses": []}
    
    for course in courses:
        # Get lessons for this course
        lessons = session.exec(
            select(Lesson)
            .where(Lesson.course_id == course.id)
            .where(Lesson.is_active == True)
            .order_by(Lesson.order)
        ).all()
        
        course_data = {
            "id": course.id,
            "title": course.title,
            "subject": course.subject,
            "description": course.description,
            "difficulty_level": course.difficulty_level,
            "lessons": []
        }
        
        for lesson in lessons:
            # Get learning outcomes for this lesson
            outcomes = session.exec(
                select(LearningOutcome)
                .where(LearningOutcome.lesson_id == lesson.id)
                .where(LearningOutcome.is_active == True)
                .order_by(LearningOutcome.order)
            ).all()
            
            lesson_data = {
                "id": lesson.id,
                "title": lesson.title,
                "topic": lesson.topic,
                "description": lesson.description,
                "learning_outcomes": []
            }
            
            for outcome in outcomes:
                # Get content for this outcome
                content_service = ContentService(session)
                content_chunks = content_service.get_content_for_outcome(
                    outcome.id,
                    approved_only=False  # Show all content in management interface
                )
                
                # Parse key_concepts from JSON if it's a string
                import json
                key_concepts = outcome.key_concepts
                if key_concepts and isinstance(key_concepts, str):
                    try:
                        key_concepts = json.loads(key_concepts)
                    except:
                        # If it fails, split by comma as fallback
                        key_concepts = [k.strip() for k in key_concepts.split(',') if k.strip()]
                
                outcome_data = {
                    "id": outcome.id,
                    "key": outcome.key,
                    "description": outcome.description,
                    "key_concepts": key_concepts,
                    "examples": outcome.examples,
                    "content_chunks": [
                        {
                            "id": chunk.id,
                            "content_text": chunk.content_text,
                            "content_type": chunk.content_type,
                            "source": chunk.source,
                            "approval_status": chunk.approval_status,
                            "created_at": chunk.created_at.isoformat(),
                        }
                        for chunk in content_chunks
                    ]
                }
                
                lesson_data["learning_outcomes"].append(outcome_data)
            
            course_data["lessons"].append(lesson_data)
        
        result["courses"].append(course_data)
    
    return result


@app.get("/api/content/{content_id}")
async def get_single_content(
    content_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Get a single content chunk for editing."""
    content = session.get(LearningContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    return {
        "id": content.id,
        "learning_outcome_id": content.learning_outcome_id,
        "content_text": content.content_text,
        "content_type": content.content_type,
        "approval_status": content.approval_status,
        "source": content.source
    }


@app.post("/api/outcomes/{outcome_id}/process-pdf")
async def process_pdf_upload(
    outcome_id: int,
    file: Annotated[bytes, Form()],
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Process uploaded PDF and extract text for content creation."""
    # Verify outcome exists
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    # Check file size (10MB limit)
    if len(file) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF file too large (max 10MB)")
    
    content_service = ContentService(session)
    
    try:
        from io import BytesIO
        pdf_buffer = BytesIO(file)
        result = content_service.process_pdf(pdf_buffer, outcome_id)
        return result
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/outcomes/{outcome_id}/content")
async def get_outcome_content(
    outcome_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session)
):
    """Get all content chunks for a learning outcome."""
    # Verify outcome exists
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    content_service = ContentService(session)
    
    # Admins see all content, learners only see approved
    approved_only = current_user.role != UserRole.ADMIN
    chunks = content_service.get_content_for_outcome(outcome_id, approved_only=approved_only)
    
    return {
        "learning_outcome_id": outcome_id,
        "outcome_description": outcome.description,
        "content_chunks": [
            {
                "id": chunk.id,
                "content_text": chunk.content_text,
                "content_type": chunk.content_type,
                "chunk_order": chunk.chunk_order,
                "source": chunk.source,
                "approval_status": chunk.approval_status,
                "created_at": chunk.created_at.isoformat(),
                "updated_at": chunk.updated_at.isoformat()
            }
            for chunk in chunks
        ]
    }


@app.post("/api/outcomes/{outcome_id}/content")
async def create_outcome_content(
    outcome_id: int,
    content_text: Annotated[str, Form()],
    content_type: Annotated[str, Form()] = "explanation",
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Create a new content chunk for a learning outcome (manual upload)."""
    # Verify outcome exists
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    content_service = ContentService(session)
    
    try:
        # Get current max chunk_order
        existing_chunks = content_service.get_content_for_outcome(outcome_id, approved_only=False)
        chunk_order = len(existing_chunks)
        
        chunk = content_service.create_content_chunk(
            learning_outcome_id=outcome_id,
            content_text=content_text,
            content_type=content_type,
            source="manual",
            user_id=current_user.id,
            approval_status="approved",
            chunk_order=chunk_order
        )
        
        return {
            "id": chunk.id,
            "learning_outcome_id": chunk.learning_outcome_id,
            "content_text": chunk.content_text,
            "content_type": chunk.content_type,
            "chunk_order": chunk.chunk_order,
            "source": chunk.source,
            "approval_status": chunk.approval_status,
            "message": "Content chunk created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating content chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outcomes/{outcome_id}/generate-content")
async def generate_outcome_content(
    outcome_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Generate learning content for an outcome using LLM."""
    # Verify outcome exists
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    content_service = ContentService(session)
    
    try:
        result = content_service.generate_content_for_outcome(
            learning_outcome_id=outcome_id,
            user_id=current_user.id
        )
        
        return result
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outcomes/{outcome_id}/generate-and-save-content")
async def generate_and_save_outcome_content(
    outcome_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Generate and immediately save learning content for an outcome (for bulk operations)."""
    # Verify outcome exists
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    content_service = ContentService(session)
    
    try:
        result = content_service.generate_and_save_content(
            learning_outcome_id=outcome_id,
            user_id=current_user.id,
            approval_status="approved"  # Auto-approve for bulk generation
        )
        
        return result
    except Exception as e:
        logger.error(f"Error generating and saving content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lessons/suggest-structure")
async def suggest_lesson_structure(
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Generate AI-suggested lesson structure with learning outcomes."""
    body = await request.json()
    
    lesson_title = body.get("lesson_title", "")
    lesson_topic = body.get("lesson_topic", "")
    lesson_description = body.get("lesson_description", "")
    course_id = body.get("course_id")
    
    if not lesson_title or not lesson_topic:
        raise HTTPException(status_code=400, detail="Lesson title and topic are required")
    
    # Get course context if course_id provided
    course_context = ""
    if course_id:
        course = session.get(Course, course_id)
        if course:
            course_context = f"{course.title} - {course.subject} ({course.difficulty_level})"
    
    content_service = ContentService(session)
    
    try:
        result = content_service.suggest_lesson_structure(
            lesson_title=lesson_title,
            lesson_topic=lesson_topic,
            lesson_description=lesson_description,
            course_context=course_context
        )
        
        return result
    except Exception as e:
        logger.error(f"Error suggesting lesson structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lessons/create-from-suggestion")
async def create_lesson_from_suggestion(
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Create a lesson and learning outcomes from AI suggestion after approval."""
    body = await request.json()
    
    course_id = body.get("course_id")
    lesson_title = body.get("lesson_title")
    lesson_topic = body.get("lesson_topic")
    lesson_description = body.get("lesson_description", "")
    lesson_overview = body.get("lesson_overview", "")
    estimated_duration_minutes = body.get("estimated_duration_minutes", 60)
    learning_outcomes = body.get("learning_outcomes", [])
    
    if not course_id or not lesson_title or not lesson_topic:
        raise HTTPException(status_code=400, detail="Course ID, lesson title, and topic are required")
    
    # Verify course exists
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    try:
        # Get the next order number
        existing_lessons = session.exec(
            select(Lesson).where(Lesson.course_id == course_id)
        ).all()
        next_order = max([l.order for l in existing_lessons], default=-1) + 1
        
        # Create the lesson
        lesson = Lesson(
            course_id=course_id,
            title=lesson_title,
            topic=lesson_topic,
            description=lesson_overview if lesson_overview else lesson_description,
            order=next_order,
            estimated_duration_minutes=estimated_duration_minutes
        )
        session.add(lesson)
        session.flush()  # Get lesson ID without committing
        
        # Create learning outcomes
        created_outcomes = []
        for idx, lo_data in enumerate(learning_outcomes):
            # Convert key_concepts array to JSON string if it's a list
            key_concepts = lo_data.get("key_concepts")
            if isinstance(key_concepts, list):
                import json
                key_concepts = json.dumps(key_concepts)
            
            outcome = LearningOutcome(
                lesson_id=lesson.id,
                key=lo_data.get("key", f"outcome_{idx}"),
                description=lo_data.get("description", ""),
                order=idx,
                key_concepts=key_concepts,
                examples=lo_data.get("examples")
            )
            session.add(outcome)
            created_outcomes.append({
                "key": outcome.key,
                "description": outcome.description,
                "order": outcome.order
            })
        
        session.commit()
        session.refresh(lesson)
        
        return {
            "lesson": {
                "id": lesson.id,
                "course_id": lesson.course_id,
                "title": lesson.title,
                "topic": lesson.topic,
                "description": lesson.description,
                "order": lesson.order,
                "estimated_duration_minutes": lesson.estimated_duration_minutes
            },
            "learning_outcomes": created_outcomes,
            "success": True
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating lesson from suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/courses/suggest-structure")
async def suggest_course_structure(
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Generate AI-suggested complete course structure with lessons and learning outcomes."""
    body = await request.json()
    
    course_title = body.get("title", "")
    subject = body.get("subject", "")
    description = body.get("description", "")
    difficulty_level = body.get("difficulty_level", "intermediate")
    
    if not course_title or not subject:
        raise HTTPException(status_code=400, detail="Course title and subject are required")
    
    content_service = ContentService(session)
    
    try:
        result = content_service.suggest_course_structure(
            course_title=course_title,
            subject=subject,
            description=description,
            difficulty_level=difficulty_level
        )
        
        return result
    except Exception as e:
        logger.error(f"Error suggesting course structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/courses/create-from-suggestion")
async def create_course_from_suggestion(
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Create a course with lessons and learning outcomes from AI suggestion after approval."""
    body = await request.json()
    
    course_title = body.get("title")
    subject = body.get("subject")
    description = body.get("description", "")
    difficulty_level = body.get("difficulty_level", "intermediate")
    lessons_data = body.get("lessons", [])
    
    if not course_title or not subject:
        raise HTTPException(status_code=400, detail="Course title and subject are required")
    
    try:
        # Create the course
        course = Course(
            title=course_title,
            subject=subject,
            description=description,
            difficulty_level=difficulty_level
        )
        session.add(course)
        session.flush()  # Get course ID without committing
        
        # Create lessons and learning outcomes
        created_lessons = []
        for lesson_idx, lesson_data in enumerate(lessons_data):
            lesson = Lesson(
                course_id=course.id,
                title=lesson_data.get("title", ""),
                topic=lesson_data.get("topic", ""),
                description=lesson_data.get("description", ""),
                order=lesson_idx,
                estimated_duration_minutes=lesson_data.get("estimated_duration_minutes", 60)
            )
            session.add(lesson)
            session.flush()  # Get lesson ID
            
            # Create learning outcomes for this lesson
            created_outcomes = []
            for outcome_idx, outcome_data in enumerate(lesson_data.get("learning_outcomes", [])):
                # Convert key_concepts array to JSON string if it's a list
                key_concepts = outcome_data.get("key_concepts")
                if isinstance(key_concepts, list):
                    import json
                    key_concepts = json.dumps(key_concepts)
                
                outcome = LearningOutcome(
                    lesson_id=lesson.id,
                    key=outcome_data.get("key", f"outcome_{outcome_idx}"),
                    description=outcome_data.get("description", ""),
                    order=outcome_idx,
                    key_concepts=key_concepts,
                    examples=outcome_data.get("examples")
                )
                session.add(outcome)
                created_outcomes.append({
                    "key": outcome.key,
                    "description": outcome.description,
                    "order": outcome.order
                })
            
            created_lessons.append({
                "id": lesson.id,
                "title": lesson.title,
                "topic": lesson.topic,
                "description": lesson.description,
                "order": lesson.order,
                "learning_outcomes": created_outcomes
            })
        
        session.commit()
        session.refresh(course)
        
        return {
            "course": {
                "id": course.id,
                "title": course.title,
                "subject": course.subject,
                "description": course.description,
                "difficulty_level": course.difficulty_level
            },
            "lessons": created_lessons,
            "success": True
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating course from suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outcomes/{outcome_id}/save-generated-content")
async def save_generated_content(
    outcome_id: int,
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Save LLM-generated content chunks after admin review."""
    # Verify outcome exists
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    # Get chunks from request body
    body = await request.json()
    chunks = body.get("chunks", [])
    
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks provided")
    
    content_service = ContentService(session)
    
    try:
        saved_chunks = content_service.save_generated_content(
            learning_outcome_id=outcome_id,
            chunks=chunks,
            user_id=current_user.id,
            approval_status="approved"
        )
        
        return {
            "message": f"Successfully saved {len(saved_chunks)} content chunks",
            "chunks": [
                {
                    "id": chunk.id,
                    "content_type": chunk.content_type,
                    "chunk_order": chunk.chunk_order
                }
                for chunk in saved_chunks
            ]
        }
    except Exception as e:
        logger.error(f"Error saving generated content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/content")
async def create_content_chunk(
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Create a new content chunk."""
    form = await request.form()
    
    outcome_id = int(form.get("outcome_id"))
    content_type = form.get("content_type", "explanation")
    content_text = form.get("content_text")
    
    if not outcome_id or not content_text:
        raise HTTPException(status_code=400, detail="Outcome ID and content text are required")
    
    # Verify outcome exists
    outcome = session.get(LearningOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learning outcome not found")
    
    content_service = ContentService(session)
    
    try:
        # Get current max chunk order for this outcome
        existing_chunks = content_service.get_content_for_outcome(outcome_id, approved_only=False)
        next_order = max([c.chunk_order for c in existing_chunks], default=-1) + 1
        
        chunk = content_service.create_content_chunk(
            learning_outcome_id=outcome_id,
            content_text=content_text,
            content_type=content_type,
            chunk_order=next_order,
            source="manual",
            user_id=current_user.id,
            approval_status="approved"
        )
        
        return {
            "id": chunk.id,
            "content_text": chunk.content_text,
            "content_type": chunk.content_type,
            "chunk_order": chunk.chunk_order,
            "message": "Content chunk created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating content chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/content/{content_id}")
async def update_content_chunk(
    content_id: int,
    request: Request,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Update a content chunk."""
    body = await request.json()
    
    content_service = ContentService(session)
    
    try:
        updated_chunk = content_service.update_content_chunk(
            content_id=content_id,
            content_text=body.get("content_text"),
            content_type=body.get("content_type"),
            approval_status=body.get("approval_status"),
            approved_by_user_id=current_user.id
        )
        
        if not updated_chunk:
            raise HTTPException(status_code=404, detail="Content chunk not found")
        
        return {
            "id": updated_chunk.id,
            "content_text": updated_chunk.content_text,
            "content_type": updated_chunk.content_type,
            "approval_status": updated_chunk.approval_status,
            "message": "Content chunk updated successfully"
        }
    except Exception as e:
        logger.error(f"Error updating content chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/content/{content_id}")
async def delete_content_chunk(
    content_id: int,
    current_user: User = Depends(require_content_access),
    session: Session = Depends(get_session)
):
    """Delete a content chunk."""
    content_service = ContentService(session)
    
    success = content_service.delete_content_chunk(content_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Content chunk not found")
    
    return {"message": "Content chunk deleted successfully"}


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
    form_excluded_columns = [LearningOutcome.outcome_progress, LearningOutcome.content_chunks, LearningOutcome.created_at, LearningOutcome.updated_at]


class LearningContentAdmin(ModelView, model=LearningContent):
    """Admin view for LearningContent model."""
    column_list = [LearningContent.id, LearningContent.learning_outcome_id, LearningContent.content_type, LearningContent.approval_status, LearningContent.source]
    column_searchable_list = [LearningContent.content_text]
    column_details_exclude_list = [LearningContent.embedding]  # Exclude vector from detail view
    form_excluded_columns = [LearningContent.embedding, LearningContent.created_at, LearningContent.updated_at]


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
admin.add_view(LearningContentAdmin)
admin.add_view(AssessmentSessionAdmin)

# ============================================================================
# Static Files (CSS, JS, images)
# ============================================================================

app.mount("/static", StaticFiles(directory="app/static"), name="static")
