import logging
import re
from typing import List, Optional
from pydantic import BaseModel

from discord import NotFound
import aiohttp
from typing import Dict, Any
from regex import regex

from src.config import config
from src.proxies import ChannelProxy, LLMProxy
from src.services.discord_client import bot

logger = logging.getLogger(__name__)


class MessageData(BaseModel):
    username: str
    content: str


class Simulator:
    def __init__(self):
        pass

    @classmethod
    def extract_usernames(cls, response_str: str) -> List[str]:
        matches = regex.finditer(
            r"^<(?P<username>[^>]+)>",
            response_str,
            flags=re.MULTILINE,
        )
        return [match.group("username") for match in matches]

    @classmethod
    async def get_next_participant(cls, channel: ChannelProxy) -> Optional[LLMProxy]:
        messages = []
        message_data_list: List[MessageData] = []

        guild = await channel.get_guild()
        llms_in_guild = await guild.get_llms()

        if not llms_in_guild:
            return None

        for llm in llms_in_guild:
            messages.append(f"* {llm.name} joined")

        history = await channel.history(limit=100)
        for message in reversed(history):
            if not message.content:
                continue

            if message.webhook_id:
                try:
                    msg_webhook = await bot.fetch_webhook(message.webhook_id)
                except NotFound:
                    continue
                username = msg_webhook.name
            else:
                username = message.author.name

            matches = re.finditer(r"<@(?P<user_id>\d+)>", message.content)

            message_replaced_mentions = message.content
            for match in matches:
                user_id = match.group("user_id")
                try:
                    user = await bot.fetch_user(user_id)
                    message_replaced_mentions = message_replaced_mentions.replace(
                        f"<@{user_id}>", f"@{user.name}"
                    )
                except NotFound:
                    continue

            message_data_list.append(MessageData(username=username, content=message_replaced_mentions))

        # Get the last speaker from the collected data
        last_speaker = message_data_list[-1].username if message_data_list else None

        # Transform message_data_list to strings
        messages.extend([f"<{data.username}> {data.content}" for data in message_data_list])

        prompt = "\n\n\n".join(messages) + "\n\n\n"

        logger.info(f"Simulating conversation in #{channel.name}...")
        response = await cls.generate_raw_response(prompt=prompt)
        response_str = response["choices"][0]["text"]

        logger.info(f"Received simulator response: {response_str}")

        # Send raw simulator response to the designated channel if set
        guild = await channel.get_guild()
        if guild.simulator_channel_id:
            simulator_channel = await ChannelProxy.get(guild.simulator_channel_id)
            if simulator_channel:
                await simulator_channel.send(f"{channel.mention}:\n```\n{response_str}\n```")

        usernames = cls.extract_usernames(response_str)

        if not usernames:
            logger.info("No usernames found in the response")
            return None

        # Find the first username that's different from the last speaker
        next_speaker = next((username for username in usernames if username != last_speaker), None)

        if next_speaker is None:
            logger.info("No new speaker found in the response")
            return None

        return await LLMProxy.get_by_name(next_speaker, channel.guild.id)

    @classmethod
    async def generate_raw_response(cls, prompt: str) -> Dict[str, Any]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "meta-llama/llama-3.1-405b",
            "prompt": prompt,
            "max_tokens": 256,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Error {response.status}: {await response.text()}")
