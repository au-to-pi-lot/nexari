import discord
from src.proxies.message import MessageProxy


async def on_message_delete(message: discord.Message):
    """
    Called when a message is deleted.

    Args:
        message (discord.Message): The deleted message.
    """
    await MessageProxy.delete_by_id(message.id)

