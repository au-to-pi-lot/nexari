from itertools import groupby
from typing import List, Union, Iterable
from datetime import datetime

import discord
from litellm import acompletion
from litellm.types.utils import ModelResponse
from pydantic import BaseModel
from sqlalchemy import select

from src.db.engine import Session
from src.db.models import LanguageModel, Webhook


class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """
    role: str
    content: str

class LLMHandler:
    def __init__(self, language_model: LanguageModel):
        self.language_model = language_model

    async def get_webhook(self, bot: discord.Client, channel: discord.TextChannel) -> discord.Webhook:
        async with Session() as session:
            query = select(Webhook).where(channel_id=channel.id, language_model_id=self.language_model.id)
            webhook_model = await session.scalars(query).one_or_none()

            if webhook_model:
                webhook = await discord.Webhook.partial(
                    id=webhook_model.id,
                    token=webhook_model.token,
                    client=bot
                ).fetch()
            else:
                webhook = await channel.create_webhook(name=self.language_model.name)
                session.add(Webhook(
                    id=webhook.id,
                    token=webhook.token,
                    channel_id=channel.id,
                    language_model_id=self.language_model.id,
                ))
                await session.commit()

        return webhook

    async def generate_raw_response(self, messages: List[LiteLLMMessage]) -> ModelResponse:
        try:
            sampling_config = {
                "temperature": self.language_model.temperature,
                "top_p": self.language_model.top_p,
                "top_k": self.language_model.top_k,
                "frequency_penalty": self.language_model.frequency_penalty,
                "presence_penalty": self.language_model.presence_penalty,
                "repetition_penalty": self.language_model.repetition_penalty,
                "min_p": self.language_model.min_p,
                "top_a": self.language_model.top_a,
            }
            response = await acompletion(
                model=self.language_model.model_name,
                messages=messages,
                max_tokens=self.language_model.max_tokens,
                **{key: val for key, val in sampling_config.items() if val is not None},
                api_base=self.language_model.api_base,
                api_key=self.language_model.api_key,
                stop=["<|begin_metadata|>"],
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {str(e)}")
            raise

    def get_system_prompt(self, guild_name: str, channel_name: str) -> str:
        return f"""\
{self.language_model.system_prompt}

You are: {self.language_model.name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {guild_name}
Current Discord Channel: {channel_name}
"""

    @staticmethod
    def parse_llm_response(content: str) -> str:
        if "<|begin_metadata|>" in content:
            content = content.split("<|begin_metadata|>", 1)[0]
        return content.strip()

    async def fetch_message_history(self, bot: discord.Client, channel: Union[discord.TextChannel, discord.DMChannel]) -> List[
        LiteLLMMessage]:
        """
        Fetch message history from a Discord channel.

        Args:
            channel (Union[discord.TextChannel, discord.DMChannel]): The channel to fetch history from.
            bot (discord.Client): The current discord client instance.

        Returns:
            List[LiteLLMMessage]: A list of messages in LiteLLM format.
        """
        discord_history: Iterable[discord.Message] = reversed(
            [
                message
                async for message in channel.history(limit=self.language_model.message_limit)
            ]
        )

        webhook = await self.get_webhook(bot, channel)

        # group adjacent messages from the same user
        # this saves some tokens on repeated metadata
        history = []
        for _, message_group in groupby(discord_history, lambda a: a.author):
            message_group = list(message_group)
            first_message = message_group[0]
            role: str = "assistant" if first_message.webhook_id and first_message.webhook_id == webhook.id else "user"
            msg_content = "\n\n".join((message.content for message in message_group))
            content = f"""\
{msg_content}
<|begin_metadata|>
Author: {first_message.author.display_name + ("" if first_message.author.bot else f" ({first_message.author.name})")}
Author ID: {first_message.author.id}
Sent at: {first_message.created_at}
<|end_metadata|>
"""

            history.append(LiteLLMMessage(role=role, content=content))

        return history

    async def get_response(self, message_history: List[LiteLLMMessage]) -> str:
        """
        Generate a LLM response and post it to a Discord channel using the appropriate webhook.

        Args:
            message_history (List[LiteLLMMessage]): The message history in the channel.

        Returns:
            str: The literal response as generated by the LLM.
        """
        response = await self.generate_raw_response(message_history)
        response_str = response.choices[0].message.content

        content = LLMHandler.parse_llm_response(response_str)

        print(f"{self.language_model.name}: {content}")

        return response_str


