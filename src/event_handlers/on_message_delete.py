import discord
from src.proxies.message import MessageProxy


async def on_message_delete(message: discord.Message):
    """
    Called when a message is deleted.

    Args:
        message (discord.Message): The deleted message.
    """
    message_proxy = await MessageProxy.get(message.id)
    if message_proxy:
        await message_proxy.delete()
