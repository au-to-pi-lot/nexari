from typing import Optional, Self
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import discord

from src.db.models.message import Message as DBMessage, MessageCreate
from src.services import svc
from src.types.proxy import BaseProxy
from src.proxies.guild import GuildProxy
from src.proxies.channel import ChannelProxy

class MessageProxy(BaseProxy[discord.Message, DBMessage]):
    def __init__(self, discord_message: discord.Message, db_message: DBMessage):
        super().__init__(discord_message, db_message)

    @classmethod
    async def get(cls, identifier: int) -> Optional[Self]:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            db_message = (await session.scalars(select(DBMessage).filter(DBMessage.id == identifier))).one_or_none()
            if db_message is None:
                return None
            
            bot = svc.get(discord.Client)
            discord_message = await bot.get_channel(db_message.channel_id).fetch_message(db_message.id)
            
            return cls(discord_message, db_message)

    async def save(self) -> None:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            session.add(self._db_obj)
            await session.commit()

    @classmethod
    async def create(cls, discord_message: discord.Message) -> Self:
        db_message = DBMessage(
            id=discord_message.id,
            content=discord_message.content,
            author_id=discord_message.author.id,
            channel_id=discord_message.channel.id,
            guild_id=discord_message.guild.id,
            created_at=discord_message.created_at
        )
        
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            session.add(db_message)
            await session.commit()
        
        return cls(discord_message, db_message)

    async def edit(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self._db_obj, key):
                setattr(self._db_obj, key, value)
        if 'content' in kwargs:
            self._db_obj.content = kwargs['content']
        await self.save()

    async def delete(self) -> None:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            await session.delete(self._db_obj)
            await session.commit()
        self._db_obj = None

    async def get_guild(self) -> GuildProxy:
        return await GuildProxy.get(self._discord_obj.guild.id)

    async def get_channel(self) -> ChannelProxy:
        return await ChannelProxy.get(self._discord_obj.channel.id)

    @classmethod
    async def get_or_create(cls, discord_message: discord.Message) -> Self:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
        async with Session() as session:
            db_message = await session.get(DBMessage, discord_message.id)
            if db_message is None:
                db_message = DBMessage(
                    id=discord_message.id,
                    content=discord_message.content,
                    author_id=discord_message.author.id,
                    channel_id=discord_message.channel.id,
                    created_at=discord_message.created_at
                )
                session.add(db_message)
                await session.commit()
        
        return cls(discord_message, db_message)
