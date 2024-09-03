import discord
from typing import Optional, List

from src.db.models import Guild as DBGuild
from src.types.proxy import BaseProxy
from src.services import svc
from sqlalchemy.ext.asyncio import AsyncSession
from src.bot import DiscordBot

class GuildProxy(BaseProxy):
    def __init__(self, discord_guild: discord.Guild, db_guild: DBGuild):
        super().__init__(discord_guild, db_guild)

    @classmethod
    async def get(cls, identifier: int) -> Optional['GuildProxy']:
        bot = await svc.resolve(DiscordBot)()
        discord_guild = bot.get_guild(identifier)
        if not discord_guild:
            return None

        async with svc.resolve(AsyncSession)() as session:
            db_guild = await session.get(DBGuild, identifier)
            if not db_guild:
                db_guild = DBGuild(id=identifier, name=discord_guild.name)
                session.add(db_guild)
                await session.commit()

        return cls(discord_guild, db_guild)

    async def save(self):
        async with svc.resolve(AsyncSession)() as session:
            self._db_obj.name = self._discord_obj.name
            session.add(self._db_obj)
            await session.commit()

    @property
    def name(self) -> str:
        return self._discord_obj.name

    @property
    def member_count(self) -> int:
        return self._discord_obj.member_count

    @property
    def channels(self) -> List[discord.abc.GuildChannel]:
        return self._discord_obj.channels

    @property
    def roles(self) -> List[discord.Role]:
        return self._discord_obj.roles

    async def fetch_members(self) -> List[discord.Member]:
        return [member async for member in self._discord_obj.fetch_members()]

    async def create_text_channel(self, name: str, **kwargs) -> discord.TextChannel:
        channel = await self._discord_obj.create_text_channel(name, **kwargs)
        # You might want to add logic here to update your database with the new channel
        return channel

    async def create_role(self, name: str, **kwargs) -> discord.Role:
        role = await self._discord_obj.create_role(name=name, **kwargs)
        # You might want to add logic here to update your database with the new role
        return role

    def get_member(self, user_id: int) -> Optional[discord.Member]:
        return self._discord_obj.get_member(user_id)

    async def fetch_member(self, user_id: int) -> discord.Member:
        return await self._discord_obj.fetch_member(user_id)

    async def kick(self, user: discord.User, reason: Optional[str] = None):
        await self._discord_obj.kick(user, reason=reason)

    async def ban(self, user: discord.User, reason: Optional[str] = None, delete_message_days: int = 1):
        await self._discord_obj.ban(user, reason=reason, delete_message_days=delete_message_days)

    async def unban(self, user: discord.User, *, reason: Optional[str] = None):
        await self._discord_obj.unban(user, reason=reason)
