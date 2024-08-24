from typing import List, Dict
from datetime import datetime

import discord
from litellm import acompletion
from litellm.types.utils import ModelResponse
from pydantic import BaseModel

from src.config import WebhookConfig, LiteLLMConfig

class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """
    role: str
    content: str

class LLMHandler:
    def __init__(self, webhooks: List[WebhookConfig]):
        self.webhooks: Dict[str, WebhookConfig] = {webhook.name: webhook for webhook in webhooks}
        self.discord_webhooks: Dict[str, discord.Webhook] = {}

    async def setup_webhooks(self, bot: discord.Client):
        for webhook_config in self.webhooks.values():
            channel = bot.get_channel(webhook_config.channel_id)
            if channel:
                webhook = await channel.create_webhook(name=webhook_config.name)
                self.discord_webhooks[webhook_config.name] = webhook
                print(f"Created webhook {webhook_config.name} in channel {channel.name}")
            else:
                print(f"Could not find channel with ID {webhook_config.channel_id}")

    async def generate_response(self, messages: List[LiteLLMMessage], webhook_name: str) -> ModelResponse:
        webhook_config = self.webhooks[webhook_name]
        litellm_config = webhook_config.litellm
        try:
            sampling_config = litellm_config.sampling
            response = await acompletion(
                model=litellm_config.llm_name,
                messages=messages,
                max_tokens=litellm_config.max_tokens,
                **{key: val for key, val in sampling_config if val is not None},
                api_base=litellm_config.api_base,
                api_key=litellm_config.api_key,
                stop=["<|begin_metadata|>"],
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {str(e)}")
            raise

    def get_system_prompt(self, webhook_name: str, guild_name: str, channel_name: str) -> str:
        webhook_config = self.webhooks[webhook_name]
        return f"""\
{webhook_config.system_prompt}

You are: {webhook_name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {guild_name}
Current Discord Channel: {channel_name}
"""

    def get_discord_webhook(self, webhook_name: str) -> discord.Webhook:
        return self.discord_webhooks.get(webhook_name)

    @staticmethod
    def parse_llm_response(content: str) -> str:
        if "<|begin_metadata|>" in content:
            content = content.split("<|begin_metadata|>", 1)[0]
        return content.strip()
