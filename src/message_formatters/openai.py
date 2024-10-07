from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Message
from src.services.discord_client import bot
from src.services.message import MessageService
from src.types.litellm_message import LiteLLMMessage
from src.types.message_formatter import InstructMessageFormatter, ParseResponse


class OpenAIMessageFormatter(InstructMessageFormatter):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def format_instruct(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        webhook: Optional[discord.Webhook],
    ) -> List[LiteLLMMessage]:
        message_service = MessageService(self.session)

        formatted_messages: List[LiteLLMMessage] = []
        if system_prompt is not None:
            formatted_messages.append(
                LiteLLMMessage(role="system", content=system_prompt)
            )

        for message in messages:
            if not message.content:
                continue

            name = await message_service.author_name(message)

            if message.webhook_id:
                try:
                    msg_webhook = await bot.fetch_webhook(message.webhook_id)
                except discord.NotFound:
                    continue
                role = (
                    "assistant"
                    if webhook is not None and msg_webhook.id == webhook.id
                    else "user"
                )
            else:
                role = "user"

            formatted_messages.append(
                LiteLLMMessage(role=role, content=message.content, name=name)
            )

        return formatted_messages

    async def parse_messages(self, response: str) -> ParseResponse:
        messages_to_send = self.break_messages(response)

        return ParseResponse(
            complete_message=response,
            split_messages=messages_to_send,
            username=None,  # OpenAI doesn't use usernames in the same way as IRC
        )
