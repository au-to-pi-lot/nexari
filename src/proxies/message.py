from typing import Optional, Self
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import discord

from src.db.models.message import Message as DBMessage
from src.services import svc
from src.types.proxy import BaseProxy

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
        await self.save()

    async def delete(self) -> None:
        Session: type[AsyncSession] = svc.get(type[AsyncSession])()
        async with Session() as session:
            await session.delete(self._db_obj)
            await session.commit()
        self._db_obj = None