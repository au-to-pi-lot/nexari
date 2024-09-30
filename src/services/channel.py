from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models.channel import Channel, ChannelUpdate
from src.services.guild import GuildService


class ChannelService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, channel_id: int) -> Optional[Channel]:
        return await self.session.get(Channel, channel_id)

    async def create(self, channel: discord.abc.GuildChannel) -> Channel:
        guild_service = GuildService(session=self.session)
        await guild_service.get_or_create(channel.guild)

        db_channel = Channel(
            id=channel.id,
            guild_id=channel.guild.id
        )
        self.session.add(db_channel)
        await self.session.commit()
        return db_channel

    async def get_or_create(self, channel: discord.TextChannel) -> Channel:
        db_channel = await self.get(channel.id)
        if db_channel is None:
            db_channel = await self.create(channel)

        return db_channel

    async def update(self, channel: Channel, update_data: ChannelUpdate) -> Channel:
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

    async def sync(self, discord_channel: discord.TextChannel) -> Channel:
        """
        Synchronize the database channel with the Discord channel.

        Args:
            discord_channel (discord.TextChannel): The Discord channel to sync with.

        Returns:
            Channel: The updated database Channel object.
        """
        db_channel = await self.get(discord_channel.id)
        if db_channel is None:
            db_channel = await self.create(discord_channel)
        else:
            # Update channel properties
            db_channel.name = discord_channel.name
            db_channel.position = discord_channel.position
            db_channel.category_id = discord_channel.category_id
            db_channel.is_nsfw = discord_channel.is_nsfw()
            db_channel.slowmode_delay = discord_channel.slowmode_delay
            db_channel.topic = discord_channel.topic
            
            # Update permissions if needed
            # This is a simplified example, you might want to implement a more detailed permission sync
            db_channel.default_auto_archive_duration = discord_channel.default_auto_archive_duration
            
            await self.session.commit()

        return db_channel
