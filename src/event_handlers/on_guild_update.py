import discord.abc

from src.services.db import Session
from src.services.guild import GuildService


async def on_guild_update(before: discord.Guild, after: discord.Guild):
    async with Session() as session:
        guild_service = GuildService(session)
        await guild_service.sync(after)
