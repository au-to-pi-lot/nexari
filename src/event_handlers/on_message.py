import logging
import asyncio
from collections import defaultdict

import discord

from src.proxies import LLMProxy, MessageProxy
from src.services.discord_client import bot
from src.simulator import Simulator

logger = logging.getLogger(__name__)

channel_locks = defaultdict(asyncio.Lock)



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

    lock = channel_locks[channel.id]
    if lock.locked():
        return

    async with lock:
        llms = await LLMProxy.get_all(guild.id)

        # Set to keep track of which LLMs have been pinged in this message
        pinged_llms: set[LLMProxy] = set()

        for llm in llms:
            if await llm.mentioned_in_message(message):
                pinged_llms.add(llm)
                logger.info(f"Pinged {llm.name}")

        if pinged_llms:
            for llm in pinged_llms:
                await llm.respond(channel)
        else:
            llm = await Simulator.get_next_participant(channel)
            if llm is not None:
                await llm.respond(channel)
