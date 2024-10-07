from typing import Optional, List
import re

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Message
from src.services.message import MessageService
from src.types.litellm_message import LiteLLMMessage
from src.types.message_formatter import InstructMessageFormatter, ParseResponse


class GeminiMessageFormatter(InstructMessageFormatter):
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
                LiteLLMMessage(role="user", content=system_prompt)
            )

        current_role = "user"
        current_content = []

        for message in messages:
            if not message.content:
                continue

            username = await message_service.author_name(message)
            content = f"<msg username='{username}'>\n\t{message.content}\n</msg>"

            if message.webhook_id and webhook and message.webhook_id == webhook.id:
                if current_role != "assistant":
                    if current_content:
                        formatted_messages.append(
                            LiteLLMMessage(role=current_role, content="<chat_log>\n" + "\n".join(current_content) + "\n</chat_log>")
                        )
                        current_content = []
                    current_role = "assistant"
            else:
                if current_role != "user":
                    if current_content:
                        formatted_messages.append(
                            LiteLLMMessage(role=current_role, content="<chat_log>\n" + "\n".join(current_content) + "\n</chat_log>")
                        )
                        current_content = []
                    current_role = "user"

            current_content.append(content)

        if current_content:
            formatted_messages.append(
                LiteLLMMessage(role=current_role, content="<chat_log>\n" + "\n".join(current_content) + "\n</chat_log>")
            )

        return formatted_messages

    async def parse_messages(self, response: str) -> ParseResponse:
        # Remove the opening <chat_log> tag if present
        response = re.sub(r'^\s*<chat_log>\s*', '', response)
        
        # Find all message blocks
        message_blocks = re.findall(r'<msg username=[\'"]?(\w+)[\'"]?>\s*(.*?)\s*</msg>', response, re.DOTALL)
        
        if not message_blocks:
            # If no message blocks found, treat the entire response as a single message
            return ParseResponse(
                complete_message=response,
                split_messages=self.break_messages(response),
                username=None
            )
        
        # Process message blocks
        complete_message = ""
        split_messages = []
        username = None
        
        for block_username, block_content in message_blocks:
            if username is None:
                username = block_username
            elif username != block_username:
                # Stop processing if a different username is encountered
                break
            
            complete_message += block_content + "\n"
            split_messages.extend(self.break_messages(block_content))
        
        return ParseResponse(
            complete_message=complete_message.strip(),
            split_messages=split_messages,
            username=username
        )
