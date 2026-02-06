/**
 * Alpine.js component for content management interface
 * Manages courses, lessons, learning outcomes, and content chunks
 * Includes AI-powered content generation and CRUD operations
 */
function contentManager() {
    return {
        loading: true,
        courses: [],
        filteredCourses: [],
        searchTerm: '',
        modals: {
            upload: false,
            generate: false,
            edit: false,
            course: false,
            lesson: false,
            lessonAI: false,
            outcome: false,
            addChunk: false
        },
        uploadMethod: 'text',
        uploadData: {
            outcomeId: null,
            contentType: 'explanation',
            contentText: '',
            pdfFile: null
        },
        selectedOutcome: null,
        generatedContent: null,
        editData: {
            contentId: null,
            outcomeId: null,
            contentText: '',
            approvalStatus: 'approved'
        },
        newChunkData: {
            outcomeId: null,
            contentType: 'explanation',
            contentText: ''
        },
        courseData: {
            id: null,
            title: '',
            subject: '',
            description: '',
            difficulty_level: 'beginner'
        },
        lessonData: {
            id: null,
            course_id: null,
            title: '',
            topic: '',
            description: '',
            estimated_duration_minutes: 60,
            mastery_threshold: 0.8
        },
        outcomeData: {
            id: null,
            lesson_id: null,
            key: '',
            description: '',
            key_concepts: '',
            examples: ''
        },
        aiLessonData: {
            course_id: null,
            title: '',
            topic: '',
            description: ''
        },
        aiSuggestion: null,
        aiCoursePreview: null,
        aiCourseGenerating: false,
        bulkGenerating: false,
        bulkProgress: {
            total: 0,
            completed: 0,
            failed: 0,
            items: []
        },

        async init() {
            await this.loadData();
        },

        async loadData() {
            try {
                const response = await fetch('/api/content-management/all');
                const data = await response.json();
                console.log('Loaded data:', data); // DEBUG
                this.courses = data.courses.map(course => ({
                    ...course,
                    expanded: false,
                    lessons: course.lessons.map(lesson => ({
                        ...lesson,
                        expanded: false,
                        learning_outcomes: lesson.learning_outcomes.map(outcome => ({
                            ...outcome,
                            content_chunks: outcome.content_chunks || []
                        }))
                    }))
                }));
                this.filteredCourses = this.courses;
                this.loading = false;
            } catch (error) {
                console.error('Error loading data:', error);
                alert('Failed to load content');
            }
        },

        toggleCourse(idx) {
            this.filteredCourses[idx].expanded = !this.filteredCourses[idx].expanded;
        },

        toggleLesson(courseIdx, lessonIdx) {
            this.filteredCourses[courseIdx].lessons[lessonIdx].expanded = 
                !this.filteredCourses[courseIdx].lessons[lessonIdx].expanded;
        },

        expandAll() {
            this.filteredCourses.forEach((course, idx) => {
                this.filteredCourses[idx].expanded = true;
                course.lessons.forEach((lesson, lidx) => {
                    this.filteredCourses[idx].lessons[lidx].expanded = true;
                });
            });
        },

        collapseAll() {
            this.filteredCourses.forEach((course, idx) => {
                this.filteredCourses[idx].expanded = false;
                course.lessons.forEach((lesson, lidx) => {
                    this.filteredCourses[idx].lessons[lidx].expanded = false;
                });
            });
        },

        filterContent() {
            if (!this.searchTerm) {
                this.filteredCourses = this.courses;
                return;
            }
            const term = this.searchTerm.toLowerCase();
            // Create NEW objects with the SAME nested object references
            this.filteredCourses = this.courses.filter(course => 
                course.title.toLowerCase().includes(term) ||
                course.lessons.some(lesson => 
                    lesson.title.toLowerCase().includes(term) ||
                    lesson.learning_outcomes.some(outcome => 
                        outcome.key.toLowerCase().includes(term) ||
                        outcome.description.toLowerCase().includes(term)
                    )
                )
            );
        },

        openUploadModal(outcome) {
            this.selectedOutcome = outcome;
            this.uploadData.outcomeId = outcome.id;
            this.uploadData.contentText = '';
            this.modals.upload = true;
        },

        handlePdfSelect(event) {
            this.uploadData.pdfFile = event.target.files[0];
        },

        async submitUpload() {
            if (this.uploadMethod === 'text') {
                const formData = new FormData();
                formData.append('content_text', this.uploadData.contentText);
                formData.append('content_type', this.uploadData.contentType);

                try {
                    const response = await fetch(`/api/outcomes/${this.uploadData.outcomeId}/content`, {
                        method: 'POST',
                        body: formData
                    });
                    if (response.ok) {
                        this.modals.upload = false;
                        await this.loadData();
                        alert('Content uploaded successfully!');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Upload failed');
                }
            }
        },

        openGenerateModal(outcome) {
            this.selectedOutcome = outcome;
            this.generatedContent = null;
            this.modals.generate = true;
        },

        async generateContent() {
            try {
                const response = await fetch(`/api/outcomes/${this.selectedOutcome.id}/generate-content`, {
                    method: 'POST'
                });
                const data = await response.json();
                this.generatedContent = JSON.stringify(data.generated_content, null, 2);
            } catch (error) {
                console.error('Error:', error);
                alert('Generation failed');
            }
        },

        async saveGenerated() {
            try {
                const response = await fetch(`/api/outcomes/${this.selectedOutcome.id}/save-generated-content`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: this.generatedContent
                });
                if (response.ok) {
                    this.modals.generate = false;
                    await this.loadData();
                    alert('Content saved!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Save failed');
            }
        },

        // Add Content Chunk
        openAddChunkModal(outcome) {
            this.newChunkData = {
                outcomeId: outcome.id,
                contentType: 'explanation',
                contentText: ''
            };
            this.modals.addChunk = true;
        },

        async saveNewChunk() {
            if (!this.newChunkData.contentText) {
                alert('Please enter content');
                return;
            }

            const formData = new FormData();
            formData.append('outcome_id', this.newChunkData.outcomeId);
            formData.append('content_type', this.newChunkData.contentType);
            formData.append('content_text', this.newChunkData.contentText);

            try {
                const response = await fetch('/api/content', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    this.modals.addChunk = false;
                    await this.loadData();
                    alert('Content chunk added!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Save failed');
            }
        },

        async deleteContentChunk(contentId) {
            if (!confirm('Delete this content chunk?')) return;
            try {
                const response = await fetch(`/api/content/${contentId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadData();
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Delete failed');
            }
        },

        async moveChunkUp(outcomeId, chunkIdx) {
            await this.swapChunks(outcomeId, chunkIdx, chunkIdx - 1);
        },

        async moveChunkDown(outcomeId, chunkIdx) {
            await this.swapChunks(outcomeId, chunkIdx, chunkIdx + 1);
        },

        async swapChunks(outcomeId, idx1, idx2) {
            const outcome = this.findOutcomeById(outcomeId);
            if (!outcome) return;

            const chunks = outcome.content_chunks;
            const chunk1 = chunks[idx1];
            const chunk2 = chunks[idx2];

            try {
                // Update chunk orders on backend
                await fetch(`/api/content/${chunk1.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content_text: chunk1.content_text,
                        chunk_order: idx2,
                        approval_status: chunk1.approval_status
                    })
                });

                await fetch(`/api/content/${chunk2.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content_text: chunk2.content_text,
                        chunk_order: idx1,
                        approval_status: chunk2.approval_status
                    })
                });

                await this.loadData();
            } catch (error) {
                console.error('Error:', error);
                alert('Reorder failed');
            }
        },

        findOutcomeById(outcomeId) {
            for (const course of this.courses) {
                for (const lesson of course.lessons) {
                    const outcome = lesson.learning_outcomes.find(o => o.id === outcomeId);
                    if (outcome) return outcome;
                }
            }
            return null;
        },

        openEditModal(chunk, outcomeId) {
            this.editData = {
                contentId: chunk.id,
                outcomeId: outcomeId,
                contentText: chunk.content_text,
                approvalStatus: chunk.approval_status
            };
            this.modals.edit = true;
        },

        async saveEdit() {
            try {
                const response = await fetch(`/api/content/${this.editData.contentId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        content_text: this.editData.contentText,
                        approval_status: this.editData.approvalStatus
                    })
                });
                if (response.ok) {
                    this.modals.edit = false;
                    await this.loadData();
                    alert('Content updated!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Update failed');
            }
        },

        async deleteContent() {
            if (!confirm('Delete this content?')) return;
            try {
                const response = await fetch(`/api/content/${this.editData.contentId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    this.modals.edit = false;
                    await this.loadData();
                    alert('Content deleted!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Delete failed');
            }
        },

        // Course CRUD
        openCourseModal() {
            this.courseData = {
                id: null,
                title: '',
                subject: '',
                description: '',
                difficulty_level: 'beginner'
            };
            this.aiCoursePreview = null;
            this.aiCourseGenerating = false;
            this.modals.course = true;
        },

        openEditCourseModal(course) {
            this.courseData = {
                id: course.id,
                title: course.title,
                subject: course.subject,
                description: course.description || '',
                difficulty_level: course.difficulty_level || 'beginner'
            };
            this.modals.course = true;
        },

        async saveCourse() {
            const formData = new FormData();
            formData.append('title', this.courseData.title);
            formData.append('subject', this.courseData.subject);
            formData.append('description', this.courseData.description);
            formData.append('difficulty_level', this.courseData.difficulty_level);

            try {
                const url = this.courseData.id 
                    ? `/api/courses/${this.courseData.id}`
                    : '/api/courses';
                const method = this.courseData.id ? 'PUT' : 'POST';
                
                const response = await fetch(url, {
                    method: method,
                    body: formData
                });
                
                if (response.ok) {
                    this.modals.course = false;
                    await this.loadData();
                    alert(this.courseData.id ? 'Course updated!' : 'Course created!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Save failed');
            }
        },

        async deleteCourse(courseId) {
            if (!confirm('Delete this course? This will also delete all lessons and outcomes.')) return;
            try {
                const response = await fetch(`/api/courses/${courseId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadData();
                    alert('Course deleted!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Delete failed');
            }
        },

        async generateCourseStructure() {
            if (!this.courseData.title || !this.courseData.subject) {
                alert('Please enter course title and subject first');
                return;
            }

            this.aiCourseGenerating = true;

            try {
                const response = await fetch('/api/courses/suggest-structure', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: this.courseData.title,
                        subject: this.courseData.subject,
                        description: this.courseData.description,
                        difficulty_level: this.courseData.difficulty_level
                    })
                });

                if (response.ok) {
                    this.aiCoursePreview = await response.json();
                    this.aiCourseGenerating = false;
                } else {
                    throw new Error('Failed to generate course structure');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to generate course structure. Please try again.');
                this.aiCourseGenerating = false;
            }
        },

        removeLessonFromPreview(lessonIdx) {
            this.aiCoursePreview.suggestion.lessons.splice(lessonIdx, 1);
        },

        async saveAICourseStructure() {
            if (!this.aiCoursePreview) return;

            try {
                const response = await fetch('/api/courses/create-from-suggestion', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: this.courseData.title,
                        subject: this.courseData.subject,
                        description: this.courseData.description || this.aiCoursePreview.suggestion.course_overview,
                        difficulty_level: this.courseData.difficulty_level,
                        lessons: this.aiCoursePreview.suggestion.lessons
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    this.modals.course = false;
                    this.aiCoursePreview = null;
                    await this.loadData();
                    alert(`Course created with ${result.lessons.length} lessons!`);
                } else {
                    throw new Error('Failed to create course');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to save course. Please try again.');
            }
        },

        // Lesson CRUD
        openLessonModal(course) {
            this.lessonData = {
                id: null,
                course_id: course.id,
                title: '',
                topic: '',
                description: '',
                estimated_duration_minutes: 60,
                mastery_threshold: 0.8
            };
            this.modals.lesson = true;
        },

        openEditLessonModal(lesson) {
            this.lessonData = {
                id: lesson.id,
                course_id: lesson.course_id,
                title: lesson.title,
                topic: lesson.topic,
                description: lesson.description || '',
                estimated_duration_minutes: lesson.estimated_duration_minutes || 60,
                mastery_threshold: lesson.mastery_threshold || 0.8
            };
            this.modals.lesson = true;
        },

        async saveLesson() {
            const formData = new FormData();
            formData.append('title', this.lessonData.title);
            formData.append('topic', this.lessonData.topic);
            formData.append('description', this.lessonData.description);
            formData.append('estimated_duration_minutes', this.lessonData.estimated_duration_minutes);
            formData.append('mastery_threshold', this.lessonData.mastery_threshold);

            try {
                const url = this.lessonData.id 
                    ? `/api/lessons/${this.lessonData.id}`
                    : `/api/courses/${this.lessonData.course_id}/lessons`;
                const method = this.lessonData.id ? 'PUT' : 'POST';
                
                const response = await fetch(url, {
                    method: method,
                    body: formData
                });
                
                if (response.ok) {
                    this.modals.lesson = false;
                    await this.loadData();
                    alert(this.lessonData.id ? 'Lesson updated!' : 'Lesson created!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Save failed');
            }
        },

        async deleteLesson(lessonId) {
            if (!confirm('Delete this lesson? This will also delete all learning outcomes.')) return;
            try {
                const response = await fetch(`/api/lessons/${lessonId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadData();
                    alert('Lesson deleted!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Delete failed');
            }
        },

        // AI Lesson Suggestion
        openLessonAIModal(course) {
            this.aiLessonData = {
                course_id: course.id,
                title: '',
                topic: '',
                description: ''
            };
            this.aiSuggestion = null;
            this.modals.lessonAI = true;
        },

        async generateLessonSuggestion() {
            try {
                const response = await fetch('/api/lessons/suggest-structure', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        lesson_title: this.aiLessonData.title,
                        lesson_topic: this.aiLessonData.topic,
                        lesson_description: this.aiLessonData.description,
                        course_id: this.aiLessonData.course_id
                    })
                });
                
                if (response.ok) {
                    this.aiSuggestion = await response.json();
                } else {
                    alert('Failed to generate suggestion');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Generation failed');
            }
        },

        async createLessonFromAI() {
            try {
                const response = await fetch('/api/lessons/create-from-suggestion', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        course_id: this.aiLessonData.course_id,
                        lesson_title: this.aiLessonData.title,
                        lesson_topic: this.aiLessonData.topic,
                        lesson_description: this.aiLessonData.description,
                        lesson_overview: this.aiSuggestion.suggestion.lesson_overview,
                        estimated_duration_minutes: this.aiSuggestion.suggestion.estimated_duration_minutes,
                        learning_outcomes: this.aiSuggestion.suggestion.learning_outcomes
                    })
                });
                
                if (response.ok) {
                    this.modals.lessonAI = false;
                    await this.loadData();
                    alert('Lesson created with learning outcomes!');
                } else {
                    alert('Failed to create lesson');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Creation failed');
            }
        },

        // Learning Outcome CRUD
        openOutcomeModal(lesson) {
            this.outcomeData = {
                id: null,
                lesson_id: lesson.id,
                key: '',
                description: '',
                key_concepts: '',
                examples: ''
            };
            this.modals.outcome = true;
        },

        openEditOutcomeModal(outcome) {
            this.outcomeData = {
                id: outcome.id,
                lesson_id: outcome.lesson_id,
                key: outcome.key,
                description: outcome.description,
                key_concepts: outcome.key_concepts || '',
                examples: outcome.examples || ''
            };
            this.modals.outcome = true;
        },

        async saveOutcome() {
            const formData = new FormData();
            formData.append('key', this.outcomeData.key);
            formData.append('description', this.outcomeData.description);
            formData.append('key_concepts', this.outcomeData.key_concepts);
            formData.append('examples', this.outcomeData.examples);

            try {
                const url = this.outcomeData.id 
                    ? `/api/outcomes/${this.outcomeData.id}`
                    : `/api/lessons/${this.outcomeData.lesson_id}/outcomes`;
                const method = this.outcomeData.id ? 'PUT' : 'POST';
                
                const response = await fetch(url, {
                    method: method,
                    body: formData
                });
                
                if (response.ok) {
                    this.modals.outcome = false;
                    await this.loadData();
                    alert(this.outcomeData.id ? 'Learning outcome updated!' : 'Learning outcome created!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Save failed');
            }
        },

        async deleteOutcome(outcomeId) {
            if (!confirm('Delete this learning outcome? This will also delete all content.')) return;
            try {
                const response = await fetch(`/api/outcomes/${outcomeId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadData();
                    alert('Learning outcome deleted!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Delete failed');
            }
        },

        // Bulk Content Generation
        async generateAllCourseContent(course) {
            // Collect all learning outcomes from all lessons
            const allOutcomes = [];
            course.lessons.forEach(lesson => {
                lesson.learning_outcomes.forEach(outcome => {
                    allOutcomes.push({
                        id: outcome.id,
                        key: outcome.key,
                        description: outcome.description,
                        lesson_title: lesson.title
                    });
                });
            });

            if (allOutcomes.length === 0) {
                alert('No learning outcomes found in this course. Please add lessons and outcomes first.');
                return;
            }

            const confirm_msg = `Generate AI content for all ${allOutcomes.length} learning outcomes in this course? This will take approximately ${Math.ceil(allOutcomes.length * 3 / 60)} minutes.`;
            if (!confirm(confirm_msg)) return;

            // Initialize progress
            this.bulkProgress = {
                total: allOutcomes.length,
                completed: 0,
                failed: 0,
                items: allOutcomes.map(o => ({
                    id: o.id,
                    key: o.key,
                    description: `${o.lesson_title}: ${o.description}`,
                    status: 'pending'
                }))
            };
            this.bulkGenerating = true;

            // Generate content for each outcome sequentially
            for (let i = 0; i < allOutcomes.length; i++) {
                const outcome = allOutcomes[i];
                this.bulkProgress.items[i].status = 'generating';

                try {
                    const response = await fetch(`/api/outcomes/${outcome.id}/generate-and-save-content`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    if (response.ok) {
                        this.bulkProgress.items[i].status = 'success';
                    } else {
                        this.bulkProgress.items[i].status = 'error';
                        this.bulkProgress.failed++;
                    }
                } catch (error) {
                    console.error(`Error generating content for outcome ${outcome.id}:`, error);
                    this.bulkProgress.items[i].status = 'error';
                    this.bulkProgress.failed++;
                }

                this.bulkProgress.completed++;
            }

            // Reload data to show new content
            await this.loadData();
        },

        closeBulkGeneration() {
            this.bulkGenerating = false;
            this.bulkProgress = {
                total: 0,
                completed: 0,
                failed: 0,
                items: []
            };
        }
    };
}
