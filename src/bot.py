import textwrap
from datetime import datetime
from itertools import groupby, cycle
from typing import List, Dict, Union, Iterable, Literal, Optional

import discord
from litellm import CustomStreamWrapper, acompletion
from litellm.types.utils import ModelResponse
from pydantic import BaseModel

from src.config import BotConfig
from src.const import DISCORD_MESSAGE_MAX_CHARS


class LiteLLMMessage(BaseModel):
    role: str
    content: str


class DiscordBot(discord.Client):
    def __init__(self, bot_config: BotConfig):
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = bot_config

    async def on_ready(self):
        print(
            f'{self.user} has connected to Discord! INVITE URL: https://discord.com/api/oauth2/authorize?client_id={self.config.discord.client_id}&permissions=412317273088&scope=bot')

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        if self.user.mentioned_in(message):
            async with message.channel.typing():
                try:
                    history: List[LiteLLMMessage] = await self.fetch_message_history(message.channel)

                    system_prompt = f"""\
{self.config.system_prompt}

You are: {self.user.name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {message.guild.name}
Current Discord Channel: {message.channel.name}
Your Discord ID: {self.user.id}
"""

                    messages: List[Dict[str, str]] = [
                        {"role": "system", "content": system_prompt},
                        *history,
                    ]

                    await self.stream_llm_response(messages=messages, channel=message.channel)
                except Exception as e:
                    if hasattr(e, 'message'):
                        error_message = e.message
                    else:
                        error_message = e

                    print(f"An error occurred: {error_message}")
                    await message.channel.send(f"[Script error: {error_message}]")

    async def fetch_message_history(self, channel: Union[discord.TextChannel, discord.DMChannel]) -> List[
        LiteLLMMessage]:
        discord_history: Iterable[discord.Message] = reversed([
            message
            async for message in channel.history(limit=self.config.message_limit)
        ])

        # group adjacent messages from the same user
        # this saves some tokens on repeated metadata
        history = []
        for _, message_group in groupby(discord_history, lambda a: a.author):
            message_group = list(message_group)
            first_message = message_group[0]
            role: str = "assistant" if first_message.author == self.user else "user"
            msg_content = "\n\n".join((message.content for message in message_group))
            content = f"""\
<content>
{msg_content}
</content>
<metadata>
Author: {first_message.author.display_name + ("" if first_message.author.bot else f" ({first_message.author.name})") }
Author ID: {first_message.author.id}
Sent at: {first_message.created_at}
</metadata>
"""

            history.append(LiteLLMMessage(role=role, content=content))

        return history

    async def generate_response(self, messages: List[Dict[str, str]]) -> Union[ModelResponse, CustomStreamWrapper]:
        try:
            response = await acompletion(
                model=self.config.litellm.llm_name,
                messages=messages,
                max_tokens=self.config.litellm.max_tokens,
                temperature=self.config.litellm.temperature,
                api_base=self.config.litellm.api_base,
                api_key=self.config.litellm.api_key,
                stop=["</content>", "<metadata>"]
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {e.message}")
            raise

    async def stream_llm_response(self, messages: List[Dict[str, str]], channel: discord.TextChannel) -> str:
        response = await self.generate_response(messages)
        response_str = response.choices[0].message.content

        if "<content>" in response_str:
            response_str = response_str.split("<content>", 1)[1]
        if "</content>" in response_str:
            response_str = response_str.split("</content>", 1)[0]

        print(f"{self.config.name}: {response_str}")
        await self.send_message(response_str, channel)

        return response_str

    async def send_message(self, content: str, channel: discord.TextChannel) -> None:
        content = content.strip()

        if not content:
            return None

        messages = self.break_messages(content)

        for message in messages:
            await channel.send(message)

    @staticmethod
    def break_messages(content: str) -> List[str]:
        class CharBlock(BaseModel):
            content: str
            block_type: Literal['text', 'code']
            block_start_newline: Optional[bool]
            block_end_newline: Optional[bool]

        char_blocks = (
            CharBlock(content=content, block_type=block_type, block_start_newline=content.startswith("\n"), block_end_newline=content.endswith("\n"))
            for content, block_type in zip(content.split("```"), cycle(["text", "code"]))
            if content
        )

        messages = []
        for block in char_blocks:
            if block.block_type == "text":
                messages.extend([
                    nonempty_message
                    for paragraph in block.content.split("\n\n")
                    for message in textwrap.wrap(
                        paragraph,
                        width=DISCORD_MESSAGE_MAX_CHARS,
                        expand_tabs=False,
                        replace_whitespace=False
                    )
                    if (nonempty_message := message.strip())
                ])
            elif block.block_type == "code":
                lines = block.content.split("\n")
                message_lines = []
                current_length = 0
                count = 0
                for index, line in enumerate(lines):
                    first_line = index == 0
                    last_line = index == len(lines) - 1

                    if current_length + len(line) + len("```\n") + len("\n```") + 1 <= DISCORD_MESSAGE_MAX_CHARS:
                        message_lines.append(line)
                        current_length += len(line) + 1
                    else:
                        messages.append(
                            ("```" if first_line and block.block_start_newline else "```\n")
                            + "\n".join(message_lines)
                            + ("```" if last_line and block.block_end_newline else "\n```")
                        )
                        message_lines = []
                        current_length = 0
                        count += 1

                if message_lines:
                    messages.append(
                        ("```" if len(message_lines) == len(lines) and block.block_start_newline else "```\n")
                        + "\n".join(message_lines)
                        + ("```" if block.block_end_newline else "\n```")
                    )

        return messages
