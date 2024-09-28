import logging
import asyncio
from collections import defaultdict
from typing import Optional

import discord

from src.proxies import ChannelProxy, GuildProxy, LLMProxy, MessageProxy
from src.services.discord_client import bot
from src.simulator import Simulator

logger = logging.getLogger(__name__)

class ChannelQueue:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue(maxsize=1)

channel_queues = defaultdict(ChannelQueue)

async def process_message(message: MessageProxy, channel: 'ChannelProxy', guild: 'GuildProxy'):
    llm = await Simulator.get_next_participant(channel)
    if llm is not None:
        async with channel._discord_obj.typing():
            await llm.respond(channel)

async def on_message(message: discord.Message):
    """
    Called when a message is received.

    Args:
        message (discord.Message): The received message.
    """
    if message.flags.ephemeral:
        return

    if message.author.id == bot.user.id:
        return

    message_proxy = await MessageProxy.get_or_create(message)

    if not message_proxy:
        raise ValueError("")

    if message_proxy.author.id == bot.user.id:
        return

    await bot.process_commands(message)

    guild = await message_proxy.get_guild()
    channel = await message_proxy.get_channel()

    # Ignore messages from the simulator dump channel
    if guild.simulator_channel_id == channel.id:
        return

    llms = await guild.get_llms()

    channel_queue = channel_queues[channel.id]

    replied_to_webhook_id: Optional[int] = None
    if message_proxy.reference and message_proxy.reference.message_id:
        other_msg_id: int = message_proxy.reference.message_id
        other_msg = await channel.fetch_message(other_msg_id)
        if other_msg.webhook_id:
            replied_to_webhook_id = other_msg.webhook_id

    pinged_llms: set[LLMProxy] = set()
    for llm in llms:
        webhook = await llm.get_webhook(channel.id)
        if replied_to_webhook_id and replied_to_webhook_id == webhook.id:
            pinged_llms.add(llm)
        if await llm.mentioned_in_message(message_proxy):
            pinged_llms.add(llm)
            logger.info(f"Pinged {llm.name}")

    if pinged_llms:
        for llm in pinged_llms:
            async with channel._discord_obj.typing():
                await llm.respond(channel)
    else:
        try:
            channel_queue.queue.put_nowait(message_proxy)
        except asyncio.QueueFull:
            logger.info(f"Queue full for channel {channel.id}, ignoring message")
            return

        async with channel_queue.lock:
            while not channel_queue.queue.empty():
                queued_message = await channel_queue.queue.get()
                await process_message(queued_message, channel, guild)
