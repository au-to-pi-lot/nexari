import re
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Message, LLM
from src.services.message import MessageService
from src.types.litellm_message import LiteLLMMessage
from src.types.message_formatter import InstructMessageFormatter, ParseResponse


class GeminiMessageFormatter(InstructMessageFormatter):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def format_instruct(
        self,
        llm: LLM,
        messages: List[Message],
        system_prompt: Optional[str],
    ) -> List[LiteLLMMessage]:
        message_service = MessageService(self.session)

        formatted_messages: List[LiteLLMMessage] = []
        if system_prompt is not None:
            formatted_messages.append(
                LiteLLMMessage(role="user", content=system_prompt)
            )

        current_role = "user"
        current_content = []

        messages = [message for message in messages if message.content]

        for message in messages:
            username = await message_service.author_name(message)

            if (
                message.llm_id and message.llm_id == llm.id
            ):  # If the message is from Gemini
                if current_role == "user":
                    if current_content:
                        formatted_messages.append(
                            LiteLLMMessage(
                                role="assistant",
                                content="<chat_log>\n"
                                + "\n".join(current_content)
                                + "\n</chat_log>",
                            )
                        )
                        current_content = []
                    current_role = "assistant"
                formatted_messages.append(
                    LiteLLMMessage(role="assistant", content=message.content)
                )
            else:
                if current_role == "assistant":
                    current_role = "user"
                content = f"<msg username='{username}'>\n\t{message.content}\n</msg>"
                current_content.append(content)

        if current_content:
            formatted_messages.append(
                LiteLLMMessage(
                    role=current_role,
                    content="<chat_log>\n"
                    + "\n".join(current_content)
                    + "\n</chat_log>",
                )
            )

        formatted_messages.append(
            LiteLLMMessage(role="user", content=f'<msg username="{llm.name}">')
        )

        return formatted_messages

    async def parse_messages(self, response: str) -> ParseResponse:
        # Remove the closing </msg> tag if present
        response = re.sub(r"</msg>", "", response)

        return ParseResponse(
            complete_message=response,
            split_messages=self.break_messages(response),
            username=None,
        )
