from discord import Client
from svcs import Container

from src.bot import logger
from src.services import registry


async def on_ready():
    """
    Called when the bot is ready and connected to Discord.
    """
    client = Container(registry=registry).get(Client)
    logger.info(f"{client.user} has connected to Discord!")

    for guild in client.guilds:
        await client.ensure_guild_exists(guild)

    try:
        guild = await client.fetch_guild(307011228293660683)
        client.tree.copy_global_to(guild=guild)
        synced = await client.tree.sync(guild=guild)
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.exception(f"Error syncing command tree: {e}")
