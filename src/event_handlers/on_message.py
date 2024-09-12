import random

import discord
from discord.ext.commands import Bot

from src.proxies import LLMProxy
from src.proxies import MessageProxy
from src.services.discord_client import bot


async def on_message(message: discord.Message):
    """
    Called when a message is received.

    Args:
        message (discord.Message): The received message.
    """
    message = await MessageProxy.get_or_create(message)

    if message.author.id == bot.user.id:
        return

    await bot.process_commands(message)

    guild = await message.get_guild()
    channel = await message.get_channel()

    if channel.last_responder_id:
        llm = await LLMProxy.get(channel.last_responder_id)
    else:
        llms = await LLMProxy.get_all(guild.id)
        if not llms:
            return
        llm = random.choice(llms)

    await llm.respond(channel)
