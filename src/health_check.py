import logging
import os

from aiohttp import web

logger = logging.getLogger(__name__)


async def health_check(request):
    """Health check endpoint that returns OK"""
    return web.Response(text="OK")


async def start_health_check_server():
    """Start the health check server on PORT env var (default 8080)"""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)  # Additional health endpoint

    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)

    try:
        logger.info(f"Starting health check server on port {port}")
        await site.start()
        logger.info(f"Health check server started successfully on port {port}")
    except Exception as e:
        logger.error(f"Failed to start health check server: {e}")
        raise