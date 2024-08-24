import asyncio

from config import config
from src.bot import DiscordBot


def main():
    """
    Main function to start the Discord bot.

    This function creates a DiscordBot instance with the bot configuration,
    starts it in the event loop, and runs the loop indefin
itely.
    """
    bot = DiscordBot(config.bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(bot.config.discord.bot_token))
    loop.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bot stopped.")
