from typing import Optional, TYPE_CHECKING, Union, List
import logging

import discord
from discord.ext.commands import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sqlalchemy

from src.db.models import Channel, Guild
from src.services.db import Session
from src.services.discord_client import bot
from src.types.proxy import BaseProxy
from src.proxies.message import MessageProxy

if TYPE_CHECKING:
    from src.proxies import GuildProxy

logger = logging.getLogger(__name__)


class ChannelProxy(BaseProxy[discord.TextChannel, Channel]):
    def __init__(self, discord_channel: discord.TextChannel, db_channel: Channel):
        super().__init__(discord_channel, db_channel)

    @staticmethod
    async def ensure_linked_tables_exist():
        async with Session() as session:
            # Ensure Guilds exist
            discord_guilds = bot.guilds
            db_guilds = (await session.execute(select(Guild))).scalars().all()
            db_guild_ids = {guild.id for guild in db_guilds}
            
            for discord_guild in discord_guilds:
                if discord_guild.id not in db_guild_ids:
                    new_guild = Guild(id=discord_guild.id)
                    session.add(new_guild)

            # Ensure Channels exist
            discord_channels = [channel for guild in bot.guilds for channel in guild.channels if isinstance(channel, discord.TextChannel)]
            db_channels = (await session.execute(select(Channel))).scalars().all()
            db_channel_ids = {channel.id for channel in db_channels}
            
            for discord_channel in discord_channels:
                if discord_channel.id not in db_channel_ids:
                    new_channel = Channel(id=discord_channel.id, guild_id=discord_channel.guild.id)
                    session.add(new_channel)

            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                await session.rollback()
                logger.error("Failed to ensure linked tables exist due to integrity error")

    @classmethod
    async def get(cls, identifier: int) -> Optional["ChannelProxy"]:
        discord_channel = bot.get_channel(identifier)
        if not discord_channel or not isinstance(discord_channel, discord.TextChannel):
            return None

        async with Session() as session:
            db_channel = await session.get(Channel, identifier)
            if not db_channel:
                # Check if the guild exists in the database, if not create it
                db_guild = await session.get(Guild, discord_channel.guild.id)
                if not db_guild:
                    db_guild = Guild(id=discord_channel.guild.id, name=discord_channel.guild.name)
                    session.add(db_guild)

                db_channel = Channel(id=identifier, guild_id=discord_channel.guild.id)
                session.add(db_channel)
                try:
                    await session.commit()
                except sqlalchemy.exc.IntegrityError:
                    await session.rollback()
                    logger.error(f"Failed to create channel {identifier} due to integrity error")
                    return None

        return cls(discord_channel, db_channel)

    async def save(self):
        async with Session() as session:
            session.add(self._db_obj)
            await session.commit()

    async def edit(self, **kwargs):
        columns = Channel.__table__.columns.keys()
        for key, value in kwargs.items():
            if key in columns:
                setattr(self._db_obj, key, value)

        await self.save()

    @property
    def id(self) -> int:
        return self._discord_obj.id

    @property
    def name(self) -> str:
        return self._discord_obj.name

    @property
    def guild(self) -> discord.Guild:
        return self._discord_obj.guild

    @property
    def mention(self) -> str:
        return self._discord_obj.mention

    async def get_guild(self) -> "GuildProxy":
        from src.proxies import GuildProxy

        return await GuildProxy.get(self._discord_obj.guild.id)

    async def send(self, content: str = None, **kwargs) -> MessageProxy:
        discord_message = await self._discord_obj.send(content, **kwargs)
        return await MessageProxy.get_or_create(discord_message)

    async def fetch_message(self, message_id: int) -> MessageProxy:
        discord_message = await self._discord_obj.fetch_message(message_id)
        return await MessageProxy.get_or_create(discord_message)

    async def set_permissions(
        self, target: Union[discord.Role, discord.Member], **permissions
    ):
        await self._discord_obj.set_permissions(target, **permissions)

    async def create_webhook(self, name: str, **kwargs) -> discord.Webhook:
        return await self._discord_obj.create_webhook(name=name, **kwargs)

    async def webhooks(self) -> list[discord.Webhook]:
        return await self._discord_obj.webhooks()

    async def history(self, **kwargs) -> List[MessageProxy]:
        return [
            await MessageProxy.get_or_create(message)
            async for message in self._discord_obj.history(**kwargs)
            if message.author.id != bot.user.id
        ]
