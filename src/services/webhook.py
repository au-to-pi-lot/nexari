import logging
from typing import Optional

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.const import WEBHOOK_NAME, MAX_WEBHOOKS_PER_CHANNEL
from src.db.models.webhook import Webhook
from src.services.channel import AllowedChannelType, ChannelService
from src.services.discord_client import bot

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, webhook_id: int) -> Optional[Webhook]:
        return await self.session.get(Webhook, webhook_id)

    async def create(self, webhook: discord.Webhook) -> Webhook:
        from src.services.channel import ChannelService
        channel_service = ChannelService(self.session)
        await channel_service.get_or_create(webhook.channel)

        db_webhook = Webhook(
            id=webhook.id,
            name=webhook.name,
            token=webhook.token,
            channel_id=webhook.channel_id,
        )
        self.session.add(db_webhook)
        await self.session.commit()
        return db_webhook

    async def get_or_create(self, webhook: discord.Webhook) -> Webhook:
        db_webhook = self.get(webhook.id)
        if db_webhook is None:
            db_webhook = await self.create(webhook)
        return db_webhook

    async def get_by_channel(self, channel_id: int) -> Optional[Webhook]:
        # If channel is a thread, use the parent channel instead
        channel_service = ChannelService(self.session)
        channel = await channel_service.get(channel_id)
        if channel.parent_id is not None:
            channel_id = channel.parent_id

        stmt = select(Webhook).where(Webhook.channel_id == channel_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_by_channel(self, channel: AllowedChannelType) -> Webhook:
        # If channel is a thread, use the parent channel instead
        if hasattr(channel, "parent"):
            channel = channel.parent

        existing_webhooks = await channel.webhooks()
        if len(existing_webhooks) >= MAX_WEBHOOKS_PER_CHANNEL:
            raise ValueError(f"Cannot create new webhook; channel already has maximum number of webhooks ({MAX_WEBHOOKS_PER_CHANNEL})")

        discord_webhook = await channel.create_webhook(name=WEBHOOK_NAME)
        db_webhook = await self.create(discord_webhook)
        return db_webhook

    async def get_or_create_by_channel(self, channel: AllowedChannelType) -> Webhook:
        db_webhook = await self.get_by_channel(channel.id)
        if db_webhook is None:
            db_webhook = await self.create_by_channel(channel)
        return db_webhook

    async def delete(self, *webhooks: Webhook) -> None:
        for webhook in webhooks:
            await self.session.delete(webhook)
        await self.session.commit()

    async def sync(self, discord_webhook: discord.Webhook) -> Optional[Webhook]:
        """
        Synchronize the database webhook with the Discord webhook.

        Args:
            discord_webhook (discord.Webhook): The Discord webhook to sync with.

        Returns:
            Webhook: The updated database Webhook object.
        """
        from src.services.llm import LLMService

        db_webhook = await self.get(discord_webhook.id)

        if db_webhook is not None and db_webhook.name != WEBHOOK_NAME:
            await self.delete(db_webhook)
            db_webhook = None

        if db_webhook is None:
            if await self.is_local_webhook(webhook=discord_webhook):
                logger.warning(f"Owned webhook {discord_webhook.id} not found in database, deleting")

                # TEMPORARY: get the url of the webhook's avatar
                llm_service = LLMService(session=self.session)
                llm = await llm_service.get_by_name(discord_webhook.name, discord_webhook.guild_id)
                if llm is not None and discord_webhook.avatar is not None:
                    llm.avatar_url = discord_webhook.avatar.url
                    await self.session.commit()

                await discord_webhook.delete()

            return None

        # Update webhook properties
        db_webhook.name = discord_webhook.name

        await self.session.commit()

        return db_webhook

    @staticmethod
    async def is_local_webhook(webhook: discord.Webhook) -> bool:
        """Determine whether the webhook was created by this bot."""
        return webhook.user.id == bot.user.id
