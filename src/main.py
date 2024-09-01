import asyncio
import os
import sys
import logging
import logging.handlers

from config import config
from src.bot import DiscordBot

logger = logging.getLogger(__name__)



async def main():
    """
    Main function to start the Discord bot.
    """
    os.makedirs("log", exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler("log/nexari.log", maxBytes=1024 * 1024, backupCount=10, encoding="utf-8")
    ]
    logging.basicConfig(
        handlers=handlers,
        level=logging.INFO,
        style="{",
        format='[{asctime}] {levelname} ({name}): {message}'
    )

    def handle_exception(loop, context):
        logger.error(f"Uncaught exception: {context['message']}")

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(handle_exception)

    bot = DiscordBot(config)
    async with bot:
        await bot.start(config.bot_token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
