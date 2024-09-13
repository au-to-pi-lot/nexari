import logging
import asyncio
from collections import defaultdict

import discord

from src.proxies import LLMProxy, MessageProxy
from src.services.discord_client import bot
from src.simulator import Simulator

logger = logging.getLogger(__name__)

class ChannelQueue:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue(maxsize=1)

channel_queues = defaultdict(ChannelQueue)

async def process_message(message: MessageProxy, channel: 'ChannelProxy', guild: 'GuildProxy'):
    llms = await LLMProxy.get_all(guild.id)
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

    channel_queue = channel_queues[channel.id]

    try:
        channel_queue.queue.put_nowait(message)
    except asyncio.QueueFull:
        logger.info(f"Queue full for channel {channel.id}, ignoring message")
        return

    async with channel_queue.lock:
        while not channel_queue.queue.empty():
            queued_message = await channel_queue.queue.get()
            await process_message(queued_message, channel, guild)
