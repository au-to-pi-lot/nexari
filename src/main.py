import asyncio
from config import config
from src.bot import DiscordBot


async def main():
    """
    Main function to start the Discord bot.
    """
    bot = DiscordBot(config)
    await bot.start(config.bot_token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
