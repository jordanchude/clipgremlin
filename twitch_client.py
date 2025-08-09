import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
import aiohttp
from twitchio.ext import commands
from twitchio import Client, Channel

logger = logging.getLogger(__name__)

class TwitchClient:
    """Client for Twitch IRC and API interactions."""
    
    def __init__(self, config):
        self.config = config
        self.client: Optional[Client] = None
        self.channel: Optional[Channel] = None
        self.is_connected = False
        self.is_muted = False
        self.message_history: List[Dict[str, Any]] = []
        self.last_message_time = 0
        self.message_count = 0
        self.rate_limit_reset_time = 0
        
    async def connect(self, channel_name: str):
        """Connect to Twitch IRC channel."""
        try:
            # Initialize TwitchIO client
            self.client = Client(
                token=self.config.twitch_bot_token,
                client_id=self.config.twitch_client_id,
                client_secret=self.config.twitch_client_secret,
                nick='ClipGremlin'
            )
            
            # Connect to the channel
            await self.client.connect()
            self.channel = self.client.get_channel(channel_name)
            
            if self.channel:
                await self.channel.join()
                self.is_connected = True
                logger.info(f"Connected to Twitch channel: {channel_name}")
                
                # Set color to green
                await self.send_message("/color Green")
            else:
                logger.error(f"Failed to join channel: {channel_name}")
                
        except Exception as e:
            logger.error(f"Error connecting to Twitch: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Twitch IRC."""
        if self.client:
            await self.client.disconnect()
            self.is_connected = False
            logger.info("Disconnected from Twitch")
    
    async def send_message(self, message: str) -> bool:
        """
        Send a message to the channel with rate limiting.
        
        Args:
            message: Message to send
            
        Returns:
            True if message was sent, False if rate limited
        """
        if not self.is_connected or not self.channel:
            logger.error("Not connected to Twitch channel")
            return False
        
        if self.is_muted:
            logger.info("Bot is muted, not sending message")
            return False
        
        # Check rate limiting
        current_time = time.time()
        if current_time - self.rate_limit_reset_time >= self.config.rate_limit_window:
            # Reset rate limit counter
            self.message_count = 0
            self.rate_limit_reset_time = current_time
        
        if self.message_count >= self.config.max_message_rate:
            logger.warning("Rate limit exceeded, skipping message")
            return False
        
        try:
            await self.channel.send(message)
            self.message_count += 1
            self.last_message_time = current_time
            logger.debug(f"Sent message: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    async def check_automod(self, message: str) -> bool:
        """
        Check if message passes AutoMod.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is allowed, False if denied
        """
        try:
            # This is a simplified implementation
            # In production, you'd use Twitch's Check AutoMod Status endpoint
            # For now, we'll do basic content filtering
            
            # Basic content filtering
            blocked_words = [
                'fuck', 'shit', 'bitch', 'asshole', 'dick', 'pussy',
                'cock', 'cunt', 'whore', 'slut', 'nigger', 'faggot'
            ]
            
            message_lower = message.lower()
            for word in blocked_words:
                if word in message_lower:
                    logger.info(f"Message blocked by AutoMod: {message}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking AutoMod: {e}")
            return False
    
    def add_message_to_history(self, username: str, message: str, is_moderator: bool = False):
        """
        Add a message to the rolling history window.
        
        Args:
            username: Username of the message sender
            message: Message content
            is_moderator: Whether the user is a moderator
        """
        current_time = time.time()
        
        # Add message to history
        self.message_history.append({
            'username': username,
            'message': message,
            'timestamp': current_time,
            'is_moderator': is_moderator
        })
        
        # Remove messages older than silence duration
        cutoff_time = current_time - self.config.silence_duration
        self.message_history = [
            msg for msg in self.message_history 
            if msg['timestamp'] > cutoff_time
        ]
    
    def is_silent(self) -> bool:
        """
        Check if the channel has been silent for the configured duration.
        
        Returns:
            True if silent for the required duration
        """
        if not self.message_history:
            return True
        
        current_time = time.time()
        cutoff_time = current_time - self.config.silence_duration
        
        # Check if any messages are within the silence window
        recent_messages = [
            msg for msg in self.message_history 
            if msg['timestamp'] > cutoff_time
        ]
        
        return len(recent_messages) == 0
    
    async def handle_command(self, username: str, message: str, is_moderator: bool, is_broadcaster: bool) -> Optional[str]:
        """
        Handle bot commands.
        
        Args:
            username: Username of the command sender
            message: Command message
            is_moderator: Whether the user is a moderator
            is_broadcaster: Whether the user is the broadcaster
            
        Returns:
            Response message or None
        """
        if not (is_moderator or is_broadcaster):
            return None
        
        message_lower = message.lower().strip()
        
        if message_lower == "!gremlin pause":
            self.is_muted = True
            return "Gremlin muted 😶"
        
        elif message_lower == "!gremlin resume":
            self.is_muted = False
            return "Gremlin unleashed 😈"
        
        return None
    
    def get_recent_transcript(self, max_length: int = 500) -> str:
        """
        Get recent transcript text for context.
        
        Args:
            max_length: Maximum length of transcript
            
        Returns:
            Recent transcript text
        """
        # This would be populated by the main bot logic
        # For now, return a placeholder
        return "Recent stream content..."
