import asyncio
import logging
import logging.handlers
import os
import sys

from src.commands import LLMCommands
from src.config import config
from src.event_handlers import register_event_handlers
from src.health_check import start_health_check_server
from src.services.discord_client import bot

logger = logging.getLogger(__name__)


async def main():
    """
    Main function to start the Discord bot and health check server.
    """
    os.makedirs("log", exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler("log/nexari.log", maxBytes=1024 * 1024, backupCount=10, encoding="utf-8"),
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

    await start_health_check_server(bot)
    logger.info("Health check server started")

    register_event_handlers(bot)
    await bot.add_cog(LLMCommands(bot))
    async with bot:
        await bot.start(config.bot_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
