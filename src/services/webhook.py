from typing import Optional, List
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from src.db.models.webhook import Webhook, WebhookCreate
from src.db.models.channel import Channel
from src.db.models.guild import Guild
from src.services.discord_client import bot

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_webhook(self, webhook_id: int) -> Optional[Webhook]:
        return await self.session.get(Webhook, webhook_id)

    async def get_webhook_for_channel_and_llm(self, channel_id: int, llm_id: int) -> Optional[Webhook]:
        stmt = select(Webhook).where(
            and_(Webhook.channel_id == channel_id, Webhook.llm_id == llm_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_webhook(self, webhook_data: WebhookCreate) -> Webhook:
        webhook = Webhook(**webhook_data.dict())
        self.session.add(webhook)
        await self.session.commit()
        return webhook

    async def delete_webhook(self, webhook: Webhook) -> None:
        await self.session.delete(webhook)
        await self.session.commit()

    async def get_or_create_webhook(self, channel_id: int, llm_id: int, name: str) -> Webhook:
        webhook = await self.get_webhook_for_channel_and_llm(channel_id, llm_id)
        if webhook:
            return webhook

        # Fetch the channel to ensure it exists
        channel = await self.session.get(Channel, channel_id)
        if not channel:
            guild = await self.session.get(Guild, channel.guild_id)
            if not guild:
                raise ValueError(f"Guild for channel {channel_id} not found")
            channel = Channel(id=channel_id, guild_id=guild.id)
            self.session.add(channel)

        # Create Discord webhook
        discord_channel = bot.get_channel(channel_id)
        if not discord_channel:
            raise ValueError(f"Discord channel {channel_id} not found")
        
        discord_webhook = await discord_channel.create_webhook(name=name)

        # Create database webhook
        webhook_data = WebhookCreate(
            id=discord_webhook.id,
            token=discord_webhook.token,
            channel_id=channel_id,
            llm_id=llm_id
        )
        return await self.create_webhook(webhook_data)

    async def cleanup_duplicate_webhooks(self):
        # Find duplicates
        stmt = select(Webhook.channel_id, Webhook.llm_id).group_by(Webhook.channel_id, Webhook.llm_id).having(sqlalchemy.func.count() > 1)
        result = await self.session.execute(stmt)
        duplicates = result.fetchall()

        for channel_id, llm_id in duplicates:
            webhooks = await self.session.execute(
                select(Webhook)
                .where(Webhook.channel_id == channel_id, Webhook.llm_id == llm_id)
                .order_by(Webhook.id)
            )
            webhooks = webhooks.scalars().all()

            # Keep the first one, delete the rest
            for webhook in webhooks[1:]:
                await self.delete_webhook(webhook)
                # Also delete the Discord webhook if it exists
                try:
                    discord_webhook = await bot.fetch_webhook(webhook.id)
                    await discord_webhook.delete()
                except discord.NotFound:
                    pass

        await self.session.commit()
