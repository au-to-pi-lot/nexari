import asyncio

from config import config
from src.bot import DiscordBot


def main():
    bots = (DiscordBot(bot_config) for bot_config in config.bots)
    bot_coroutines = (bot.start(bot.config.discord.bot_token) for bot in bots)
    asyncio.gather(*bot_coroutines)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bots stopped.")
