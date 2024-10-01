import discord.abc

from src.services.channel import ChannelService
from src.services.db import Session


async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    if not ChannelService.is_allowed_channel_type(channel):
        return

    async with Session() as session:
        channel_service = ChannelService(session=session)
        await channel_service.create(channel=channel)