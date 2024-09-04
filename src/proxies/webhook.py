import logging
from typing import Optional, Self

import discord

from discord.ext.commands import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Webhook as DBWebhook
from src.services import svc
from src.types.proxy import BaseProxy
from src.proxies.llm import LLMProxy

logger = logging.getLogger(__name__)


class WebhookProxy(BaseProxy[discord.Webhook, DBWebhook]):
    def __init__(self, discord_webhook: discord.Webhook, db_webhook: DBWebhook):
        super().__init__(discord_webhook, db_webhook)

    @classmethod
    async def get(cls, identifier: int) -> Optional["WebhookProxy"]:
        bot: Bot = await svc.get(Bot)
        Session: type[AsyncSession] = svc.get(type[AsyncSession])

        async with Session() as session:
            db_webhook = await session.get(DBWebhook, identifier)
            if not db_webhook:
                return None

        discord_webhook = await bot.fetch_webhook(identifier)
        if not discord_webhook:
            return None

        return cls(discord_webhook, db_webhook)

    @classmethod
    async def create(cls, channel: discord.TextChannel, name: str, **kwargs) -> Self:
        discord_webhook = await channel.create_webhook(name=name, **kwargs)
        
        db_webhook = DBWebhook(
            id=discord_webhook.id,
            token=discord_webhook.token,
            channel_id=channel.id,
            llm_id=kwargs.get('llm_id')
        )
        
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
        async with Session() as session:
            session.add(db_webhook)
            await session.commit()
        
        return cls(discord_webhook, db_webhook)

    @classmethod
    async def get_or_create(cls, channel: discord.TextChannel, name: str, **kwargs) -> Self:
        existing_webhooks = await channel.webhooks()
        for webhook in existing_webhooks:
            if webhook.name == name:
                return await cls.get(webhook.id)
        
        return await cls.create(channel, name, **kwargs)

    async def save(self):
        async with svc.get(type[AsyncSession])() as session:
            session.add(self._db_obj)
            await session.commit()

    @property
    def name(self) -> str:
        return self._discord_obj.name

    @property
    def channel(self) -> discord.TextChannel:
        return self._discord_obj.channel

    async def send(self, content: str = None, **kwargs) -> discord.Message:
        return await self._discord_obj.send(content, **kwargs)

    async def delete(self, **kwargs):
        await self._discord_obj.delete(**kwargs)
        async with svc.get(type[AsyncSession])() as session:
            await session.delete(self._db_obj)
            await session.commit()

    async def edit(self, **kwargs):
        await self._discord_obj.edit(**kwargs)
        for key, value in kwargs.items():
            if hasattr(self._db_obj, key):
                setattr(self._db_obj, key, value)
        await self.save()

    async def set_avatar(self, avatar: bytes):
        """
        Set the avatar for this webhook.

        Args:
            avatar (bytes): The avatar image data.

        Raises:
            discord.HTTPException: If setting the avatar fails.
        """
        await self._discord_obj.edit(avatar=avatar)

    async def get_llm(self) -> Optional[LLMProxy]:
        """
        Retrieve the LLMProxy associated with this webhook.

        Returns:
            Optional[LLMProxy]: The associated LLMProxy, or None if not found.
        """
        if self._db_obj.llm_id is None:
            return None
        return await LLMProxy.get(self._db_obj.llm_id)
