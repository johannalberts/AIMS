import os
import uuid
import logging
import traceback
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId

from app.services.graph import AIMSGraph

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
logger.info(f"Connecting to MongoDB at: {MONGODB_URL}")
try:
    client = MongoClient(MONGODB_URL)
    db = client["aims_db"]
    # Test connection
    client.admin.command('ping')
    logger.info("✅ MongoDB connection successful")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    raise

# FastAPI app
app = FastAPI(
    title="AIMS API",
    description="Adaptive Intelligent Mastery System API",
    version="1.0.0"
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class StartAssessmentRequest(BaseModel):
    lesson_id: str

class SubmitAnswerRequest(BaseModel):
    session_id: str
    answer: str

class ContinueRequest(BaseModel):
    session_id: str

# In-memory session storage (in production, use Redis or database)
active_sessions: Dict[str, Dict[str, Any]] = {}


# API Endpoints

@app.get("/api/lessons")
async def get_lessons():
    """Get all available lessons."""
    try:
        logger.info("📚 Fetching lessons from database...")
        lessons = list(db.lessons.find())
        logger.info(f"✅ Found {len(lessons)} lessons")
        
        # Convert ObjectId to string for JSON serialization
        for lesson in lessons:
            lesson["_id"] = str(lesson["_id"])
            logger.debug(f"  - {lesson.get('title', 'Untitled')} (ID: {lesson['_id']})")
        
        return lessons
    except Exception as e:
        logger.error(f"❌ Error fetching lessons: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/assessment/start")
async def start_assessment(request: StartAssessmentRequest):
    """Start a new assessment session."""
    try:
        logger.info(f"🎯 Starting assessment for lesson: {request.lesson_id}")
        
        # Fetch lesson from database
        logger.info(f"📖 Fetching lesson from database...")
        lesson = db.lessons.find_one({"_id": ObjectId(request.lesson_id)})
        
        if not lesson:
            logger.error(f"❌ Lesson not found: {request.lesson_id}")
            raise HTTPException(status_code=404, detail="Lesson not found")
        
        logger.info(f"✅ Found lesson: {lesson.get('title', 'Untitled')}")
        logger.info(f"   Topic: {lesson.get('topic', 'Unknown')}")
        logger.info(f"   Learning outcomes: {len(lesson.get('learning_outcomes', {}))}")
        
        # Create AIMS initial state
        logger.info("🔧 Creating initial AIMS state...")
        initial_state = AIMSGraph.create_initial_state(
            topic=lesson["topic"],
            learning_outcomes=lesson["learning_outcomes"]
        )
        logger.info(f"✅ Initial state created with {len(initial_state['learning_outcomes'])} outcomes")
        
        # Initialize AIMS graph
        logger.info("🤖 Initializing AIMS graph...")
        graph = AIMSGraph()
        logger.info("✅ Graph initialized")
        
        # Start assessment (get first question)
        logger.info("💭 Generating first question...")
        result = graph.invoke(initial_state)
        logger.info(f"✅ First question generated for outcome: {result.get('current_outcome_key')}")
        logger.debug(f"   Question: {result.get('last_question', '')[:100]}...")
        
        # Create session
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = {
            "lesson_id": str(lesson["_id"]),
            "graph": graph,
            "state": result,
            "created_at": datetime.utcnow()
        }
        logger.info(f"✅ Session created: {session_id}")
        logger.info(f"📊 Active sessions: {len(active_sessions)}")
        
        return {
            "session_id": session_id,
            "lesson_title": lesson["title"],
            "lesson_topic": lesson["topic"],
            "session_state": result,
            "status": "in_progress"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting assessment: {type(e).__name__}: {e}")
        logger.error(f"📋 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.post("/api/assessment/submit")
async def submit_answer(request: SubmitAnswerRequest):
    """Submit an answer to the current question."""
    try:
        logger.info(f"📝 Submitting answer for session: {request.session_id}")
        logger.debug(f"   Answer length: {len(request.answer)} characters")
        
        # Get session
        session = active_sessions.get(request.session_id)
        if not session:
            logger.error(f"❌ Session not found: {request.session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        
        logger.info("✅ Session found")
        
        # Update state with user response
        current_state = session["state"]
        current_outcome = current_state.get("current_outcome_key")
        logger.info(f"🎯 Current outcome: {current_outcome}")
        
        current_state["last_response"] = request.answer
        
        # Process answer through graph
        logger.info("🤖 Processing answer through AIMS graph...")
        graph = session["graph"]
        result = graph.invoke(current_state)
        
        logger.info(f"✅ Answer processed")
        logger.info(f"   Feedback: {result.get('feedback', '')[:100]}...")
        logger.info(f"   Next outcome: {result.get('current_outcome_key')}")
        
        # Update session
        session["state"] = result
        
        # Check if all outcomes are mastered
        all_mastered = result.get("current_outcome_key") == "all_mastered"
        if all_mastered:
            logger.info("🎉 All outcomes mastered! Assessment complete!")
        
        return {
            "session_id": request.session_id,
            "session_state": result,
            "status": "completed" if all_mastered else "in_progress"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error submitting answer: {type(e).__name__}: {e}")
        logger.error(f"📋 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.post("/api/assessment/next")
async def continue_assessment(request: ContinueRequest):
    """Continue to the next question."""
    try:
        logger.info(f"➡️  Continuing assessment for session: {request.session_id}")
        
        # Get session
        session = active_sessions.get(request.session_id)
        if not session:
            logger.error(f"❌ Session not found: {request.session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        
        logger.info("✅ Session found")
        
        # Get current state and invoke graph to get next question
        current_state = session["state"]
        current_outcome = current_state.get("current_outcome_key")
        logger.info(f"🎯 Current outcome: {current_outcome}")
        
        graph = session["graph"]
        
        # Clear last response for next question
        current_state["last_response"] = ""
        
        logger.info("💭 Generating next question...")
        result = graph.invoke(current_state)
        
        logger.info(f"✅ Next question generated")
        logger.debug(f"   Question: {result.get('last_question', '')[:100]}...")
        
        # Update session
        session["state"] = result
        
        return {
            "session_id": request.session_id,
            "session_state": result,
            "status": "in_progress"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error continuing assessment: {type(e).__name__}: {e}")
        logger.error(f"📋 Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get current session state."""
    logger.info(f"🔍 Fetching session: {session_id}")
    
    session = active_sessions.get(session_id)
    if not session:
        logger.error(f"❌ Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    logger.info("✅ Session found")
    
    return {
        "session_id": session_id,
        "session_state": session["state"],
        "lesson_id": session["lesson_id"],
        "created_at": session["created_at"]
    }


@app.get("/")
async def read_root():
    """Root endpoint - redirects to static frontend."""
    logger.info("🏠 Root endpoint accessed")
    return {"message": "AIMS API is running", "docs": "/docs", "frontend": "/index.html"}


# Startup event
@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("=" * 60)
    logger.info("🚀 AIMS API Starting Up")
    logger.info("=" * 60)
    logger.info(f"📊 MongoDB URL: {MONGODB_URL}")
    logger.info(f"🔑 OpenAI API Key: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not Set'}")
    logger.info(f"📁 Static files directory: static/")
    logger.info("=" * 60)


# Mount static files (frontend) - must be last
app.mount("/", StaticFiles(directory="static", html=True), name="static")
