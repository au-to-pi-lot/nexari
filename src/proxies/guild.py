import discord

from src.db.models import Guild
from src.types.proxy import BaseProxy


class GuildProxy(BaseProxy):
    def __init__(self, discord_guild: discord.Guild, db_guild: Guild):
        super().__init__(discord_guild, db_guild)

    @classmethod
    async def get(cls, identifier: int):
        bot =

    async def save(self):
        pass