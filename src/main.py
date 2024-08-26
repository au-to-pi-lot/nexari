import asyncio
from config import config
from src.bot import DiscordBot


def main():
    """
    Main function to start the Discord bot.
    """
    bot = DiscordBot(config)
    bot.run(config.bot_token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
