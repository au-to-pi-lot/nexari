from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models.channel import Channel, ChannelUpdate
from src.db.models.thread import Thread
from src.services.channel import ChannelService


class ThreadService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, thread_id: int) -> Optional[Thread]:
        return await self.session.get(Channel, thread_id)

    async def create(self, thread: discord.Thread) -> Channel:
        channel_service = ChannelService(session=self.session)
        channel = await channel_service.get_or_create(thread.parent)

        db_channel = Channel(
            id=channel.id,
            guild_id=channel.guild.id,
            last_responder_id=None
        )
        self.session.add(db_channel)
        await self.session.commit()
        return db_channel

    async def get_or_create(self, thread: discord.Thread) -> Channel:
        db_thread = await self.get(thread.id)
        if db_thread is None:
            db_thread = await self.create(thread)

        return db_thread

    async def update(self, thread: Thread, update_data: ThreadUpdate) -> Channel:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(channel, key, value)
        await self.session.commit()
        return channel

    async def delete(self, channel: Channel) -> None:
        await self.session.delete(channel)
        await self.session.commit()

    async def get_by_guild(self, guild_id: int) -> List[Channel]:
        result = await self.session.execute(select(Channel).where(Channel.guild_id == guild_id))
        return list(result.scalars().all())
