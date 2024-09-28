import textwrap
from abc import ABC, abstractmethod, abstractproperty
from itertools import cycle
from typing import List, Literal, Optional

import discord
from litellm import ModelResponse
from pydantic import BaseModel

from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.proxies import WebhookProxy, MessageProxy, ChannelProxy
from src.types.litellm_message import LiteLLMMessage
from src.util import drop_both_ends

class ParseResponse(BaseModel):
    complete_message: str
    split_messages: list[str]
    username: Optional[str]

class MessageFormatter(ABC):
    def __init__(self):
        pass

    @staticmethod
    @abstractmethod
    async def format_instruct(messages: List[MessageProxy], system_prompt: str, webhook: Optional[WebhookProxy]) -> List[LiteLLMMessage]:
        """
        Format a list of Discord messages into a list of LiteLLMMessages.

        Args:
            webhook (WebhookProxy): The webhook who will reply.
            system_prompt (str): A system message to place at the start of the context.
            messages (List[discord.Message]): The list of Discord messages to format.

        Returns:
            List[LiteLLMMessage]: The formatted list of LiteLLMMessages.
        """
        pass

    @staticmethod
    @abstractmethod
    async def format_simulator(messages: list[MessageProxy], system_prompt: Optional[str], webhook: Optional[WebhookProxy], channel: Optional[ChannelProxy] = None, users_in_channel: list[str] = None, force_response_from_user: Optional[str] = None) -> str:
        """
        Format a list of Discord messages into a simulator prompt.

        Args:
            webhook (WebhookProxy): The webhook who will reply.
            system_prompt (str): A system message to place at the start of the context.
            messages (List[discord.Message]): The list of Discord messages to format.

        Returns:
            List[LiteLLMMessage]: The formatted list of LiteLLMMessages.
        """
        pass


    @staticmethod
    @abstractmethod
    async def parse_messages(response: str) -> ParseResponse:
        """
        Parse a ModelResponse into a list of messages to send to Discord.

        Args:
            response (ModelResponse): The ModelResponse to parse.

        Returns:
            List[str]: The parsed list of strings.
        """
        pass

    @staticmethod
    @abstractmethod
    async def parse_next_user(response: str, last_speaker: str) -> str:
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


