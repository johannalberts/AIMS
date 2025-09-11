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
- Docker (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/johannalberts/AIMS.git
cd aims

# Install dependencies using uv
uv add fastapi uvicorn langgraph langchain-openai

# Set environment variables
export OPENAI_API_KEY="your-api-key-here"
```

### Running Locally

#### Option 1: Using uv directly (Recommended for development)

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Run the application
uv run uvicorn app.main:app --reload
```

#### Option 2: Using Docker Compose

```bash
# Build and run the application
docker-compose up --build

# For subsequent runs (no rebuild needed)
docker-compose up

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

**Note**: When using Docker, you can set environment variables in a `.env` file:
```bash
# Create .env file
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

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

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines and feel free to submit issues or pull requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙋‍♂️ Support

For questions or support, please open an issue or contact the development team.

---

**AIMS: Where every student achieves true mastery, one outcome at a time.**