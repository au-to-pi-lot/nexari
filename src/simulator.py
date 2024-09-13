import logging
import re
from typing import List, Optional

from discord import NotFound
from litellm import acompletion
from litellm.types.utils import ModelResponse
from regex import regex

from src.config import config
from src.proxies import ChannelProxy, LLMProxy
from src.services.discord_client import bot
from src.types.litellm_message import LiteLLMMessage

logger = logging.getLogger(__name__)

class Simulator:
    def __init__(self):
        pass

    @classmethod
    async def get_next_participant(cls, channel: ChannelProxy) -> Optional[LLMProxy]:
        history = await channel.history(limit=100)

        messages = []
        for message in reversed(history):
            if not message.content:
                continue

            if message.webhook_id:
                try:
                    msg_webhook = await bot.fetch_webhook(message.webhook_id)
                except NotFound as e:
                    continue
                username = msg_webhook.name
            else:
                username = message.author.name

            role = "user"
            content = f"<{username}> {message.content}"
            messages.append(LiteLLMMessage(role=role, content=content))

        response = await cls.generate_raw_response(messages)
        response_str = response.choices[0].message.content

        logger.info(f"Received simulator response: {response_str}")

        match = regex.search(
            r"^<(?P<username>[^>]+)>",
            response_str,
            flags=re.MULTILINE,
        )

        if not match:
            logger.info(f'No match for username ')
            return None

        username = match.group("username")

        return await LLMProxy.get_by_name(username, channel.guild.id)

    @classmethod
    async def generate_raw_response(
        cls, messages: List[LiteLLMMessage]
    ) -> ModelResponse:
        response = await acompletion(
            model="openrouter/meta-llama/llama-3.1-405b",
            messages=messages,
            max_tokens=256,
            api_base="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key,
            stop=[],
        )
        return response
