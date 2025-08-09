import asyncio
import subprocess
import tempfile
import os
from typing import AsyncGenerator, Optional
import aiohttp
import aiofiles
from pydub import AudioSegment
import logging

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio stream processing and chunking."""
    
    def __init__(self, config):
        self.config = config
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.temp_dir = tempfile.mkdtemp()
        self.chunk_counter = 0
    
    async def start_stream_capture(self, stream_url: str) -> AsyncGenerator[bytes, None]:
        """
        Start capturing audio from HLS stream and yield audio chunks.
        
        Args:
            stream_url: HLS playlist URL
            
        Yields:
            Audio chunks as bytes (WAV format, mono, 16kHz)
        """
        try:
            # FFmpeg command to capture HLS stream and convert to WAV
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-f', 'wav',
                '-ac', '1',  # mono
                '-ar', '16000',  # 16kHz sample rate
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-loglevel', 'error',
                '-'
            ]
            
            logger.info(f"Starting FFmpeg process for stream: {stream_url}")
            
            # Start FFmpeg process
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Read audio data in chunks
            chunk_size = 16000 * 2 * self.config.audio_chunk_duration  # 16kHz * 2 bytes * duration
            buffer = b''
            
            while self.ffmpeg_process.poll() is None:
                data = self.ffmpeg_process.stdout.read(chunk_size)
                if not data:
                    break
                
                buffer += data
                
                # Yield complete chunks
                while len(buffer) >= chunk_size:
                    chunk = buffer[:chunk_size]
                    buffer = buffer[chunk_size:]
                    
                    # Check if chunk is too large
                    if len(chunk) > self.config.max_audio_size_mb * 1024 * 1024:
                        logger.warning(f"Audio chunk too large ({len(chunk)} bytes), skipping")
                        continue
                    
                    yield chunk
                    self.chunk_counter += 1
                    
                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error in audio capture: {e}")
            raise
        finally:
            self.stop_stream_capture()
    
    def stop_stream_capture(self):
        """Stop the FFmpeg process."""
        if self.ffmpeg_process:
            logger.info("Stopping FFmpeg process")
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
            self.ffmpeg_process = None
    
    async def get_stream_url(self, channel_name: str) -> Optional[str]:
        """
        Get the HLS stream URL for a Twitch channel.
        
        Args:
            channel_name: Twitch channel name
            
        Returns:
            HLS playlist URL or None if not found
        """
        try:
            # This is a simplified version - in production you'd use Twitch's API
            # to get the actual stream URL
            stream_url = f"https://usher.ttvnw.net/api/channel/hls/{channel_name}.m3u8"
            
            # Verify the stream is actually live
            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        if '#EXTM3U' in content:
                            return stream_url
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting stream URL for {channel_name}: {e}")
            return None
    
    def cleanup(self):
        """Clean up temporary files and resources."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}")
