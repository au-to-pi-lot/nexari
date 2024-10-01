from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models.channel import Channel, ChannelUpdate
from src.services.guild import GuildService

AllowedChannelType = (
    discord.TextChannel
    | discord.ForumChannel
    | discord.VoiceChannel
    | discord.StageChannel
    | discord.Thread
)


class ChannelService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, channel_id: int) -> Optional[Channel]:
        return await self.session.get(Channel, channel_id)

    async def create(self, channel: AllowedChannelType) -> Channel:
        guild_service = GuildService(session=self.session)
        await guild_service.get_or_create(channel.guild)
        is_thread = isinstance(channel, discord.Thread)

        db_channel = Channel(
            id=channel.id,
            guild_id=channel.guild.id,
            name=channel.name,
            parent_id=channel.parent.id if is_thread else None,
        )
        self.session.add(db_channel)
        await self.session.commit()
        return db_channel

    async def get_or_create(self, channel: AllowedChannelType) -> Channel:
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
        result = await self.session.execute(
            select(Channel).where(Channel.guild_id == guild_id)
        )
        return list(result.scalars().all())

    async def sync(self, discord_channel: AllowedChannelType) -> Channel:
        """
        Synchronize the database channel with the Discord channel.

        Args:
            discord_channel (discord.abc.GuildChannel): The Discord channel to sync with.

        Returns:
            Channel: The updated database Channel object.
        """
        db_channel = await self.get(discord_channel.id)
        if db_channel is None:
            db_channel = await self.create(discord_channel)
        else:
            # Update channel properties
            db_channel.name = discord_channel.name

            await self.session.commit()

        return db_channel

    @staticmethod
    def is_allowed_channel_type(
        channel: discord.abc.GuildChannel | discord.Thread,
    ) -> bool:
        if isinstance(channel, discord.CategoryChannel):
            return False
        return True

    @staticmethod
    def has_threads(channel: discord.abc.GuildChannel | discord.Thread) -> bool:
        return isinstance(channel, discord.TextChannel) or isinstance(
            channel, discord.ForumChannel
        )
