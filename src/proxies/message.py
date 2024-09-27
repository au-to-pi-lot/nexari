from typing import Optional, Self, TYPE_CHECKING, Union
import logging

import discord
from sqlalchemy import select
import sqlalchemy

from src.db.models.message import Message
from src.db.models import User, Channel, Guild, Webhook
from src.proxies.guild import GuildProxy
from src.services.db import Session
from src.services.discord_client import bot
from src.types.proxy import BaseProxy

if TYPE_CHECKING:
    from src.proxies import ChannelProxy, UserProxy, WebhookProxy

logger = logging.getLogger(__name__)


class MessageProxy(BaseProxy[discord.Message, Message]):
    def __init__(self, discord_message: discord.Message, db_message: Message):
        super().__init__(discord_message, db_message)

    @staticmethod
    async def ensure_linked_tables_exist():
        async with Session() as session:
            # Ensure Guilds exist
            discord_guilds = bot.guilds
            db_guilds = (await session.execute(select(Guild))).scalars().all()
            db_guild_ids = {guild.id for guild in db_guilds}

            for discord_guild in discord_guilds:
                if discord_guild.id not in db_guild_ids:
                    new_guild = Guild(id=discord_guild.id)
                    session.add(new_guild)

            # Ensure Channels exist
            discord_channels = [
                channel
                for guild in bot.guilds
                for channel in guild.channels
                if isinstance(channel, discord.TextChannel)
            ]
            db_channels = (await session.execute(select(Channel))).scalars().all()
            db_channel_ids = {channel.id for channel in db_channels}

            for discord_channel in discord_channels:
                if discord_channel.id not in db_channel_ids:
                    new_channel = Channel(
                        id=discord_channel.id, guild_id=discord_channel.guild.id
                    )
                    session.add(new_channel)

            # Ensure Users exist
            for guild in bot.guilds:
                async for member in guild.fetch_members(limit=None):
                    db_user = await session.get(User, member.id)
                    if db_user is None:
                        new_user = User(
                            id=member.id,
                            name=member.name,
                            discriminator=member.discriminator,
                        )
                        session.add(new_user)

            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                await session.rollback()
                logger.error(
                    "Failed to ensure linked tables exist due to integrity error"
                )

    @classmethod
    async def get(cls, identifier: int) -> Optional[Self]:
        async with Session() as session:
            db_message = (
                await session.scalars(select(Message).filter(Message.id == identifier))
            ).one_or_none()
            if db_message is None:
                return None

            discord_message = await bot.get_channel(
                db_message.channel_id
            ).fetch_message(db_message.id)

            return cls(discord_message, db_message)

    async def save(self) -> None:
        async with Session() as session:
            session.add(self._db_obj)
            await session.commit()

    @classmethod
    async def create(cls, discord_message: discord.Message) -> Optional[Self]:
        async with Session() as session:
            is_webhook = discord_message.webhook_id is not None
            
            # Check if channel exists in the database, if not create it
            db_channel = await session.get(Channel, discord_message.channel.id)
            if not db_channel:
                db_guild = await session.get(Guild, discord_message.guild.id)
                if not db_guild:
                    db_guild = Guild(id=discord_message.guild.id, name=discord_message.guild.name)
                    session.add(db_guild)
                db_channel = Channel(id=discord_message.channel.id, guild_id=discord_message.guild.id)
                session.add(db_channel)

            if is_webhook:
                db_webhook = await session.get(Webhook, discord_message.webhook_id)
                if not db_webhook:
                    # Create a placeholder webhook if it doesn't exist
                    db_webhook = Webhook(id=discord_message.webhook_id, channel_id=discord_message.channel.id)
                    session.add(db_webhook)
                db_message = Message(
                    id=discord_message.id,
                    content=discord_message.content,
                    webhook_id=discord_message.webhook_id,
                    channel_id=discord_message.channel.id,
                    created_at=discord_message.created_at,
                )
            else:
                db_user = await session.get(User, discord_message.author.id)
                if not db_user:
                    # Create a new user if it doesn't exist
                    db_user = User(
                        id=discord_message.author.id,
                        name=discord_message.author.name,
                        discriminator=discord_message.author.discriminator,
                    )
                    session.add(db_user)
                db_message = Message(
                    id=discord_message.id,
                    content=discord_message.content,
                    user_id=discord_message.author.id,
                    channel_id=discord_message.channel.id,
                    created_at=discord_message.created_at,
                )

            session.add(db_message)
            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                await session.rollback()
                logger.error(
                    f"Failed to create message {discord_message.id} due to integrity error"
                )
                return None

        return cls(discord_message, db_message)

    @property
    def webhook_id(self) -> Optional[int]:
        return self._discord_obj.webhook_id

    @property
    def content(self) -> str:
        return self._discord_obj.content

    @property
    def author(self) -> Union[discord.User, discord.Member, discord.WebhookMessage.author]:
        return self._discord_obj.author

    @property
    def reference(self) -> Optional[discord.MessageReference]:
        return self._discord_obj.reference

    async def get_author(self) -> Union["UserProxy", "WebhookProxy"]:
        if self._db_obj.webhook_id is not None:
            from src.proxies import WebhookProxy
            return await WebhookProxy.get(self._db_obj.webhook_id)
        else:
            from src.proxies import UserProxy
            return await UserProxy.get(self._db_obj.user_id)

    async def edit(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self._db_obj, key):
                setattr(self._db_obj, key, value)
        if "content" in kwargs:
            self._db_obj.content = kwargs["content"]
        await self.save()

    async def delete(self) -> None:
        async with Session() as session:
            await session.delete(self._db_obj)
            await session.commit()
        self._db_obj = None

    async def get_guild(self) -> GuildProxy:
        return await GuildProxy.get(self._discord_obj.guild.id)

    async def get_channel(self) -> "ChannelProxy":
        from src.proxies.channel import ChannelProxy
        return await ChannelProxy.get(self._discord_obj.channel.id)

    @classmethod
    async def get_or_create(cls, discord_message: discord.Message) -> Self:
        async with Session() as session:
            db_message = await session.get(Message, discord_message.id)
            if db_message is None:
                return await cls.create(discord_message)
            return cls(discord_message, db_message)
