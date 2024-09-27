import logging
from typing import Optional, Self, TYPE_CHECKING

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sqlalchemy

from src.db.models import Webhook as DBWebhook, Channel, LLM, Guild
from src.services.db import Session
from src.services.discord_client import bot
from src.types.proxy import BaseProxy

if TYPE_CHECKING:
    from src.proxies.llm import LLMProxy

logger = logging.getLogger(__name__)


class WebhookProxy(BaseProxy[discord.Webhook, DBWebhook]):
    def __init__(self, discord_webhook: discord.Webhook, db_webhook: DBWebhook):
        super().__init__(discord_webhook, db_webhook)

    @staticmethod
    async def ensure_linked_tables_exist():
        async with Session() as session:
            # Ensure Channels exist
            discord_channels = [channel for guild in bot.guilds for channel in guild.channels if isinstance(channel, discord.TextChannel)]
            db_channels = (await session.execute(select(Channel))).scalars().all()
            db_channel_ids = {channel.id for channel in db_channels}
            
            for discord_channel in discord_channels:
                if discord_channel.id not in db_channel_ids:
                    new_channel = Channel(id=discord_channel.id, guild_id=discord_channel.guild.id)
                    session.add(new_channel)

            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                await session.rollback()
                logger.error("Failed to ensure linked tables exist due to integrity error")

    @classmethod
    async def get(cls, identifier: int) -> Optional["WebhookProxy"]:
        async with Session() as session:
            db_webhook = await session.get(DBWebhook, identifier)
            if not db_webhook:
                return None

        discord_webhook = await bot.fetch_webhook(identifier)
        if not discord_webhook:
            return None

        return cls(discord_webhook, db_webhook)

    @classmethod
    async def create(cls, channel: discord.TextChannel, name: str, **kwargs) -> Optional[Self]:
        discord_webhook = await channel.create_webhook(name=name, **kwargs)

        async with Session() as session:
            # Check if channel exists in the database, if not create it
            db_channel = await session.get(Channel, channel.id)
            if not db_channel:
                db_guild = await session.get(Guild, channel.guild.id)
                if not db_guild:
                    db_guild = Guild(id=channel.guild.id)
                    session.add(db_guild)
                db_channel = Channel(id=channel.id, guild_id=channel.guild.id)
                session.add(db_channel)

            # Check if LLM exists in the database, if not create a placeholder
            llm_id = kwargs.get("llm_id")
            if llm_id:
                db_llm = await session.get(LLM, llm_id)
                if not db_llm:
                    db_llm = LLM(id=llm_id, name="Placeholder LLM", guild_id=channel.guild.id)
                    session.add(db_llm)

            db_webhook = DBWebhook(
                id=discord_webhook.id,
                token=discord_webhook.token,
                channel_id=channel.id,
                llm_id=llm_id,
            )

            session.add(db_webhook)
            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                await session.rollback()
                logger.error(f"Failed to create webhook {discord_webhook.id} due to integrity error")
                await discord_webhook.delete()
                return None

        return cls(discord_webhook, db_webhook)

    async def save(self):
        async with Session() as session:
            session.add(self._db_obj)
            await session.commit()

    @property
    def id(self) -> int:
        return self._discord_obj.id

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
        async with Session() as session:
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

    async def get_llm(self) -> "LLMProxy":
        """
        Retrieve the LLMProxy associated with this webhook.

        Returns:
            Optional[LLMProxy]: The associated LLMProxy, or None if not found.
        """
        from src.proxies.llm import LLMProxy

        return await LLMProxy.get(self._db_obj.llm_id)
