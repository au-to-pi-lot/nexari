import asyncio

from config import config
from src.bot import DiscordBot


def main():
    """
    Main function to start the Discord bots.

    This function creates DiscordBot instances for each bot configuration,
    starts them in the event loop, and runs the loop indefinitely.
    """
    bots = [DiscordBot(bot_config) for bot_config in config.bots]
    loop = asyncio.get_event_loop()
    for bot in bots:
        loop.create_task(bot.start(bot.config.discord.bot_token))
    loop.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bots stopped.")
