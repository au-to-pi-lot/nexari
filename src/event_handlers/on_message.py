import asyncio
import logging
from collections import defaultdict

import discord

from src.db.models import LLM
from src.services.channel import ChannelService
from src.services.db import Session
from src.services.discord_client import bot
from src.services.guild import GuildService
from src.services.llm import LLMService
from src.services.message import MessageService

logger = logging.getLogger(__name__)


class ChannelQueue:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue(maxsize=1)


channel_queues = defaultdict(ChannelQueue)


async def process_message(message: discord.Message):
    async with Session() as session:
        llm_service = LLMService(session)
        llm = await llm_service.get_next_participant(message.channel)
        if llm is not None:
            async with message.channel.typing():

                await llm_service.respond(llm, message.channel)


async def on_message(message: discord.Message):
    """
    Called when a message is received.

    Args:
        message (discord.Message): The received message.
    """
    guild = message.guild
    channel = message.channel

    if not ChannelService.is_allowed_channel_type(channel):
        return
    if message.flags.ephemeral:
        return
    if message.author.id == bot.user.id:
        return
    if guild is None:
        return

    await bot.process_commands(message)

    channel_queue = channel_queues[channel.id]

    async with Session() as session:
        guild_service = GuildService(session)
        message_service = MessageService(session)
        llm_service = LLMService(session)
        db_guild = await guild_service.get_or_create(guild)

        # Ignore messages from the simulator dump channel
        if db_guild.simulator_channel_id == channel.id:
            return

        # Store new message in DB
        await message_service.sync(message)

        llms = await llm_service.get_by_guild(guild.id, enabled=True)
        pinged_llms: set[LLM] = set()

        # Check if the message replies to another message
        if message.reference is not None and message.reference.message_id is not None:
            other_msg_id: int = message.reference.message_id
            replied_to_message = await channel.fetch_message(other_msg_id)
            replied_to_llm = await llm_service.get_by_message(replied_to_message)
            if replied_to_llm is not None:
                pinged_llms.add(replied_to_llm)

        for llm in llms:
            if await llm_service.mentioned_in_message(llm, message):
                pinged_llms.add(llm)
                logger.info(f"Pinged {llm.name}")

        if pinged_llms:
            for llm in pinged_llms:
                async with channel.typing():
                    await llm_service.respond(llm, channel)
        else:
            try:
                channel_queue.queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.info(f"Queue full for channel {channel.id}, ignoring message")
                return

    async with channel_queue.lock:
        while not channel_queue.queue.empty():
            queued_message = await channel_queue.queue.get()
            await process_message(queued_message)
