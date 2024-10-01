import discord

from src.services.db import Session
from src.services.message import MessageService


async def on_message_delete(message: discord.Message):
    """
    Called when a message is deleted.

    Args:
        message (discord.Message): The deleted message.
    """
    async with Session() as session:
        message_service = MessageService(session)
        db_message = await message_service.get(message.id)
        await message_service.delete(db_message)

