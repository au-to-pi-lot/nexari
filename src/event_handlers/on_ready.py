import logging

from src.config import config
from src.services.db import Session
from src.services.discord_client import bot
from src.services.guild import GuildService

logger = logging.getLogger(__name__)


async def on_ready():
    """
    Called when the bot is ready and connected to Discord.
    """
    logger.info(f"{bot.user} has connected to Discord!")
    print(
        f"{bot.user} has connected to Discord! INVITE URL: "
        f"https://discord.com/api/oauth2/authorize?client_id={config.client_id}&permissions=412854144000&scope=bot"
    )

    async with Session() as session:
        guild_service = GuildService(session)
        for guild in bot.guilds:
            await guild_service.sync(guild)

    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.exception(f"Error syncing command tree: {e}")
