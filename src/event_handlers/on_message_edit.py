import discord
from src.proxies.message import MessageProxy


async def on_message_edit(before: discord.Message, after: discord.Message):
    """
    Called when a message is edited.

    Args:
        before (discord.Message): The message before the edit.
        after (discord.Message): The message after the edit.
    """
    if after.flags.ephemeral:
        return

    message_proxy = await MessageProxy.get(after.id)
    if message_proxy:
        await message_proxy.edit(content=after.content)
    else:
        await MessageProxy.create(after)
