from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models.channel import Channel, ChannelCreate, ChannelUpdate
from src.db.models.guild import Guild

class ChannelService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_channel(self, channel_id: int) -> Optional[Channel]:
        return await self.session.get(Channel, channel_id)

    async def create_channel(self, channel_data: ChannelCreate) -> Channel:
        channel = Channel(**channel_data.dict())
        self.session.add(channel)
        await self.session.commit()
        return channel

    async def update_channel(self, channel: Channel, update_data: ChannelUpdate) -> Channel:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(channel, key, value)
        await self.session.commit()
        return channel

    async def delete_channel(self, channel: Channel) -> None:
        await self.session.delete(channel)
        await self.session.commit()

    async def get_channels_for_guild(self, guild_id: int) -> List[Channel]:
        result = await self.session.execute(select(Channel).where(Channel.guild_id == guild_id))
        return result.scalars().all()

    async def ensure_channel_exists(self, channel_id: int, guild_id: int) -> Channel:
        channel = await self.get_channel(channel_id)
        if not channel:
            guild = await self.session.get(Guild, guild_id)
            if not guild:
                guild = Guild(id=guild_id)
                self.session.add(guild)
            channel = Channel(id=channel_id, guild_id=guild_id)
            self.session.add(channel)
            await self.session.commit()
        return channel
