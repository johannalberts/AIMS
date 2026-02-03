# AIMS Frontend Setup Guide

## 🎯 Quick Start

### 1. Start MongoDB and Initialize Data

```bash
# Start MongoDB
docker compose up -d mongodb

# Wait a few seconds for MongoDB to start, then initialize with test data
uv run python fixtures/init_lesson_data.py
```

### 2. Start the FastAPI Backend

```bash
# Set your OpenAI API key (required for AI assessment)
export OPENAI_API_KEY="your-openai-api-key-here"

# Start the backend
uv run uvicorn app.main:app --reload
```

### 3. Access the Frontend

Open your browser and navigate to:
```
http://localhost:8000
```

That's it! You should see the AIMS interface.

## 📁 Frontend Structure

```
static/
├── index.html    # Main HTML structure
├── style.css     # Styling and layout
└── app.js        # Frontend logic and API communication
```

## 🔌 API Endpoints

The frontend communicates with these backend endpoints:

- `GET /api/lessons` - Fetch all available lessons
- `POST /api/assessment/start` - Start a new assessment session
- `POST /api/assessment/submit` - Submit an answer
- `POST /api/assessment/next` - Continue to next question
- `GET /api/session/{id}` - Get session state

## 🧪 Testing the Application

### Test Flow:

1. **Select Lesson**: Choose "Python Object-Oriented Programming Fundamentals"
2. **Start Assessment**: Click "Start Assessment"
3. **Answer Questions**: 
   - Read the AI-generated question
   - Type your answer in the text area
   - Click "Submit Answer"
4. **Receive Feedback**:
   - If correct (80%+ mastery): Move to next outcome
   - If partial: Question is rephrased with hints
   - If struggling: Concept is re-taught
5. **Complete Assessment**: When all 6 outcomes are mastered

### Keyboard Shortcuts:
- `Ctrl/Cmd + Enter` in answer field = Submit answer

## 🎨 UI Features

### Progress Tracking
- Visual progress bar showing overall completion
- Individual mastery levels for each learning outcome
- Current outcome highlighted

### Adaptive Feedback
- Success feedback (green) - Mastery achieved
- Warning feedback (yellow) - Rephrasing needed
- Reteach feedback (red) - Concept explanation provided

### Learning Outcomes List
- Shows all 6 Python OOP outcomes
- Current outcome marked with arrow (→)
- Mastered outcomes marked with checkmark (✓)
- Real-time mastery percentage

## 🐛 Debugging

### Check Backend Status:
```bash
# View API docs
http://localhost:8000/docs

# Test API directly
curl http://localhost:8000/api/lessons
```

### Browser Console:
Open browser dev tools (F12) to see:
- API requests and responses
- JavaScript errors
- Application state

Access debug info in console:
```javascript
// Get current state
window.AIMSApp.getState()

// Get session info
window.AIMSApp.getSession()

// Get available lessons
window.AIMSApp.getLessons()
```

### Common Issues:

**"Failed to fetch lessons"**
- Make sure MongoDB is running: `docker ps | grep mongodb`
- Check if data is initialized: `uv run python fixtures/init_lesson_data.py`

**"Failed to start assessment"**
- Ensure OpenAI API key is set
- Check backend logs for errors

**Questions not generating**
- Verify OpenAI API key is valid
- Check API quota/billing

## 🚀 Future Improvements

When you're ready to enhance the frontend:

1. **Add Authentication**: User login and session management
2. **Progress Persistence**: Save state to database
3. **Analytics Dashboard**: Visualize learning progress
4. **Multiple Students**: Support multiple concurrent users
5. **Responsive Design**: Better mobile experience
6. **Real-time Updates**: WebSocket for live feedback
7. **Rich Text**: Markdown support for questions/answers
8. **Code Editor**: Syntax highlighting for programming questions

## 📝 Development Notes

### Why Vanilla JS?
- No build process needed
- Easy to debug and modify
- Direct learning of fundamentals
- Can easily migrate to React/Vue later

### Current Limitations:
- In-memory session storage (resets on server restart)
- No user authentication
- Single student at a time
- Basic UI styling

These are intentional for simplicity and easy testing. You can enhance these later!

## 🔧 Customization

### Change Colors:
Edit CSS variables in `style.css`:
```css
:root {
    --primary-color: #2563eb;  /* Change this */
    --success-color: #10b981;  /* And this */
    /* etc... */
}
```

### Modify API URL:
Edit `app.js`:
```javascript
const API_BASE_URL = 'http://localhost:8000/api';
```

### Adjust Assessment Logic:
Modify the AIMS graph in `app/services/graph.py`

---

**Happy Testing! 🎉**

Your AIMS system is ready to demonstrate adaptive, mastery-based assessment!