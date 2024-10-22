import textwrap
from abc import ABC, abstractmethod
from itertools import cycle
from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.db.models import Message, LLM
from src.types.litellm_message import LiteLLMMessage
from src.util import drop_both_ends


class ParseResponse(BaseModel):
    complete_message: str
    split_messages: list[str]
    username: Optional[str]


class BaseMessageFormatter(ABC):
    """
    Base class for all message formatters.
    Provides common functionality and defines the interface for message formatting.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @abstractmethod
    async def parse_messages(self, response: str) -> ParseResponse:
        """
        Parse a ModelResponse into a list of messages to send to Discord.

        Args:
            response (str): The model's response to parse.

        Returns:
            ParseResponse: The parsed response.
        """
        pass

    @staticmethod
    def break_messages(content: str) -> List[str]:
        """
        Break a long message into smaller chunks that fit within Discord's message limit.

        Args:
            content (str): The content to break into messages.

        Returns:
            List[str]: A list of message chunks.
        """

        class CharBlock(BaseModel):
            content: str
            block_type: Literal["text", "code"]

        char_blocks = (
            CharBlock(content=content, block_type=block_type)
            for content, block_type in zip(
                content.split("```"), cycle(["text", "code"])
            )
            if content
        )

        blocks = []
        for block in char_blocks:
            if block.block_type == "text":
                block.content = block.content.strip()
                if block:
                    blocks.append(block)
            else:
                blocks.append(block)

        messages = []
        for block in blocks:
            if block.block_type == "text":
                messages.extend(
                    [
                        nonempty_message
                        for paragraph in block.content.split("\n\n")
                        for message in textwrap.wrap(
                            paragraph,
                            width=DISCORD_MESSAGE_MAX_CHARS,
                            expand_tabs=False,
                            replace_whitespace=False,
                        )
                        if (nonempty_message := message.strip())
                    ]
                )
            elif block.block_type == "code":
                lines = block.content.split("\n")

                potential_language_marker = None
                if lines[0] != "":
                    potential_language_marker = lines[0]
                    lines = lines[1:]

                lines = drop_both_ends(lambda ln: ln == "", lines)

                if not lines and potential_language_marker:
                    lines = [potential_language_marker]

                if lines:
                    message_lines = []
                    current_length = 0
                    for index, line in enumerate(lines):
                        estimated_length = (
                            current_length + len(line) + len("```\n") + len("\n```") + 1
                        )
                        if estimated_length <= DISCORD_MESSAGE_MAX_CHARS:
                            message_lines.append(line)
                            current_length += len(line) + 1  # plus one for newline
                        else:
                            messages.append(
                                "```\n" + "\n".join(message_lines) + "\n```"
                            )
                            message_lines = []
                            current_length = 0

                    if message_lines:
                        messages.append("```\n" + "\n".join(message_lines) + "\n```")
                else:  # empty code block
                    messages.append("```\n```")

        return messages


class InstructMessageFormatter(BaseMessageFormatter, ABC):
    """
    Abstract base class for formatters designed to work with instruct-tuned models.
    Implements methods specific to formatting messages for instruction-following LLMs.
    """

    @abstractmethod
    async def format_instruct(
        self,
        llm: LLM,
        messages: list[Message],
        system_prompt: Optional[str],
    ) -> List[LiteLLMMessage]:
        """
        Format a list of Discord messages into a list of LiteLLMMessages.

        Args:
            llm (LLM): The sending LLM.
            messages (List[Message]): The list of Discord messages to format.
            system_prompt (Optional[str]): A system message to place at the start of the context.

        Returns:
            List[LiteLLMMessage]: The formatted list of LiteLLMMessages.
        """
        pass


class SimulatorMessageFormatter(BaseMessageFormatter, ABC):
    """
    Abstract base class for formatters designed to work with simulator models.
    Implements methods specific to formatting messages for base models and text completion tasks.
    """

    @abstractmethod
    async def format_simulator(
        self,
        llm: LLM,
        messages: list[Message],
        system_prompt: Optional[str],
        users_in_channel: list[str] = None,
        force_response_from_user: Optional[str] = None,
    ) -> str:
        """
        Format a list of Discord messages into a simulator prompt.

        Args:
            llm (LLM): The sending LLM.
            messages (List[Message]): The list of Discord messages to format.
            system_prompt (Optional[str]): A system message to place at the start of the context.
            users_in_channel (Optional[list[str]]): List of users in the channel.
            force_response_from_user (Optional[str]): Force a response from a specific user.

        Returns:
            str: The formatted simulator prompt.
        """
        pass

    @abstractmethod
    async def parse_next_user(self, response: str, last_speaker: str) -> str:
        """
        Parse the next user from the model's response.

        Args:
            response (str): The model's response.
            last_speaker (str): The last speaker in the conversation.

        Returns:
            str: The next user to speak.
        """
        pass


class ComboMessageFormatter(InstructMessageFormatter, SimulatorMessageFormatter, ABC):
    """
    Abstract base class that combines functionality of both InstructMessageFormatter and SimulatorMessageFormatter.
    Suitable for formatters that need to support both instruct-tuned and simulator models.
    """

    pass
