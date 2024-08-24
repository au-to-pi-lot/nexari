from typing import List
from datetime import datetime

import discord
from litellm import acompletion
from litellm.types.utils import ModelResponse
from pydantic import BaseModel

from src.config import WebhookConfig
from src.db import get_webhook_info, save_webhook_info

class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """
    role: str
    content: str

class LLMHandler:
    def __init__(self, webhook_config: WebhookConfig):
        self.webhook_config = webhook_config

    async def get_webhook(self, bot: discord.Client, channel: discord.TextChannel) -> discord.Webhook:
        webhook_info = get_webhook_info(self.webhook_config.name)
        if webhook_info:
            webhook_id, webhook_token = webhook_info
            return discord.Webhook.partial(webhook_id, webhook_token, client=bot)
        else:
            new_webhook = await channel.create_webhook(name=self.webhook_config.name)
            save_webhook_info(self.webhook_config.name, new_webhook.id, new_webhook.token)
            print(f"Created new webhook {self.webhook_config.name} in channel {channel.name}")
            return new_webhook

    async def generate_response(self, messages: List[LiteLLMMessage]) -> ModelResponse:
        litellm_config = self.webhook_config.llm
        try:
            sampling_config = litellm_config.sampling
            response = await acompletion(
                model=litellm_config.llm_name,
                messages=messages,
                max_tokens=litellm_config.max_tokens,
                **{key: val for key, val in sampling_config.dict().items() if val is not None},
                api_base=litellm_config.api_base,
                api_key=litellm_config.api_key,
                stop=["<|begin_metadata|>"],
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {str(e)}")
            raise

    def get_system_prompt(self, guild_name: str, channel_name: str) -> str:
        return f"""\
{self.webhook_config.system_prompt}

You are: {self.webhook_config.name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {guild_name}
Current Discord Channel: {channel_name}
"""

    @staticmethod
    def parse_llm_response(content: str) -> str:
        if "<|begin_metadata|>" in content:
            content = content.split("<|begin_metadata|>", 1)[0]
        return content.strip()
