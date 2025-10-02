// AIMS Frontend Application
// API Configuration
const API_BASE_URL = 'http://localhost:8000/api';

// Application State
let currentSession = null;
let currentLessons = [];
let assessmentState = null;

// DOM Elements
const lessonSelect = document.getElementById('lessonSelect');
const startBtn = document.getElementById('startBtn');
const lessonSelection = document.getElementById('lessonSelection');
const assessmentSection = document.getElementById('assessmentSection');
const completionSection = document.getElementById('completionSection');
const questionContent = document.getElementById('questionContent');
const answerInput = document.getElementById('answerInput');
const submitBtn = document.getElementById('submitBtn');
const nextBtn = document.getElementById('nextBtn');
const feedbackCard = document.getElementById('feedbackCard');
const feedbackContent = document.getElementById('feedbackContent');
const currentOutcome = document.getElementById('currentOutcome');
const masteryLevel = document.getElementById('masteryLevel');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const outcomesList = document.getElementById('outcomesList');
const loadingOverlay = document.getElementById('loadingOverlay');
const restartBtn = document.getElementById('restartBtn');

// Utility Functions
function showLoading() {
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function showError(message) {
    // Create a more detailed error display
    const errorDetails = typeof message === 'object' ? JSON.stringify(message, null, 2) : message;
    
    // Log to console for debugging
    console.error('AIMS Error:', errorDetails);
    
    // Show user-friendly alert
    alert(`Error: ${errorDetails}`);
    hideLoading();
}

function formatPercentage(value) {
    return `${Math.round(value * 100)}%`;
}

// API Functions
async function fetchLessons() {
    try {
        showLoading();
        console.log('Fetching lessons from:', `${API_BASE_URL}/lessons`);
        
        const response = await fetch(`${API_BASE_URL}/lessons`);
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch lessons' }));
            throw new Error(errorData.detail || 'Failed to fetch lessons');
        }
        
        const lessons = await response.json();
        console.log('Lessons loaded:', lessons.length);
        
        currentLessons = lessons;
        populateLessonSelect(lessons);
        hideLoading();
    } catch (error) {
        console.error('Error fetching lessons:', error);
        showError(error.message);
    }
}

async function startAssessment(lessonId) {
    try {
        showLoading();
        console.log('Starting assessment for lesson:', lessonId);
        
        const response = await fetch(`${API_BASE_URL}/assessment/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lesson_id: lessonId })
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to start assessment' }));
            console.error('Error response:', errorData);
            throw new Error(errorData.detail || 'Failed to start assessment');
        }
        
        const data = await response.json();
        console.log('Assessment started:', data);
        
        currentSession = data;
        assessmentState = data.session_state;
        
        // Switch to assessment view
        lessonSelection.style.display = 'none';
        assessmentSection.style.display = 'block';
        
        updateAssessmentUI();
        hideLoading();
    } catch (error) {
        console.error('Error starting assessment:', error);
        showError(error.message);
    }
}

async function submitAnswer(answer) {
    try {
        showLoading();
        console.log('Submitting answer for session:', currentSession.session_id);
        console.log('Answer length:', answer.length);
        
        const response = await fetch(`${API_BASE_URL}/assessment/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession.session_id,
                answer: answer
            })
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to submit answer' }));
            console.error('Error response:', errorData);
            throw new Error(errorData.detail || 'Failed to submit answer');
        }
        
        const data = await response.json();
        console.log('Answer submitted:', data);
        
        assessmentState = data.session_state;
        
        // Show feedback
        displayFeedback(data);
        
        // Check if completed
        if (data.status === 'completed') {
            setTimeout(() => showCompletion(data), 2000);
        } else {
            // Enable next button
            submitBtn.style.display = 'none';
            nextBtn.style.display = 'inline-block';
        }
        
        updateProgress();
        updateOutcomesList();
        hideLoading();
    } catch (error) {
        console.error('Error submitting answer:', error);
        showError(error.message);
    }
}

async function continueToNext() {
    try {
        showLoading();
        console.log('Continuing to next question for session:', currentSession.session_id);
        
        const response = await fetch(`${API_BASE_URL}/assessment/next`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession.session_id
            })
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to continue' }));
            console.error('Error response:', errorData);
            throw new Error(errorData.detail || 'Failed to continue');
        }
        
        const data = await response.json();
        console.log('Next question loaded:', data);
        
        assessmentState = data.session_state;
        
        // Reset UI for next question
        answerInput.value = '';
        feedbackCard.style.display = 'none';
        submitBtn.style.display = 'inline-block';
        nextBtn.style.display = 'none';
        
        updateAssessmentUI();
        hideLoading();
    } catch (error) {
        console.error('Error continuing:', error);
        showError(error.message);
    }
}

// UI Update Functions
function populateLessonSelect(lessons) {
    lessonSelect.innerHTML = '<option value="">-- Choose a lesson --</option>';
    lessons.forEach(lesson => {
        const option = document.createElement('option');
        option.value = lesson._id || lesson.id;
        option.textContent = `${lesson.title} (${lesson.topic})`;
        lessonSelect.appendChild(option);
    });
}

function updateAssessmentUI() {
    if (!assessmentState) return;
    
    // Update current outcome
    const currentOutcomeKey = assessmentState.current_outcome_key;
    if (currentOutcomeKey && currentOutcomeKey !== 'all_mastered') {
        const outcome = assessmentState.learning_outcomes[currentOutcomeKey];
        currentOutcome.textContent = outcome.description;
        masteryLevel.textContent = formatPercentage(outcome.mastery_level);
    }
    
    // Update question
    if (assessmentState.last_question) {
        questionContent.innerHTML = `<p>${assessmentState.last_question}</p>`;
    }
    
    updateProgress();
    updateOutcomesList();
}

function updateProgress() {
    if (!assessmentState) return;
    
    const outcomes = assessmentState.learning_outcomes;
    const total = Object.keys(outcomes).length;
    const mastered = Object.values(outcomes).filter(o => o.mastery_level >= 0.8).length;
    const percentage = (mastered / total) * 100;
    
    progressFill.style.width = `${percentage}%`;
    progressText.textContent = `${mastered} of ${total} outcomes mastered (${Math.round(percentage)}%)`;
}

function updateOutcomesList() {
    if (!assessmentState) return;
    
    outcomesList.innerHTML = '';
    const currentKey = assessmentState.current_outcome_key;
    
    Object.entries(assessmentState.learning_outcomes).forEach(([key, outcome]) => {
        const item = document.createElement('div');
        item.className = 'outcome-item';
        
        const isCurrent = key === currentKey;
        const isMastered = outcome.mastery_level >= 0.8;
        
        if (isCurrent) item.classList.add('current');
        if (isMastered) item.classList.add('mastered');
        
        const status = document.createElement('div');
        status.className = 'outcome-status';
        status.textContent = isMastered ? '✓' : isCurrent ? '→' : '';
        
        const name = document.createElement('div');
        name.className = 'outcome-name';
        name.textContent = formatOutcomeName(key);
        
        const mastery = document.createElement('div');
        mastery.className = 'outcome-mastery';
        mastery.textContent = formatPercentage(outcome.mastery_level);
        
        item.appendChild(status);
        item.appendChild(name);
        item.appendChild(mastery);
        outcomesList.appendChild(item);
    });
}

function displayFeedback(data) {
    feedbackCard.style.display = 'block';
    feedbackContent.textContent = assessmentState.feedback || 'Processing your response...';
    
    // Style based on feedback type
    feedbackCard.className = 'card feedback-card';
    
    const currentOutcome = assessmentState.learning_outcomes[assessmentState.current_outcome_key];
    if (currentOutcome && currentOutcome.mastery_level >= 0.8) {
        feedbackCard.classList.add('success');
    } else if (assessmentState.failed_attempts >= 2) {
        feedbackCard.classList.add('reteach');
    } else {
        feedbackCard.classList.add('warning');
    }
    
    // Scroll to feedback
    feedbackCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showCompletion(data) {
    assessmentSection.style.display = 'none';
    completionSection.style.display = 'block';
    
    // Show completion stats
    const stats = document.getElementById('completionStats');
    const outcomes = assessmentState.learning_outcomes;
    const totalOutcomes = Object.keys(outcomes).length;
    
    stats.innerHTML = `
        <div class="stat-item">✅ <strong>${totalOutcomes}</strong> learning outcomes mastered</div>
        <div class="stat-item">📚 Topic: <strong>${assessmentState.topic}</strong></div>
        <div class="stat-item">🎯 Mastery threshold achieved: <strong>80%+</strong></div>
    `;
}

function formatOutcomeName(key) {
    return key
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Event Listeners
lessonSelect.addEventListener('change', (e) => {
    startBtn.disabled = !e.target.value;
});

startBtn.addEventListener('click', () => {
    const lessonId = lessonSelect.value;
    if (lessonId) {
        startAssessment(lessonId);
    }
});

submitBtn.addEventListener('click', () => {
    const answer = answerInput.value.trim();
    if (!answer) {
        alert('Please provide an answer before submitting.');
        return;
    }
    submitAnswer(answer);
});

nextBtn.addEventListener('click', () => {
    continueToNext();
});

restartBtn.addEventListener('click', () => {
    // Reset everything
    currentSession = null;
    assessmentState = null;
    answerInput.value = '';
    
    // Show lesson selection
    completionSection.style.display = 'none';
    lessonSelection.style.display = 'block';
    
    // Reload lessons
    fetchLessons();
});

// Keyboard shortcuts
answerInput.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        submitBtn.click();
    }
});

// Initialize the application
window.addEventListener('DOMContentLoaded', () => {
    console.log('AIMS Frontend initialized');
    fetchLessons();
});

// Export for debugging
window.AIMSApp = {
    getState: () => assessmentState,
    getSession: () => currentSession,
    getLessons: () => currentLessons
};