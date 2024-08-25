from config import config
from src.bot import DiscordBot


def main():
    """
    Main function to start the Discord bot.
    """
    bot = DiscordBot(config.bot)
    bot.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bot stopped.")
