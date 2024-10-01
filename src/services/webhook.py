import logging
from typing import Optional

import discord
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models import LLM
from src.db.models.webhook import Webhook
from src.services.channel import ChannelService

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, webhook_id: int) -> Optional[Webhook]:
        return await self.session.get(Webhook, webhook_id)

    async def get_by_llm_channel(
        self, channel_id: int, llm_id: int
    ) -> Optional[Webhook]:
        stmt = select(Webhook).where(
            and_(Webhook.channel_id == channel_id, Webhook.llm_id == llm_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, webhook: discord.Webhook, llm: LLM) -> Webhook:
        channel_service = ChannelService(self.session)
        await channel_service.get_or_create(webhook.channel)

        db_webhook = Webhook(
            id=webhook.id,
            token=webhook.token,
            channel_id=webhook.channel_id,
            llm_id=llm.id,
        )
        self.session.add(db_webhook)
        await self.session.commit()
        return db_webhook

    async def delete(self, webhook: Webhook) -> None:
        await self.session.delete(webhook)
        await self.session.commit()

    async def get_or_create(self, webhook: discord.Webhook, llm: LLM) -> Webhook:
        db_webhook = self.get(webhook.id)
        if db_webhook is None:
            db_webhook = await self.create(webhook, llm)
        return db_webhook
