# AIMS: Adaptive Intelligent Mastery System

## Overview

AIMS (Adaptive Intelligent Mastery System) is a revolutionary educational assessment platform that moves beyond traditional static testing to create personalized, mastery-based learning experiences. Instead of asking predetermined questions, AIMS adapts to each student's understanding and dynamically generates assessments that ensure true comprehension of learning outcomes.

## 🎯 Core Concept

Traditional assessments rely on static questions that may not capture a student's actual understanding. AIMS takes a fundamentally different approach:

- **Mastery-Focused**: Each learning outcome must reach a specified mastery threshold (80%+) before moving on
- **Concept-Level Tracking**: Individual key concepts within each outcome are tracked and visualized
- **Adaptive Questioning**: Questions are generated in real-time based on the student's current understanding and missing concepts
- **Intelligent Remediation**: When students struggle, the system rephrases questions or provides targeted re-teaching
- **Continuous Assessment**: No more one-and-done tests - students work until they demonstrate true mastery
- **Rich Persistence**: Complete conversation history, concept coverage, and mastery progression stored in PostgreSQL

## 🧠 How It Works

AIMS uses a sophisticated graph-based workflow powered by LangGraph and large language models to create an intelligent tutoring system:

### Assessment Flow

1. **Outcome Selection**: The system identifies learning outcomes that haven't reached mastery
2. **Dynamic Question Generation**: AI generates questions tailored to test specific learning outcomes and missing key concepts
3. **Intelligent Assessment**: Student responses are evaluated for:
   - Understanding depth (not just correctness)
   - Which specific concepts were addressed
   - Mastery level calculation (0-100%)
4. **Concept Tracking**: Real-time tracking of which concepts have been covered vs. remaining
5. **Adaptive Response**:
   - ✅ **Mastery Achieved** (80%+): Positive feedback and move to next outcome
   - 🔄 **Partial Understanding** (20-80%): Targeted follow-up on missing concepts with acknowledgment of what was correct
   - 📚 **Needs Re-teaching** (<20%): Comprehensive explanation and retry
6. **State Persistence**: All progress, concept coverage, and conversation history saved to database

### Example Learning Journey

For an HTML lesson with learning outcomes like "Understanding HTML tags and semantics":

1. Student receives a contextual question about semantic HTML
2. Response is evaluated for depth of understanding
3. If unclear, question is rephrased with scaffolding
4. If fundamental gaps exist, concept is re-taught with examples
5. Process continues until student demonstrates mastery

## 🏗️ Technical Architecture

### Backend (FastAPI)
- **RESTful API**: Handles assessment sessions and state management
- **PostgreSQL Database**: Relational database with SQLModel ORM
- **LangGraph Integration**: Orchestrates the adaptive assessment workflow
- **OpenAI Integration**: Powers intelligent question generation and assessment
- **SQLAdmin**: Web-based admin interface for content management
- **Session Authentication**: Secure cookie-based auth with role-based access

### Frontend
- **Jinja2 Templates**: Server-side rendering
- **HTMX**: Dynamic HTML updates without page reloads
- **Alpine.js**: Reactive client-side components
- **Modern CSS**: Responsive, chat-style interface

### Key Components

```
app/
├── main.py              # FastAPI application & routes
├── models.py            # SQLModel database models
├── database.py          # PostgreSQL connection & checkpointer
├── auth.py              # Authentication & authorization
├── services/
│   ├── assessment.py    # Assessment logic & persistence
│   ├── graph.py         # LangGraph AI workflow
│   ├── content.py       # Content management API
│   └── transcription.py # Voice-to-text (faster-whisper)
├── templates/           # Jinja2 HTML templates
│   ├── assessment.html  # Chat-style assessment interface
│   ├── content_management.html  # Content CRUD interface
│   └── partials/        # HTMX partial responses
└── static/
    ├── css/             # Organized stylesheets
    └── js/              # Modular JavaScript components
```

### Assessment Graph Nodes

- **choose_outcome**: Selects next learning outcome to assess based on mastery levels
- **generate_question**: Creates tailored questions using AI, considering:
  - Current mastery level (0-100%)
  - Concepts already covered
  - Concepts still needed
  - Whether this is a follow-up or fresh question
- **assess_answer**: Evaluates student responses for:
  - Mastery score (0.0-1.0)
  - Specific concepts addressed in the answer
  - Updated concept coverage state
- **rephrase_question**: Provides hints and clarification when needed
- **re_teach_concept**: Delivers targeted remediation with examples
- **provide_feedback**: Celebrates mastery achievement and transitions to next outcome

### LangGraph State Management

The assessment graph maintains rich state including:
- **learning_outcomes**: Dict of all outcomes with mastery levels
- **concepts_covered**: Dict mapping outcome keys to lists of covered concepts
- **current_outcome_key**: Which outcome is being assessed
- **last_question**: Most recent question generated
- **last_response**: Student's most recent answer
- **failed_attempts**: Counter for adaptive difficulty
- **feedback**: Generated feedback text

State is persisted using PostgresSaver checkpointer for seamless session continuity.

## 🚀 Getting Started

### Prerequisites

- Python 3.12+ (for local development)
- OpenAI API key
- Docker & Docker Compose
- uv package manager (for local development)

### Installation

```bash
# Clone the repository
git clone https://github.com/johannalberts/AIMS.git
cd aims

# Create .env file from example
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=your-actual-key-here
```

### Quick Start Options

**Choose your preferred setup:**

#### Option 1: Local Development (Recommended for Development)
PostgreSQL in Docker, FastAPI running locally for faster iteration and hot reload.

```bash
# 1. Automated setup (one-time)
./scripts/quick_start.sh

# 2. Start the application
uv run uvicorn app.main:app --reload

# 3. Open your browser
# Navigate to: http://localhost:8000
```

#### Option 2: Full Docker (Production-like)
Everything runs in Docker containers.

```bash
# 1. Start all services
docker compose up --build

# 2. Initialize database (one-time, in another terminal)
docker compose exec web uv run python scripts/init_database.py

# 3. Open your browser
# Navigate to: http://localhost:8000

# To stop:
docker compose down
```

**Default Login Credentials:**
- Admin: `admin@aims.com` / `admin123`
- Learner: `learner@aims.com` / `learner123`

### Running Locally

#### Detailed Setup - Local Development

```bash
# 1. Start PostgreSQL in Docker
docker compose up -d postgres

# 2. Wait for PostgreSQL to be ready (check logs)
docker compose logs -f postgres
# Wait for "database system is ready to accept connections"

# 3. Initialize database with sample data
uv run python scripts/init_database.py

# 4. Set your OpenAI API key (if not in .env)
export OPENAI_API_KEY="your-api-key-here"

# 5. Run the FastAPI application locally
uv run uvicorn app.main:app --reload
```

**Access the application:**
- **Frontend Interface**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

#### Detailed Setup - Full Docker

```bash
# 1. Build and start all services
docker compose up --build

# 2. In another terminal, initialize database (one-time)
docker compose exec web uv run python scripts/init_database.py

# 3. View logs
docker compose logs -f

# 4. Stop services
docker compose down

# 5. Remove all data and start fresh
docker compose down -v
```

**Note**: When using Docker Compose, environment variables are read from the `.env` file automatically.

### Testing the Application

**For Local Development:**
1. **Login** at http://localhost:8000/login with `learner@aims.com` / `learner123`
2. **Browse** available courses on the dashboard
3. **Select** "Python Object-Oriented Programming" course
4. **Start** the "Python OOP Fundamentals" lesson
5. **Answer** AI-generated questions in the chat interface
6. **Experience** adaptive learning as the system:
   - Rephrases questions if you need clarification
   - Re-teaches concepts if you're struggling
   - Advances when you demonstrate mastery (80%+)
7. **Complete** all 6 learning outcomes

**For Content Management:**
1. **Login** as Content Manager or Admin
2. **Navigate** to Content Management from the dashboard
3. **Create courses** with AI-suggested lesson structures
4. **Define learning outcomes** with key concepts (comma-separated)
5. **Add content chunks** (definitions, explanations, examples, procedures)
6. **Generate AI content** for individual outcomes or entire courses in bulk
7. **Reorder content** chunks using drag-and-drop or arrow controls
8. **Preview and edit** all content before publishing

**For Admin Features:**
1. **Login** at http://localhost:8000/admin with `admin@aims.com` / `admin123`
2. **Manage** users, courses, lessons, and assessment sessions
3. **View** raw database records and relationships

See [SETUP.md](SETUP.md) for detailed usage documentation.

## 📊 Example Assessment Session

```python
# Via the web interface:
# 1. Admin creates course and lesson with learning outcomes
# 2. Learner starts assessment
# 3. System generates questions and evaluates answers
# 4. Progress tracked in PostgreSQL database

# Programmatic example (for developers):
from app.services.assessment import AssessmentService
from app.database import Session, engine

with Session(engine) as session:
    service = AssessmentService(session)
    
    # Start assessment for a session
    result = service.start_assessment(assessment_id=1)
    
    # Process an answer
    result = service.process_answer(
        assessment_id=1,
        answer="A class is a blueprint for creating objects..."
    )
    
    # Returns feedback, score, and next question
```

## 🌟 Key Features (v2.0)

- **🎯 Mastery-Based Learning**: Focus on understanding, not completion
- **� Concept-Level Tracking**: Individual tracking and visualization of key concepts within each learning outcome
- **🤖 AI-Powered Assessment**: Dynamic question generation and evaluation with concept awareness
- **🔄 Adaptive Remediation**: Intelligent reteaching based on student needs and missing concepts
- **📈 Progress Tracking**: Real-time mastery level monitoring per outcome with concept breakdowns
- **🎨 Personalized Experience**: Each assessment journey is unique and adapts to concept gaps
- **⚡ Real-time Feedback**: Immediate evaluation and guidance via HTMX with concept progress display
- **👥 Multi-User Support**: Admin, Content Manager, and Learner roles with authentication
- **🏗️ Content Management Dashboard**: Comprehensive CRUD interface for courses, lessons, outcomes, and content chunks
  - Create and edit courses with AI-powered structure suggestions
  - Define learning outcomes with key concepts
  - Add content chunks (definitions, explanations, examples, procedures)
  - Bulk AI content generation for entire courses
  - Reorder and manage content hierarchically
- **🎤 Voice Input**: Faster-whisper integration for speech-to-text answers (local, CPU-based)
- **💾 Full Persistence**: Complete conversation history, concept coverage, and graph state in PostgreSQL
- **🔄 Session Continuity**: LangGraph PostgresSaver ensures seamless state recovery across sessions
- **📊 Admin Dashboard**: Web-based content management with SQLAdmin

## 🛠️ Technology Stack

**Backend:**
- FastAPI - Modern Python web framework
- PostgreSQL - Relational database
- SQLModel - Pydantic-based ORM
- SQLAdmin - Admin interface
- LangGraph - AI workflow orchestration
- OpenAI GPT-4 - Language model

**Frontend:**
- Jinja2 - Template engine
- HTMX - Dynamic HTML updates
- Alpine.js - Reactive components
- Custom CSS - Modern, responsive design

**DevOps:**
- Docker & Docker Compose - Containerization
- uv - Fast Python package manager

## 🔮 Future Enhancements

- **Learning Analytics Dashboard**: Visualize mastery progression, time-to-mastery, and concept coverage patterns
- **Multi-modal Assessment**: Support for images, diagrams, and code snippets in questions and answers
- **Collaborative Learning**: Peer assessment and study group features
- **Enhanced Voice Input**: Multi-language support and custom vocabulary
- **Integration APIs**: LMS connectors (Canvas, Moodle, Blackboard)
- **Email Verification**: Secure user registration and password reset
- **Export Functionality**: Download assessment transcripts, certificates, and learning analytics
- **Real-time Updates**: WebSocket support for live progress in group settings
- **Mobile Apps**: Native iOS and Android applications
- **Offline Mode**: Continue assessments without internet connection

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Comprehensive setup and usage guide
- **[MIGRATION.md](MIGRATION.md)** - Migration guide from v1 to v2
- **[BUILD_SUMMARY.md](BUILD_SUMMARY.md)** - Complete build documentation
- **[DEV_QUICK_REF.md](DEV_QUICK_REF.md)** - Developer quick reference

## 🤝 Contributing & Usage

**Usage Policy**: This repository is public for educational and demonstration purposes. If you're interested in using, adapting, or building upon this code, please contact me first at [alberts.johann@gmail.com] or open an issue to discuss your intended use case.

**Contributing**: We welcome discussions and feedback! Please feel free to:
- Open issues for questions or suggestions
- Submit bug reports
- Propose feature ideas

For code contributions, please contact me first to discuss the proposed changes.

## 📄 License & Usage

**Copyright (c) 2025 Johann Alberts. All rights reserved.**

This code is made publicly available for educational and demonstration purposes. While you can view and study the code, any use, reproduction, modification, or distribution requires prior written permission from the author.

**Want to use this code?** Please contact me at [alberts.johann@gmail.com] or open an issue to discuss your use case. I'm happy to consider licensing arrangements for legitimate educational or commercial purposes.

## 🙋‍♂️ Support

For questions or support, please open an issue or contact the development team.

---

**AIMS: Where every student achieves true mastery, one outcome at a time.**