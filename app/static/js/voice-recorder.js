/**
 * Alpine.js component for voice recording and transcription
 * Integrates with MediaRecorder API and backend Whisper transcription service
 */
function voiceRecorder() {
    return {
        isRecording: false,
        hasRecording: false,
        isTranscribing: false,
        transcript: '',
        errorMessage: '',
        mediaRecorder: null,
        audioChunks: [],
        audioBlob: null,
        recordingTime: 0,
        recordingInterval: null,
        
        init() {
            // Check browser support
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.warn('MediaRecorder API not supported');
            }
        },
        
        async toggleRecording() {
            if (this.isRecording) {
                this.stopRecording();
            } else {
                await this.startRecording();
            }
        },
        
        async startRecording() {
            try {
                this.errorMessage = '';
                this.recordingTime = 0;
                this.audioChunks = [];
                
                // Request microphone access
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        sampleRate: 16000  // Whisper works well with 16kHz
                    } 
                });
                
                // Create MediaRecorder
                // Try webm first, fallback to other formats
                let mimeType = 'audio/webm';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'audio/ogg';
                }
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'audio/mp4';
                }
                
                this.mediaRecorder = new MediaRecorder(stream, { mimeType });
                
                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        this.audioChunks.push(event.data);
                    }
                };
                
                this.mediaRecorder.onstop = () => {
                    // Create blob from chunks
                    this.audioBlob = new Blob(this.audioChunks, { type: mimeType });
                    this.hasRecording = true;
                    
                    // Stop all tracks
                    stream.getTracks().forEach(track => track.stop());
                    
                    console.log('Recording stopped. Blob size:', this.audioBlob.size);
                };
                
                this.mediaRecorder.start();
                this.isRecording = true;
                
                // Start recording timer
                this.recordingInterval = setInterval(() => {
                    this.recordingTime++;
                }, 1000);
                
                console.log('Recording started with mimeType:', mimeType);
                
            } catch (error) {
                console.error('Error accessing microphone:', error);
                this.errorMessage = 'Could not access microphone. Please grant permission and try again.';
            }
        },
        
        stopRecording() {
            if (this.mediaRecorder && this.isRecording) {
                this.mediaRecorder.stop();
                this.isRecording = false;
                
                if (this.recordingInterval) {
                    clearInterval(this.recordingInterval);
                    this.recordingInterval = null;
                }
            }
        },
        
        async transcribeAudio() {
            if (!this.audioBlob) {
                this.errorMessage = 'No recording available';
                return;
            }
            
            try {
                this.isTranscribing = true;
                this.errorMessage = '';
                
                // Create FormData and append audio file
                const formData = new FormData();
                formData.append('audio', this.audioBlob, 'recording.webm');
                
                console.log('Sending audio for transcription...');
                
                // Send to backend
                const response = await fetch('/assess/transcribe', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Transcription failed');
                }
                
                console.log('Transcription successful:', data.transcript);
                
                // Set transcript in textarea
                this.transcript = data.transcript;
                
                // Clear recording
                this.hasRecording = false;
                this.audioBlob = null;
                this.audioChunks = [];
                
            } catch (error) {
                console.error('Transcription error:', error);
                this.errorMessage = error.message || 'Transcription failed. Please try again.';
            } finally {
                this.isTranscribing = false;
            }
        },
        
        clearTranscript() {
            this.transcript = '';
            this.hasRecording = false;
            this.audioBlob = null;
            this.audioChunks = [];
            this.errorMessage = '';
        }
    }
}
