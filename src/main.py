import asyncio
import logging
import logging.handlers
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import config
from src.commands import LLMCommands
from src.event_handlers import register_event_handlers
from src.services.discord_client import bot

logger = logging.getLogger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_check_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(('', port), HealthCheckHandler)
    logger.info(f"Starting health check server on port {port}")
    server.serve_forever()


async def main():
    """
    Main function to start the Discord bot and health check server.
    """
    os.makedirs("log", exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            "log/nexari.log", maxBytes=1024 * 1024, backupCount=10, encoding="utf-8"
        ),
    ]
    logging.basicConfig(
        handlers=handlers,
        level=logging.INFO,
        style="{",
        format="[{asctime}] {levelname} ({name}): {message}",
    )

    def handle_exception(loop, context):
        logger.error(f"Uncaught exception: {context['message']}")

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(handle_exception)

    # Start health check server in a separate thread
    import threading
    health_check_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_check_thread.start()

    register_event_handlers(bot)
    await bot.add_cog(LLMCommands(bot))
    async with bot:
        await bot.start(config.bot_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
