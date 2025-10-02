# AIMS Quick Reference Card

## 🚀 One-Command Start

```bash
bash scripts/start_aims.sh
```

Then open http://localhost:8000

## 📝 Manual Start (Step by Step)

```bash
# 1. Set API key
export OPENAI_API_KEY="your-key"

# 2. Start MongoDB
docker compose up -d mongodb

# 3. Initialize data (first time only)
uv run python fixtures/init_lesson_data.py

# 4. Start server
uv run uvicorn app.main:app --reload

# 5. Open browser: http://localhost:8000
```

## 🔗 Important URLs

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **MongoDB** | mongodb://localhost:27017 |

## 📂 Project Structure

```
aims/
├── app/
│   ├── main.py              # FastAPI backend + API endpoints
│   └── services/
│       └── graph.py         # AIMS adaptive assessment logic
├── static/
│   ├── index.html           # Frontend interface
│   ├── style.css            # Styling
│   ├── app.js               # Frontend logic
│   └── SETUP.md             # Frontend docs
├── fixtures/
│   ├── init_lesson_data.py  # Database initialization
│   └── README.md            # Test lesson info
└── scripts/
    ├── start_aims.sh        # Quick start script
    └── verify_frontend_setup.py  # Setup checker
```

## 🎯 API Endpoints

### Core Endpoints
- `GET /api/lessons` - List all lessons
- `POST /api/assessment/start` - Start new assessment
- `POST /api/assessment/submit` - Submit answer
- `POST /api/assessment/next` - Continue to next question

### Example API Call
```bash
# Get lessons
curl http://localhost:8000/api/lessons

# Start assessment (replace with actual lesson ID)
curl -X POST http://localhost:8000/api/assessment/start \
  -H "Content-Type: application/json" \
  -d '{"lesson_id": "64f1a2b3c4d5e6f789012345"}'
```

## 🧪 Test Lesson: Python OOP

**6 Learning Outcomes:**
1. Class Definition
2. Object Instantiation
3. Inheritance Concepts
4. Encapsulation Principles
5. Polymorphism Application
6. Special Methods

**Mastery Threshold:** 80% per outcome

## 🎨 Frontend Features

- ✅ Lesson selection dropdown
- ✅ Real-time progress bar
- ✅ AI-generated questions
- ✅ Answer text area
- ✅ Adaptive feedback (color-coded)
- ✅ Learning outcomes list
- ✅ Completion screen
- ✅ Keyboard shortcut: Ctrl+Enter to submit

## 🔧 Useful Commands

### Database
```bash
# Reset database
docker compose down -v
docker compose up -d mongodb
uv run python fixtures/init_lesson_data.py
```

### Development
```bash
# Verify setup
uv run python scripts/verify_frontend_setup.py

# View logs
docker compose logs -f mongodb

# Check MongoDB data
docker exec -it aims_mongodb mongosh aims_db
```

### Docker
```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View running containers
docker ps

# Clean everything
docker compose down -v
```

## 🐛 Debugging

### Check Services
```bash
# Is MongoDB running?
docker ps | grep mongodb

# Is backend running?
curl http://localhost:8000/api/lessons

# Check API key
echo $OPENAI_API_KEY
```

### Browser Console
```javascript
// View current assessment state
window.AIMSApp.getState()

// View session info
window.AIMSApp.getSession()

// View available lessons
window.AIMSApp.getLessons()
```

### Common Issues

**"Failed to fetch lessons"**
→ MongoDB not running or no data loaded

**"Failed to start assessment"**
→ OpenAI API key not set or invalid

**"Connection refused"**
→ Backend not running on port 8000

## 📊 Assessment Flow

```
Select Lesson
    ↓
Start Assessment
    ↓
Receive AI Question
    ↓
Type Answer
    ↓
Submit (Ctrl+Enter)
    ↓
Get Feedback:
  • Mastery (80%+) → Next Outcome
  • Partial → Rephrased Question
  • Struggling → Re-teaching
    ↓
Continue Until All Outcomes Mastered
    ↓
Completion Screen! 🎉
```

## 🎓 Learning Outcomes (Graph Flow)

```
choose_outcome
    ↓
generate_question
    ↓
assess_answer
    ↓
Routing:
├─→ mastery_achieved (≥80%) → provide_feedback → next outcome
├─→ rephrase_needed (<80%, attempts<2) → rephrase_question
└─→ reteach_needed (<80%, attempts≥2) → re_teach_concept
```

## 📚 Documentation

- **Main README**: `/README.md`
- **Frontend Setup**: `/static/SETUP.md`
- **Implementation Summary**: `/FRONTEND_SUMMARY.md`
- **Test Lesson Info**: `/fixtures/README.md`
- **This Card**: `/QUICK_REFERENCE.md`

## 💡 Tips

1. **Test with real answers** - The AI evaluates understanding, not keywords
2. **Try edge cases** - Give incomplete answers to see rephrasing
3. **Watch the graph** - Check server logs to see routing decisions
4. **Use dev tools** - Browser console shows API calls
5. **Iterate on prompts** - Modify `app/services/graph.py` for better questions

## 🎉 You're Ready!

Everything is set up. Just run:
```bash
bash scripts/start_aims.sh
```

And start experiencing adaptive, mastery-based assessment!

---
**AIMS: Where every student achieves true mastery, one outcome at a time.**