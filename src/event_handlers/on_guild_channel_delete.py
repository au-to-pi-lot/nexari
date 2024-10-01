import discord.abc

from src.services.channel import ChannelService
from src.services.db import Session


async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    if not ChannelService.is_allowed_channel_type(channel):
        return

    async with Session() as session:
        channel_service = ChannelService(channel)
        db_channel = await channel_service.get(channel.id)
        await channel_service.delete(db_channel)