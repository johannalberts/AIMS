"""
AIMS Speech-to-Text Transcription Service
Uses faster-whisper for CPU-based transcription
"""
import os
import logging
from pathlib import Path
from typing import Optional
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for transcribing audio using faster-whisper."""
    
    _instance: Optional['TranscriptionService'] = None
    _model: Optional[WhisperModel] = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one model instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the Whisper model (only once)."""
        if self._model is None:
            logger.info("Initializing Whisper model (base, CPU, int8)...")
            try:
                self._model = WhisperModel(
                    "base",
                    device="cpu",
                    compute_type="int8",
                    download_root=None  # Uses default cache
                )
                logger.info("✅ Whisper model initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Whisper model: {e}")
                raise
    
    def transcribe_audio(self, audio_file_path: str) -> dict:
        """
        Transcribe an audio file to text.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            dict with 'text' and 'language' keys
            
        Raises:
            Exception: If transcription fails
        """
        if not self._model:
            raise RuntimeError("Whisper model not initialized")
        
        try:
            logger.info(f"Transcribing audio file: {audio_file_path}")
            
            # Transcribe
            segments, info = self._model.transcribe(
                audio_file_path,
                beam_size=5,
                vad_filter=True,  # Voice Activity Detection to filter silence
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Collect all segments
            text_segments = []
            for segment in segments:
                text_segments.append(segment.text)
            
            full_text = " ".join(text_segments).strip()
            
            logger.info(f"✅ Transcription complete. Language: {info.language}, Text length: {len(full_text)}")
            
            if not full_text:
                logger.warning("⚠️ No speech detected in audio file")
                return {
                    "text": "",
                    "language": info.language,
                    "error": "No speech detected in the audio"
                }
            
            return {
                "text": full_text,
                "language": info.language
            }
            
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}")
            raise Exception(f"Transcription error: {str(e)}")


def get_transcription_service() -> TranscriptionService:
    """Get the singleton transcription service instance."""
    return TranscriptionService()
