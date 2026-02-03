# AIMS: Adaptive Intelligent Mastery System

## Overview

AIMS (Adaptive Intelligent Mastery System) is a revolutionary educational assessment platform that moves beyond traditional static testing to create personalized, mastery-based learning experiences. Instead of asking predetermined questions, AIMS adapts to each student's understanding and dynamically generates assessments that ensure true comprehension of learning outcomes.

## 🎯 Core Concept

Traditional assessments rely on static questions that may not capture a student's actual understanding. AIMS takes a fundamentally different approach:

- **Mastery-Focused**: Each learning outcome must reach a specified mastery threshold (80%+) before moving on
- **Adaptive Questioning**: Questions are generated in real-time based on the student's current understanding
- **Intelligent Remediation**: When students struggle, the system rephrases questions or provides targeted re-teaching
- **Continuous Assessment**: No more one-and-done tests - students work until they demonstrate true mastery

## 🧠 How It Works

AIMS uses a sophisticated graph-based workflow powered by LangGraph and large language models to create an intelligent tutoring system:

### Assessment Flow

1. **Outcome Selection**: The system identifies learning outcomes that haven't reached mastery
2. **Dynamic Question Generation**: AI generates questions tailored to test specific learning outcomes
3. **Intelligent Assessment**: Student responses are evaluated for understanding, not just correctness
4. **Adaptive Response**:
   - ✅ **Mastery Achieved**: Positive feedback and move to next outcome
   - 🔄 **Needs Clarification**: Rephrase question with hints
   - 📚 **Needs Re-teaching**: Provide targeted explanation and retry

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
├── database.py          # PostgreSQL connection
├── auth.py              # Authentication & authorization
├── services/
│   ├── assessment.py    # Assessment logic & persistence
│   └── graph.py         # LangGraph AI workflow
├── templates/           # Jinja2 HTML templates
└── static/             # CSS and JavaScript
```

### Assessment Graph Nodes

- **choose_outcome**: Selects next learning outcome to assess
- **generate_question**: Creates tailored questions using AI
- **assess_answer**: Evaluates student responses for mastery
- **rephrase_question**: Provides hints and clarification
- **re_teach_concept**: Delivers targeted remediation
- **provide_feedback**: Celebrates mastery achievement

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

**For Admin Features:**
1. **Login** at http://localhost:8000/admin with `admin@aims.com` / `admin123`
2. **Create** new courses, lessons, and learning outcomes
3. **Manage** users and view assessment sessions

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
- **🤖 AI-Powered Assessment**: Dynamic question generation and evaluation
- **🔄 Adaptive Remediation**: Intelligent reteaching based on student needs
- **📈 Progress Tracking**: Real-time mastery level monitoring per outcome
- **🎨 Personalized Experience**: Each assessment journey is unique
- **⚡ Real-time Feedback**: Immediate evaluation and guidance via HTMX
- **👥 Multi-User Support**: Admin and learner roles with authentication
- **🏗️ Course Management**: Organize content hierarchically
- **💾 Full Persistence**: Complete conversation history in database
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

- **Learning Analytics Dashboard**: Visualize mastery progression and time-to-mastery
- **Multi-modal Assessment**: Support for images, diagrams, and code snippets
- **Collaborative Learning**: Peer assessment integration
- **Adaptive Content**: Dynamic lesson content based on mastery gaps
- **Integration APIs**: LMS and educational platform connectors
- **Email Verification**: Secure user registration
- **Export Functionality**: Download assessment transcripts and certificates
- **Real-time Updates**: WebSocket support for live progress

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