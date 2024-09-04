from typing import Optional, Union, List

import discord
from discord.ext.commands import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Channel as DBChannel
from src.services import svc
from src.types.proxy import BaseProxy
from src.proxies.message import MessageProxy


class ChannelProxy(BaseProxy[discord.TextChannel, DBChannel]):
    def __init__(self, discord_channel: discord.TextChannel, db_channel: DBChannel):
        super().__init__(discord_channel, db_channel)

    @classmethod
    async def get(cls, identifier: int) -> Optional["ChannelProxy"]:
        bot: Bot = await svc.get(Bot)
        discord_channel = bot.get_channel(identifier)
        if not discord_channel or not isinstance(discord_channel, discord.TextChannel):
            return None

        async with svc.get(type[AsyncSession])() as session:
            db_channel = await session.get(DBChannel, identifier)
            if not db_channel:
                db_channel = DBChannel(id=identifier, guild_id=discord_channel.guild.id)
                session.add(db_channel)
                await session.commit()

        return cls(discord_channel, db_channel)

    async def save(self):
        async with svc.get(type[AsyncSession])() as session:
            session.add(self._db_obj)
            await session.commit()

    @property
    def name(self) -> str:
        return self._discord_obj.name

    @property
    def guild(self) -> discord.Guild:
        return self._discord_obj.guild

    async def send(self, content: str = None, **kwargs) -> MessageProxy:
        discord_message = await self._discord_obj.send(content, **kwargs)
        return await MessageProxy.get(discord_message.id)

    async def fetch_message(self, message_id: int) -> MessageProxy:
        discord_message = await self._discord_obj.fetch_message(message_id)
        return await MessageProxy.get(discord_message.id)

    async def purge(self, limit: int = 100, **kwargs) -> List[MessageProxy]:
        discord_messages = await self._discord_obj.purge(limit=limit, **kwargs)
        return [await MessageProxy.get(message.id) for message in discord_messages]

    async def set_permissions(self, target: Union[discord.Role, discord.Member], **permissions):
        await self._discord_obj.set_permissions(target, **permissions)

    async def create_webhook(self, name: str, **kwargs) -> discord.Webhook:
        return await self._discord_obj.create_webhook(name=name, **kwargs)

    async def webhooks(self) -> list[discord.Webhook]:
        return await self._discord_obj.webhooks()

    async def history(self, **kwargs) -> List[MessageProxy]:
        return [await MessageProxy.get(message.id) async for message in self._discord_obj.history(**kwargs)]
