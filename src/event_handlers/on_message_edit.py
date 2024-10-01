import discord

from src.db.models.message import MessageUpdate
from src.services.db import Session
from src.services.message import MessageService


async def on_message_edit(before: discord.Message, after: discord.Message):
    """
    Called when a message is edited.

    Args:
        before (discord.Message): The message before the edit.
        after (discord.Message): The message after the edit.
    """
    if after.flags.ephemeral:
        return

    async with Session() as session:
        message_service = MessageService(session)
        await message_service.sync(after)

