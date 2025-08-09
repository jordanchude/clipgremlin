import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
from collections import deque

logger = logging.getLogger(__name__)

class SilenceDetector:
    """Detects periods of chat silence and triggers prompt generation."""
    
    def __init__(self, config):
        self.config = config
        self.message_history: deque = deque(maxlen=1000)  # Rolling window
        self.last_silence_check = 0
        self.silence_detected = False
        self.last_prompt_time = 0
        self.min_prompt_interval = 60  # Minimum seconds between prompts
    
    def add_message(self, username: str, message: str, timestamp: float = None):
        """
        Add a message to the history for silence detection.
        
        Args:
            username: Username of the message sender
            message: Message content
            timestamp: Message timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.message_history.append({
            'username': username,
            'message': message,
            'timestamp': timestamp
        })
        
        logger.debug(f"Added message from {username}: {message[:50]}...")
    
    def is_silent(self) -> bool:
        """
        Check if the channel has been silent for the configured duration.
        
        Returns:
            True if silent for the required duration
        """
        current_time = time.time()
        cutoff_time = current_time - self.config.silence_duration
        
        # Check if any messages are within the silence window
        recent_messages = [
            msg for msg in self.message_history 
            if msg['timestamp'] > cutoff_time
        ]
        
        is_silent = len(recent_messages) == 0
        
        if is_silent and not self.silence_detected:
            logger.info(f"Silence detected! No messages for {self.config.silence_duration} seconds")
            self.silence_detected = True
        elif not is_silent and self.silence_detected:
            logger.info("Silence ended - chat activity resumed")
            self.silence_detected = False
        
        return is_silent
    
    def can_generate_prompt(self) -> bool:
        """
        Check if enough time has passed since the last prompt.
        
        Returns:
            True if a new prompt can be generated
        """
        current_time = time.time()
        time_since_last_prompt = current_time - self.last_prompt_time
        
        return time_since_last_prompt >= self.min_prompt_interval
    
    def mark_prompt_sent(self):
        """Mark that a prompt was sent."""
        self.last_prompt_time = time.time()
        self.silence_detected = False  # Reset silence detection
        logger.info("Prompt sent, resetting silence detection")
    
    def get_recent_messages(self, duration_seconds: int = 300) -> List[Dict[str, Any]]:
        """
        Get recent messages within the specified duration.
        
        Args:
            duration_seconds: Duration to look back in seconds
            
        Returns:
            List of recent messages
        """
        current_time = time.time()
        cutoff_time = current_time - duration_seconds
        
        return [
            msg for msg in self.message_history 
            if msg['timestamp'] > cutoff_time
        ]
    
    def get_message_count(self, duration_seconds: int = 60) -> int:
        """
        Get the number of messages in the specified duration.
        
        Args:
            duration_seconds: Duration to look back in seconds
            
        Returns:
            Number of messages
        """
        return len(self.get_recent_messages(duration_seconds))
    
    def clear_history(self):
        """Clear the message history."""
        self.message_history.clear()
        self.silence_detected = False
        logger.info("Message history cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the silence detector.
        
        Returns:
            Dictionary with statistics
        """
        current_time = time.time()
        
        return {
            'total_messages': len(self.message_history),
            'messages_last_minute': self.get_message_count(60),
            'messages_last_5_minutes': self.get_message_count(300),
            'is_silent': self.is_silent(),
            'time_since_last_prompt': current_time - self.last_prompt_time,
            'can_generate_prompt': self.can_generate_prompt()
        }
