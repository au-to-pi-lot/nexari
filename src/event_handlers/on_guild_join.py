import discord

from src.proxies import GuildProxy


async def on_guild_join(guild: discord.Guild):
    """
    Called when the bot joins a new guild.
    """
    await GuildProxy.get(guild.id)
