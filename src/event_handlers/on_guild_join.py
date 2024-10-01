import discord

from src.services.channel import ChannelService
from src.services.db import Session


async def on_guild_join(guild: discord.Guild):
    """
    Called when the bot joins a new guild.
    """
    async with Session() as session:
        channel_service = ChannelService(session)
        channels = [
            channel
            for channel in guild.channels
            if ChannelService.is_allowed_channel_type(channel)
        ]
        for channel in channels:
            await channel_service.get_or_create(channel)
            if ChannelService.has_threads(channel):
                threads = channel.threads
                for thread in threads:
                    await channel_service.get_or_create(thread)
