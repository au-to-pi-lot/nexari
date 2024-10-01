import discord.abc

from src.services.channel import ChannelService
from src.services.db import Session


async def on_guild_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    if not ChannelService.is_allowed_channel_type(after):
        return

    async with Session() as session:
        channel_service = ChannelService(session)
        await channel_service.sync(after)
