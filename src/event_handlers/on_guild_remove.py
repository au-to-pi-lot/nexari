import discord

from src.services.db import Session
from src.services.guild import GuildService


async def on_guild_remove(guild: discord.Guild):
    async with Session() as session:
        guild_service = GuildService(session)
        db_guild = await guild_service.get(guild.id)
        await guild_service.delete(db_guild)