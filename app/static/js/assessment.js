/**
 * Alpine.js component for assessment chat interface
 * Handles scroll behavior and initialization
 */
function assessmentApp() {
    return {
        init() {
            this.scrollToBottom();
        },
        scrollToBottom() {
            const container = document.getElementById('chatMessages');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }
    }
}

/**
 * Update progress bars dynamically based on API response
 * @param {string} responseText - JSON string containing progress data
 */
function updateProgress(responseText) {
    console.log('[Progress Update] Called with response:', responseText);
    try {
        const data = JSON.parse(responseText);
        console.log('[Progress Update] Parsed data:', data);
        data.progress.forEach(p => {
            console.log(`[Progress Update] Processing outcome ${p.outcome_id}: ${p.mastery_level}`);
            const outcomeItem = document.querySelector(`[data-outcome-id="${p.outcome_id}"]`);
            if (outcomeItem) {
                const progressBar = outcomeItem.querySelector('.progress-fill');
                const masteryText = outcomeItem.querySelector('.outcome-mastery');
                const mastery = Math.round(p.mastery_level * 100);
                
                console.log(`[Progress Update] Updating outcome ${p.outcome_id} to ${mastery}%`);
                
                if (progressBar) {
                    progressBar.style.width = `${mastery}%`;
                }
                if (masteryText) {
                    masteryText.textContent = `${mastery}% Mastery`;
                }
                
                // Add mastered class if applicable
                if (p.is_mastered) {
                    outcomeItem.classList.add('mastered');
                } else {
                    outcomeItem.classList.remove('mastered');
                }
            } else {
                console.log(`[Progress Update] Could not find outcome item for ID ${p.outcome_id}`);
            }
        });
    } catch (e) {
        console.error('[Progress Update] Failed to update progress:', e);
    }
}

/**
 * Initialize HTMX event handlers for progress updates and auto-scroll
 */
function initAssessmentHandlers() {
    // Trigger progress update after form submission
    document.body.addEventListener('htmx:afterRequest', function(event) {
        // Check if this was the answer submission
        if (event.detail.pathInfo.requestPath.includes('/answer')) {
            console.log('[HTMX] Answer submitted, triggering progress update');
            // Fetch and update progress
            const sessionId = window.location.pathname.split('/').pop();
            fetch(`/api/progress/${sessionId}`)
                .then(response => response.json())
                .then(data => {
                    console.log('[Progress Fetch] Got progress data:', data);
                    updateProgress(JSON.stringify(data));
                })
                .catch(err => console.error('[Progress Fetch] Error:', err));
        }
    });

    // Auto-scroll on new messages
    document.body.addEventListener('htmx:afterSwap', function(event) {
        const container = document.getElementById('chatMessages');
        if (container) {
            setTimeout(() => {
                container.scrollTop = container.scrollHeight;
            }, 100);
        }
    });
}

// Initialize handlers when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAssessmentHandlers);
} else {
    initAssessmentHandlers();
}
