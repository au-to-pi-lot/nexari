import textwrap
from itertools import cycle, groupby
from typing import List, Literal

import discord
from litellm.types.utils import ModelResponse
from pydantic import BaseModel

from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.types.litellm_message import LiteLLMMessage
from src.types.message_formatter import MessageFormatter
from src.util import drop_both_ends


class MetadataBlockFormatter(MessageFormatter):
    def format(
        self, messages: List[discord.Message], system_prompt: str, webhook_id: int
    ) -> List[LiteLLMMessage]:
        # group adjacent messages from the same user
        # this saves some tokens on repeated metadata
        history = [LiteLLMMessage(role="system", content=system_prompt)]
        for _, message_group in groupby(messages, lambda a: a.author):
            message_group = list(message_group)
            first_message = message_group[0]
            role: str = (
                "assistant"
                if first_message.webhook_id and first_message.webhook_id == webhook_id
                else "user"
            )
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

    def parse(self, response: ModelResponse) -> List[str]:
        content = response.choices[0].message.content

        if "<|begin_metadata|>" in content:
            content = content.split("<|begin_metadata|>", 1)[0]

        class CharBlock(BaseModel):
            content: str
            block_type: Literal["text", "code"]

        char_blocks = (
            CharBlock(content=content, block_type=block_type)
            for content, block_type in zip(
                content.split("```"), cycle(["text", "code"])
            )
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
