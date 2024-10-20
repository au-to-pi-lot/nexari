from datetime import datetime, UTC
from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models.channel import Channel, ChannelUpdate


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
        from src.services.guild import GuildService

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

    async def sync(self, discord_channel: AllowedChannelType) -> Optional[Channel]:
        """
        Synchronize the database channel with the Discord channel.

        Args:
            discord_channel (discord.abc.GuildChannel): The Discord channel to sync with.

        Returns:
            Channel: The updated database Channel object, or None if the channel is not of an allowed type.
        """
        from src.services.message import MessageService
        from src.services.webhook import WebhookService

        if not ChannelService.is_allowed_channel_type(discord_channel):
            return None

        db_channel = await self.get_or_create(discord_channel)

        # Update channel properties
        db_channel.name = discord_channel.name
        db_channel.parent_id = (
            discord_channel.parent.id
            if isinstance(discord_channel, discord.Thread)
            else None
        )

        # Update threads
        if ChannelService.has_threads(discord_channel):
            for thread in discord_channel.threads:
                await self.sync(thread)

        # Update webhooks
        if hasattr(discord_channel, "webhooks"):
            webhook_service = WebhookService(session=self.session)
            for webhook in await discord_channel.webhooks():
                await webhook_service.sync(webhook)

        # Update messages
        if hasattr(discord_channel, "history"):
            message_service = MessageService(session=self.session)
            try:
                async for message in discord_channel.history(
                    limit=None, after=db_channel.scanned_up_to, oldest_first=True
                ):
                    await message_service.sync(message)
                    db_channel.scanned_up_to = (
                        max(db_channel.scanned_up_to, message.created_at)
                        if db_channel.scanned_up_to is not None
                        else message.created_at
                    )
            except discord.Forbidden as e:
                pass

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
