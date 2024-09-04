from typing import Optional

import discord
from discord.ext.commands import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Webhook as DBWebhook
from src.services import svc
from src.types.proxy import BaseProxy


class WebhookProxy(BaseProxy[discord.Webhook, DBWebhook]):
    def __init__(self, discord_webhook: discord.Webhook, db_webhook: DBWebhook):
        super().__init__(discord_webhook, db_webhook)

    @classmethod
    async def get(cls, identifier: int, *, llm_id: int = None) -> Optional["WebhookProxy"]:
        bot: Bot = await svc.get(Bot)
        Session: type[AsyncSession] = svc.get(type[AsyncSession])
        discord_webhook = await bot.fetch_webhook(identifier)
        if not discord_webhook:
            return None

        async with Session() as session:
            db_webhook = await session.get(DBWebhook, identifier)
            if not db_webhook:
                db_webhook = DBWebhook(
                    id=identifier,
                    token=discord_webhook.token,
                    channel_id=discord_webhook.channel_id,
                    llm_id=llm_id
                )
                session.add(db_webhook)
                await session.commit()

        return cls(discord_webhook, db_webhook)

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
