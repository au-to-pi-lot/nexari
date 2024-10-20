import logging
import asyncio
from collections import defaultdict
from typing import Optional

import discord
from discord import TextChannel, ForumChannel

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

    async with Session() as session:
        guild_service = GuildService(session)
        db_guild = await guild_service.get_or_create(guild)

        # Ignore messages from the simulator dump channel
        if db_guild.simulator_channel_id == channel.id:
            return

        message_service = MessageService(session)
        await message_service.create(message)

        llm_service = LLMService(session)
        llms = await llm_service.get_by_guild(guild.id)

        channel_queue = channel_queues[channel.id]

        replied_to_webhook_id: Optional[int] = None
        if message.reference is not None and message.reference.message_id is not None:
            other_msg_id: int = message.reference.message_id
            other_msg = await channel.fetch_message(other_msg_id)
            if other_msg.webhook_id:
                replied_to_webhook_id = other_msg.webhook_id

        pinged_llms: set[LLM] = set()
        for llm in llms:
            webhook = await llm_service.get_or_create_webhook(llm, channel)
            if replied_to_webhook_id and replied_to_webhook_id == webhook.id:
                pinged_llms.add(llm)
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
