import logging
import os
from typing import Optional

from aiohttp import web
from discord import Client

logger = logging.getLogger(__name__)

class HealthCheck:
    def __init__(self):
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.discord_client: Optional[Client] = None
        
        # Setup routes
        self.app.router.add_get("/healthz", self.liveness_check)
        self.app.router.add_get("/readyz", self.readiness_check)
        
    def set_discord_client(self, client: Client):
        """Set the Discord client for connection checking"""
        self.discord_client = client
        
    async def liveness_check(self, request: web.Request) -> web.Response:
        """Basic liveness check - if this responds, the process is alive"""
        return web.Response(text="OK")
        
    async def readiness_check(self, request: web.Request) -> web.Response:
        """Readiness check - verifies Discord connection"""
        if not self.discord_client:
            return web.Response(text="Discord client not initialized", status=503)
            
        if not self.discord_client.is_ready():
            return web.Response(text="Discord connection not ready", status=503)
            
        return web.Response(text="OK")
        
    async def start(self):
        """Start the health check server"""
        port = int(os.getenv("PORT", "8080"))
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "0.0.0.0", port)
        
        try:
            await self.site.start()
            logger.info(f"Health check server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            raise
            
    async def stop(self):
        """Gracefully stop the health check server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Health check server stopped")

# Global instance
health_check = HealthCheck()

async def start_health_check_server(discord_client: Optional[Client] = None):
    """Start the health check server and optionally set the Discord client"""
    if discord_client:
        health_check.set_discord_client(discord_client)
    await health_check.start()
