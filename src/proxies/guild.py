import discord
from typing import Optional, List, Sequence, Self

from discord import (
    CategoryChannel,
    ForumChannel,
    Role,
    StageChannel,
    TextChannel,
    VoiceChannel,
)
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from src.db.models import Guild as DBGuild, Guild, LLM
from src.proxies.llm import LLMProxy
from src.types.proxy import BaseProxy
from src.services import svc
from sqlalchemy.ext.asyncio import AsyncSession
from src.bot import DiscordBot


class GuildProxy(BaseProxy[discord.Guild, DBGuild]):
    def __init__(self, discord_guild: discord.Guild, db_guild: DBGuild):
        super().__init__(discord_guild, db_guild)

    @classmethod
    async def get(cls, identifier: int) -> Optional["GuildProxy"]:
        bot = await svc.get(DiscordBot)()
        discord_guild = bot.get_guild(identifier)
        if not discord_guild:
            return None

        async with svc.get(type[AsyncSession])() as session:
            db_guild = await session.get(DBGuild, identifier)
            if not db_guild:
                db_guild = DBGuild(id=identifier, name=discord_guild.name)
                session.add(db_guild)
                await session.commit()

        return cls(discord_guild, db_guild)

    async def save(self):
        async with svc.get(AsyncSession)() as session:
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
    def channels(
        self,
    ) -> Sequence[
        VoiceChannel | StageChannel | ForumChannel | TextChannel | CategoryChannel
    ]:
        return self._discord_obj.channels

    @property
    def roles(self) -> Sequence[Role]:
        return self._discord_obj.roles

    async def get_llms(self) -> Sequence[LLMProxy]:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            guild = (await session.scalars(
                select(Guild).options(selectinload(Guild.llms)).where(Guild.id == self._db_obj.id)
            )).one()
            llm_db_objs = guild.llms
        return [LLMProxy(llm_db_obj) for llm_db_obj in llm_db_objs]

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

    async def ban(
        self,
        user: discord.User,
        reason: Optional[str] = None,
        delete_message_days: int = 1,
    ):
        await self._discord_obj.ban(
            user, reason=reason, delete_message_days=delete_message_days
        )

    async def unban(self, user: discord.User, *, reason: Optional[str] = None):
        await self._discord_obj.unban(user, reason=reason)
