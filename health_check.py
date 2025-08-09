"""
Health check endpoint for ClipGremlin bot.
Provides status information and health monitoring.
"""

import asyncio
import json
import logging
from typing import Dict, Any
from aiohttp import web, ClientSession
import time

logger = logging.getLogger(__name__)

class HealthCheckServer:
    """HTTP server for health checks and status monitoring."""
    
    def __init__(self, bot_instance=None, port: int = 8080):
        self.bot = bot_instance
        self.port = port
        self.app = web.Application()
        self.start_time = time.time()
        
        # Setup routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/status', self.status_check)
        self.app.router.add_get('/metrics', self.metrics)
    
    async def health_check(self, request: web.Request) -> web.Response:
        """Basic health check endpoint."""
        try:
            health_status = {
                'status': 'healthy',
                'timestamp': time.time(),
                'uptime': time.time() - self.start_time,
                'service': 'ClipGremlin'
            }
            
            # Check if bot is running
            if self.bot and hasattr(self.bot, 'is_running'):
                health_status['bot_running'] = self.bot.is_running
            
            return web.json_response(health_status)
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return web.json_response(
                {'status': 'unhealthy', 'error': str(e)},
                status=500
            )
    
    async def status_check(self, request: web.Request) -> web.Response:
        """Detailed status information."""
        try:
            status = {
                'service': 'ClipGremlin',
                'version': '1.0.0',
                'timestamp': time.time(),
                'uptime': time.time() - self.start_time,
                'status': 'running'
            }
            
            if self.bot:
                # Add bot-specific status
                status.update({
                    'bot_running': getattr(self.bot, 'is_running', False),
                    'current_language': getattr(self.bot, 'current_language', 'unknown'),
                    'twitch_connected': getattr(self.bot.twitch_client, 'is_connected', False) if hasattr(self.bot, 'twitch_client') else False,
                })
                
                # Add silence detector stats if available
                if hasattr(self.bot, 'silence_detector'):
                    try:
                        silence_stats = self.bot.silence_detector.get_stats()
                        status['silence_detector'] = silence_stats
                    except Exception as e:
                        logger.warning(f"Could not get silence detector stats: {e}")
            
            return web.json_response(status)
            
        except Exception as e:
            logger.error(f"Status check error: {e}")
            return web.json_response(
                {'status': 'error', 'error': str(e)},
                status=500
            )
    
    async def metrics(self, request: web.Request) -> web.Response:
        """Prometheus-style metrics endpoint."""
        try:
            metrics_data = []
            
            # Basic metrics
            metrics_data.append(f'clipgremlin_uptime_seconds {time.time() - self.start_time}')
            metrics_data.append(f'clipgremlin_status{{status="running"}} 1')
            
            if self.bot and hasattr(self.bot, 'silence_detector'):
                try:
                    stats = self.bot.silence_detector.get_stats()
                    metrics_data.append(f'clipgremlin_total_messages {stats.get("total_messages", 0)}')
                    metrics_data.append(f'clipgremlin_messages_last_minute {stats.get("messages_last_minute", 0)}')
                    metrics_data.append(f'clipgremlin_is_silent {1 if stats.get("is_silent", False) else 0}')
                    metrics_data.append(f'clipgremlin_can_generate_prompt {1 if stats.get("can_generate_prompt", False) else 0}')
                except Exception as e:
                    logger.warning(f"Could not get metrics from silence detector: {e}")
            
            response_text = '\n'.join(metrics_data) + '\n'
            
            return web.Response(
                text=response_text,
                content_type='text/plain'
            )
            
        except Exception as e:
            logger.error(f"Metrics error: {e}")
            return web.Response(
                text=f'# Error getting metrics: {e}\n',
                content_type='text/plain',
                status=500
            )
    
    async def start_server(self):
        """Start the health check server."""
        try:
            runner = web.AppRunner(self.app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', self.port)
            await site.start()
            
            logger.info(f"Health check server started on port {self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            raise
