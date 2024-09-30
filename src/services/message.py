from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models.message import Message, MessageCreate, MessageUpdate
from src.services.channel import ChannelService
from src.services.thread import ThreadService
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

        is_thread = message.thread is not None
        if is_thread:
            thread_service = ThreadService(self.session)
            await thread_service.get_or_create(message.thread)
        else:
            channel_service = ChannelService(self.session)
            await channel_service.get_or_create(message.channel)

        db_message = Message(
            id=message.id,
            content=message.content,
            user_id=message.author.id if not is_webhook else None,
            webhook_id=message.webhook_id if is_webhook and webhook is not None else None,
            channel_id=message.channel.id if not is_thread else None,
            thread_id=message.thread.id if is_thread else None,
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
