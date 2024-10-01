import logging

from src.config import config
from src.services.channel import ChannelService
from src.services.db import Session
from src.services.discord_client import bot
from src.services.guild import GuildService
from src.services.user import UserService
from src.services.webhook import WebhookService

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
        channel_service = ChannelService(session)
        webhook_service = WebhookService(session)
        user_service = UserService(session)

        for guild in bot.guilds:
            await guild_service.sync(guild)
            for channel in guild.channels:
                if not ChannelService.is_allowed_channel_type(channel):
                    continue
                await channel_service.sync(channel)
                if ChannelService.has_threads(channel):
                    for thread in channel.threads:
                        await channel_service.sync(thread)
                for webhook in await channel.webhooks():
                    db_webhook = await webhook_service.get(webhook.id)
                    if db_webhook:
                        await webhook_service.sync(webhook)
            for user in guild.members:
                await user_service.sync(user)

    try:
        guild = await bot.fetch_guild(307011228293660683)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.exception(f"Error syncing command tree: {e}")
