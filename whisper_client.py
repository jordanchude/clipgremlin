import asyncio
import json
import logging
from typing import Optional, Dict, Any
import aiohttp
import base64

logger = logging.getLogger(__name__)

class WhisperClient:
    """Client for OpenAI Whisper-Turbo API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1/audio/transcriptions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "multipart/form-data"
        }
    
    async def transcribe_audio(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Transcribe audio data using Whisper-Turbo.
        
        Args:
            audio_data: Audio data in WAV format (mono, 16kHz)
            
        Returns:
            Transcription result or None if failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Prepare form data
                data = aiohttp.FormData()
                data.add_field('file', audio_data, 
                             filename='audio.wav',
                             content_type='audio/wav')
                data.add_field('model', 'whisper-1')
                data.add_field('response_format', 'json')
                data.add_field('language', 'auto')  # Auto-detect language
                
                # Make request
                async with session.post(
                    self.base_url,
                    data=data,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.debug(f"Whisper transcription: {result}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Whisper API error {response.status}: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None
    
    def extract_language(self, transcription_result: Dict[str, Any]) -> Optional[str]:
        """
        Extract language code from Whisper response.
        
        Args:
            transcription_result: Result from Whisper API
            
        Returns:
            Language code (e.g., 'en', 'es', 'fr') or None
        """
        try:
            return transcription_result.get('language')
        except Exception as e:
            logger.error(f"Error extracting language: {e}")
            return None
    
    def extract_text(self, transcription_result: Dict[str, Any]) -> Optional[str]:
        """
        Extract transcribed text from Whisper response.
        
        Args:
            transcription_result: Result from Whisper API
            
        Returns:
            Transcribed text or None
        """
        try:
            return transcription_result.get('text', '').strip()
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return None
    
    async def transcribe_with_retry(self, audio_data: bytes, max_retries: int = 2) -> Optional[Dict[str, Any]]:
        """
        Transcribe audio with exponential backoff retry logic.
        
        Args:
            audio_data: Audio data in WAV format
            max_retries: Maximum number of retries
            
        Returns:
            Transcription result or None if all retries failed
        """
        for attempt in range(max_retries + 1):
            try:
                result = await self.transcribe_audio(audio_data)
                if result:
                    return result
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Transcription failed, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Transcription attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
        
        logger.error("All transcription attempts failed")
        return None
