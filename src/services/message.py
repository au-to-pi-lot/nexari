from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models.message import Message, MessageCreate, MessageUpdate

class MessageService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_message(self, message_id: int) -> Optional[Message]:
        return await self.session.get(Message, message_id)

    async def create_message(self, message_data: MessageCreate) -> Message:
        message = Message(**message_data.dict())
        self.session.add(message)
        await self.session.commit()
        return message

    async def update_message(self, message: Message, update_data: MessageUpdate) -> Message:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(message, key, value)
        await self.session.commit()
        return message

    async def delete_message(self, message: Message) -> None:
        await self.session.delete(message)
        await self.session.commit()

    async def get_messages_for_channel(self, channel_id: int, limit: int = 100) -> List[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_or_create_message(self, message_id: int, message_data: MessageCreate) -> Message:
        message = await self.get_message(message_id)
        if not message:
            message = await self.create_message(message_data)
        return message
