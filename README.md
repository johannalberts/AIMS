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
- **LangGraph Integration**: Orchestrates the adaptive assessment workflow
- **OpenAI Integration**: Powers intelligent question generation and assessment
- **State Persistence**: Tracks learning progress and mastery levels

### Key Components

```
app/
├── main.py              # FastAPI application entry point
└── services/
    └── graph.py         # LangGraph implementation for assessment logic
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

- Python 3.12+
- OpenAI API key
- Docker (optional, recommended for MongoDB)
- uv package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/johannalberts/AIMS.git
cd aims

# Create .env file from example
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=your-actual-key-here

# Dependencies are managed by uv - they'll be installed automatically
```

### Quick Start (Full Stack with Frontend)

```bash
# 1. Create .env file with your OpenAI API key
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=your-actual-key-here

# 2. Start MongoDB and initialize test data
docker compose up -d mongodb
sleep 5  # Wait for MongoDB to start
uv run python fixtures/init_lesson_data.py

# 3. Start the FastAPI backend (serves frontend automatically)
uv run uvicorn app.main:app --reload

# 4. Open your browser
# Navigate to: http://localhost:8000
```

You'll see the AIMS assessment interface with the Python OOP test lesson ready to go!

### Running Locally

#### Option 1: Full Stack with Frontend (Recommended)

```bash
# Start MongoDB
docker compose up -d mongodb

# Initialize database with Python OOP lesson
uv run python fixtures/init_lesson_data.py

# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Run the application (backend + frontend)
uv run uvicorn app.main:app --reload
```

**Access the application:**
- **Frontend Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

#### Option 2: Backend Only (API Testing)

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Run just the API
uv run uvicorn app.main:app --reload
```

#### Option 3: Using Docker Compose (Everything)

```bash
# Build and run the application
docker compose up --build

# For subsequent runs (no rebuild needed)
docker compose up

# Run in detached mode
docker compose up -d

# View logs
docker compose logs -f

# Stop the application
docker compose down
```

**Note**: When using Docker, you can set environment variables in a `.env` file:
```bash
# Create .env file
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

The API will be available at `http://localhost:8000`

### Testing the Frontend

1. **Open** http://localhost:8000 in your browser
2. **Select** "Python Object-Oriented Programming Fundamentals" lesson
3. **Click** "Start Assessment"
4. **Answer** the AI-generated questions
5. **Experience** adaptive learning as the system:
   - Rephrases questions if you need clarification
   - Re-teaches concepts if you're struggling
   - Advances when you demonstrate mastery (80%+)
6. **Complete** all 6 learning outcomes to finish

See `static/SETUP.md` for detailed frontend documentation.

## 📊 Example Assessment Session

```python
# Create learning outcomes for a lesson
html_outcomes = {
    "html_semantics": {
        "description": "Understanding HTML semantic elements and their proper usage",
        "mastery_level": 0.0
    },
    "html_structure": {
        "description": "Understanding HTML document structure and hierarchy", 
        "mastery_level": 0.0
    }
}

# Initialize assessment
initial_state = AIMSGraph.create_initial_state(
    topic="HTML Fundamentals",
    learning_outcomes=html_outcomes
)

# Start adaptive assessment
result = aims_graph.invoke(initial_state)
```

## 🌟 Key Features

- **🎯 Mastery-Based Learning**: Focus on understanding, not completion
- **🤖 AI-Powered Assessment**: Dynamic question generation and evaluation
- **🔄 Adaptive Remediation**: Intelligent reteaching based on student needs
- **📈 Progress Tracking**: Real-time mastery level monitoring
- **🎨 Personalized Experience**: Each assessment journey is unique
- **⚡ Real-time Feedback**: Immediate evaluation and guidance

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python)
- **AI Orchestration**: LangGraph
- **Language Models**: OpenAI GPT-4
- **Containerization**: Docker + uv package manager
- **Deployment**: Render/AWS compatible

## 🔮 Future Enhancements

- **Learning Analytics Dashboard**: Visualize mastery progression
- **Multi-modal Assessment**: Support for images, diagrams, and code
- **Collaborative Learning**: Peer assessment integration
- **Adaptive Content**: Dynamic lesson content based on mastery gaps
- **Integration APIs**: LMS and educational platform connectors

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