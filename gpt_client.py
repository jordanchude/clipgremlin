import asyncio
import json
import logging
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

class GPTClient:
    """Client for OpenAI GPT-3.5-Turbo API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate_prompt(self, transcript_snippet: str, language: str = "en") -> Optional[str]:
        """
        Generate a mischievous PG-13 prompt based on transcript snippet.
        
        Args:
            transcript_snippet: Recent transcript text
            language: Language code (e.g., 'en', 'es', 'fr')
            
        Returns:
            Generated prompt or None if failed
        """
        try:
            # Language-specific system prompts
            language_prompts = {
                "en": "You are a mischievous but friendly bot that generates one-line, PG-13, ToS-safe 'troll' questions or comments. Keep it playful, not mean. Maximum 100 characters.",
                "es": "Eres un bot travieso pero amigable que genera preguntas o comentarios de una línea, PG-13, seguros para ToS. Manténlo juguetón, no malo. Máximo 100 caracteres.",
                "fr": "Tu es un bot espiègle mais amical qui génère des questions ou commentaires d'une ligne, PG-13, sûrs pour ToS. Garde ça ludique, pas méchant. Maximum 100 caractères.",
                "de": "Du bist ein schelmischer aber freundlicher Bot, der einzeilige, PG-13, ToS-sichere 'Troll'-Fragen oder Kommentare generiert. Halte es verspielt, nicht böse. Maximum 100 Zeichen."
            }
            
            system_prompt = language_prompts.get(language, language_prompts["en"])
            
            # Create the prompt
            user_prompt = f"Based on this transcript snippet, generate a mischievous but friendly one-line question or comment (max 100 chars):\n\n{transcript_snippet[:500]}"
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.8,
                "top_p": 0.9
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result['choices'][0]['message']['content'].strip()
                        
                        # Clean up the response
                        content = content.replace('"', '').replace("'", "")
                        if len(content) > 100:
                            content = content[:97] + "..."
                        
                        logger.debug(f"Generated prompt: {content}")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"GPT API error {response.status}: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error generating prompt: {e}")
            return None
    
    async def generate_with_retry(self, transcript_snippet: str, language: str = "en", max_retries: int = 2) -> Optional[str]:
        """
        Generate prompt with exponential backoff retry logic.
        
        Args:
            transcript_snippet: Recent transcript text
            language: Language code
            max_retries: Maximum number of retries
            
        Returns:
            Generated prompt or None if all retries failed
        """
        for attempt in range(max_retries + 1):
            try:
                result = await self.generate_prompt(transcript_snippet, language)
                if result:
                    return result
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Prompt generation failed, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Prompt generation attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
        
        logger.error("All prompt generation attempts failed")
        return None
