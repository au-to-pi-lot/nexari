from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models.message import Message, MessageUpdate
from src.services.channel import ChannelService
from src.services.discord_client import bot
from src.services.user import UserService
from src.services.webhook import WebhookService


class MessageService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, message_id: int) -> Optional[Message]:
        return await self.session.get(Message, message_id)

    async def create(self, message: discord.Message) -> Message:
        channel_service = ChannelService(self.session)
        await channel_service.get_or_create(message.channel)

        is_webhook = message.webhook_id is not None
        if is_webhook:
            webhook_service = WebhookService(self.session)
            webhook = await webhook_service.get(message.webhook_id)
            # webhook might be None, if it's from a foreign webhook source, e.g., pluralkit
        else:
            user_service = UserService(self.session)
            await user_service.get_or_create(message.author)

        channel_service = ChannelService(self.session)
        await channel_service.get_or_create(message.channel)

        db_message = Message(
            id=message.id,
            content=message.content,
            user_id=message.author.id if not is_webhook else None,
            webhook_id=(
                message.webhook_id if is_webhook and webhook is not None else None
            ),
            channel_id=message.channel.id,
            created_at=message.created_at,
        )
        self.session.add(db_message)
        await self.session.commit()
        return db_message

    async def update(self, message: Message, update_data: MessageUpdate) -> Message:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(message, key, value)
        await self.session.commit()
        return message

    async def delete(self, message: Message) -> None:
        await self.session.delete(message)
        await self.session.commit()

    async def get_by_channel(self, channel_id: int, limit: int = 100) -> List[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_or_create(self, message: discord.Message) -> Message:
        db_message = await self.get(message.id)
        if not db_message:
            db_message = await self.create(message)
        return db_message

    async def history(self, channel_id: int, limit: int = 100) -> List[Message]:
        """
        Retrieve the n most recent messages in a channel in chronological order.

        Args:
            channel_id (int): The ID of the channel to retrieve messages from.
            limit (int): The maximum number of messages to retrieve. Defaults to 100.

        Returns:
            List[Message]: A list of Message objects, ordered from oldest to newest.
        """
        stmt = (
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        messages = result.scalars().all()
        return list(reversed(messages))  # Reverse to get chronological order

    async def sync(self, discord_message: discord.Message) -> Message:
        """
        Synchronize the database message with the Discord message.

        Args:
            discord_message (discord.Message): The Discord message to sync with.

        Returns:
            Message: The updated database Message object.
        """
        db_message = await self.get(discord_message.id)
        if db_message is None:
            db_message = await self.create(discord_message)
        else:
            # Update message properties
            db_message.content = discord_message.content
            db_message.created_at = discord_message.created_at
            await self.session.commit()

        return db_message

    async def author_name(self, message: Message) -> str:
        if message.from_user:
            user_service = UserService(self.session)
            user = await user_service.get(message.user_id)
            return user.name
        elif message.from_webhook:
            webhook_service = WebhookService(self.session)
            webhook = await webhook_service.get(message.webhook_id)
            return webhook.name
        else:
            channel = await bot.get_channel(message.channel_id)
            discord_message = await channel.fetch_message(message.id)
            return discord_message.author.name

    async def jump_url(self, message: Message) -> str:
        channel_service = ChannelService(self.session)
        channel = await channel_service.get(message.channel_id)
        return f'https://discord.com/channels/{channel.guild_id}/{message.channel_id}/{message.id}'
