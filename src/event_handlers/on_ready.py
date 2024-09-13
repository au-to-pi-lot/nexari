import logging

from src.config import config
from src.proxies import GuildProxy
from src.services.discord_client import bot

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

    for guild in bot.guilds:
        await GuildProxy.get(guild.id)

    try:
        guild = await bot.fetch_guild(307011228293660683)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.exception(f"Error syncing command tree: {e}")
