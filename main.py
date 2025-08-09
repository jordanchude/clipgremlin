#!/usr/bin/env python3
"""
ClipGremlin - A mischievous Twitch bot that generates prompts during chat silence.
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional
import uvloop

from config import config
from audio_processor import AudioProcessor
from whisper_client import WhisperClient
from gpt_client import GPTClient
from twitch_client import TwitchClient
from silence_detector import SilenceDetector
from health_check import HealthCheckServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('clipgremlin.log')
    ]
)

logger = logging.getLogger(__name__)

class ClipGremlinBot:
    """Main bot class that orchestrates all components."""
    
    def __init__(self):
        self.config = config
        self.audio_processor = AudioProcessor(config)
        self.whisper_client = WhisperClient(config.openai_api_key)
        self.gpt_client = GPTClient(config.openai_api_key)
        self.twitch_client = TwitchClient(config)
        self.silence_detector = SilenceDetector(config)
        self.health_server = HealthCheckServer(bot_instance=self)
        
        self.is_running = False
        self.current_language = "en"
        self.recent_transcript = ""
        
    async def start(self):
        """Start the bot."""
        try:
            logger.info("Starting ClipGremlin bot...")
            
            # Validate configuration
            if not self.config.validate():
                logger.error("Invalid configuration. Please check environment variables.")
                return
            
            # Connect to Twitch
            await self.twitch_client.connect(self.config.channel_name)
            
            # Get stream URL
            stream_url = await self.audio_processor.get_stream_url(self.config.channel_name)
            if not stream_url:
                logger.error(f"Could not get stream URL for {self.config.channel_name}")
                return
            
            logger.info(f"Stream URL obtained: {stream_url}")
            
            self.is_running = True
            
            # Start health check server
            await self.health_server.start_server()
            
            # Start the main processing loop
            await self.run_main_loop(stream_url)
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def run_main_loop(self, stream_url: str):
        """Main processing loop."""
        try:
            # Start audio processing
            audio_task = asyncio.create_task(self.process_audio(stream_url))
            
            # Start chat monitoring
            chat_task = asyncio.create_task(self.monitor_chat())
            
            # Start silence detection
            silence_task = asyncio.create_task(self.monitor_silence())
            
            # Wait for all tasks
            await asyncio.gather(audio_task, chat_task, silence_task)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
    
    async def process_audio(self, stream_url: str):
        """Process audio stream and transcribe."""
        try:
            async for audio_chunk in self.audio_processor.start_stream_capture(stream_url):
                if not self.is_running:
                    break
                
                # Transcribe audio chunk
                transcription = await self.whisper_client.transcribe_with_retry(audio_chunk)
                if transcription:
                    text = self.whisper_client.extract_text(transcription)
                    language = self.whisper_client.extract_language(transcription)
                    
                    if text and text.strip():
                        self.recent_transcript = text.strip()
                        self.current_language = language or "en"
                        logger.debug(f"Transcribed: {text[:100]}... (lang: {self.current_language})")
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
    
    async def monitor_chat(self):
        """Monitor chat messages."""
        try:
            while self.is_running:
                # This would integrate with TwitchIO's event system
                # For now, we'll simulate chat monitoring
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error monitoring chat: {e}")
    
    async def monitor_silence(self):
        """Monitor for silence and generate prompts."""
        try:
            while self.is_running:
                if (self.silence_detector.is_silent() and 
                    self.silence_detector.can_generate_prompt()):
                    
                    logger.info("Silence detected and prompt can be generated")
                    
                    # Generate prompt
                    prompt = await self.generate_prompt()
                    if prompt:
                        # Check AutoMod
                        if await self.twitch_client.check_automod(prompt):
                            # Send message
                            success = await self.twitch_client.send_message(prompt)
                            if success:
                                self.silence_detector.mark_prompt_sent()
                                logger.info(f"Sent prompt: {prompt}")
                            else:
                                logger.warning("Failed to send prompt (rate limited)")
                        else:
                            logger.info("Prompt blocked by AutoMod")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except Exception as e:
            logger.error(f"Error monitoring silence: {e}")
    
    async def generate_prompt(self) -> Optional[str]:
        """Generate a mischievous prompt based on recent transcript."""
        try:
            if not self.recent_transcript:
                self.recent_transcript = "Stream content"
            
            prompt = await self.gpt_client.generate_with_retry(
                self.recent_transcript,
                self.current_language
            )
            
            return prompt
            
        except Exception as e:
            logger.error(f"Error generating prompt: {e}")
            return None
    
    async def handle_command(self, username: str, message: str, is_moderator: bool, is_broadcaster: bool):
        """Handle bot commands."""
        try:
            response = await self.twitch_client.handle_command(username, message, is_moderator, is_broadcaster)
            if response:
                await self.twitch_client.send_message(response)
                
        except Exception as e:
            logger.error(f"Error handling command: {e}")
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        
        self.is_running = False
        
        # Stop audio processing
        self.audio_processor.stop_stream_capture()
        self.audio_processor.cleanup()
        
        # Disconnect from Twitch
        await self.twitch_client.disconnect()
        
        logger.info("Cleanup complete")

async def main():
    """Main entry point."""
    # Use uvloop for better performance
    uvloop.install()
    
    bot = ClipGremlinBot()
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        bot.is_running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
