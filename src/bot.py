import textwrap
from datetime import datetime
from itertools import groupby, cycle
from typing import List, Dict, Union, Iterable, Literal, Optional

import discord
import litellm
from litellm import CustomStreamWrapper, acompletion
from litellm.types.utils import ModelResponse
from pydantic import BaseModel

from src.config import BotConfig
from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.util import drop_both_ends

litellm.set_verbose = True

class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """
    role: str
    content: str


class DiscordBot(discord.Client):
    """
    A Discord bot that uses LiteLLM for generating responses.
    """

    def __init__(self, bot_config: BotConfig):
        """
        Initialize the DiscordBot.

        Args:
            bot_config (BotConfig): Configuration for the bot.
        """
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = bot_config

    async def on_ready(self):
        """
        Called when the bot is ready and connected to Discord.
        """
        print(
            f'{self.user} has connected to Discord! INVITE URL: https://discord.com/api/oauth2/authorize?client_id={self.config.discord.client_id}&permissions=412317273088&scope=bot')

    async def on_message(self, message: discord.Message):
        """
        Called when a message is received.

        Args:
            message (discord.Message): The received message.
        """
        if message.author == self.user:
            return

        if self.user.mentioned_in(message):
            async with message.channel.typing():
                try:
                    history: List[LiteLLMMessage] = await self.fetch_message_history(message.channel)

                    system_prompt = f"""\
{self.config.chat.system_prompt}

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

                    await self.post_llm_response(messages=messages, channel=message.channel)
                except Exception as e:
                    if hasattr(e, 'message'):
                        error_message = e.message
                    else:
                        error_message = e

                    print(f"An error occurred: {error_message}")
                    await message.channel.send(f"[Script error: {error_message}]")

    async def fetch_message_history(self, channel: Union[discord.TextChannel, discord.DMChannel]) -> List[
        LiteLLMMessage]:
        """
        Fetch message history from a Discord channel.

        Args:
            channel (Union[discord.TextChannel, discord.DMChannel]): The channel to fetch history from.

        Returns:
            List[LiteLLMMessage]: A list of messages in LiteLLM format.
        """
        discord_history: Iterable[discord.Message] = reversed([
            message
            async for message in channel.history(limit=self.config.chat.message_limit)
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

    async def generate_response(self, messages: List[LiteLLMMessage]) -> ModelResponse:
        """
        Generate a response using LiteLLM.

        Args:
            messages (List[LiteLLMMessage]): The messages to generate a response for.

        Returns:
            ModelResponse: The generated response.

        Raises:
            Exception: If an error occurs during response generation.
        """
        try:
            sampling_config = self.config.litellm.sampling
            response = await acompletion(
                model=self.config.litellm.llm_name,
                messages=messages,
                max_tokens=self.config.litellm.max_tokens,
                temperature=sampling_config.temperature,
                top_p=sampling_config.top_p,
                top_k=sampling_config.top_k,
                frequency_penalty=sampling_config.frequency_penalty,
                presence_penalty=sampling_config.presence_penalty,
                repetition_penalty=sampling_config.repetition_penalty,
                min_p=sampling_config.min_p,
                top_a=sampling_config.top_a,
                api_base=self.config.litellm.api_base,
                api_key=self.config.litellm.api_key,
                stop=["</content>", "<metadata>"]
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {str(e)}")
            raise

    async def post_llm_response(self, messages: List[LiteLLMMessage], channel: discord.TextChannel) -> str:
        """
        Generate a LLM response and post it to a Discord channel.

        Args:
            messages (List[LiteLLMMessage]): The message history in the channel.
            channel (discord.TextChannel): The channel to send the response to.

        Returns:
            str: The literal response as generated by the LLM.
        """
        response = await self.generate_response(messages)
        response_str = response.choices[0].message.content

        content = self.parse_llm_response(response_str)

        print(f"{self.config.name}: {content}")
        await self.send_message(content, channel)

        return response_str

    async def send_message(self, content: str, channel: discord.TextChannel) -> None:
        """
        Send a message to a Discord channel, breaking it into multiple messages if necessary.

        Args:
            content (str): The content to send.
            channel (discord.TextChannel): The channel to send the message to.
        """
        content = content.strip()

        if not content:
            return None

        messages = self.break_messages(content)

        for message in messages:
            await channel.send(message)

    @staticmethod
    def parse_llm_response(content: str) -> str:
        """
        Parse the LLM response, removing content and metadata tags.

        Args:
            content (str): The raw LLM response.

        Returns:
            str: The parsed response.
        """
        if "<content>" in content:
            content = content.split("<content>", 1)[1]
        if "</content>" in content:
            content = content.split("</content>", 1)[0]
        if "<metadata>" in content:
            content = content.split("<metadata>", 1)[0]
        return content.strip()

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
            block_type: Literal['text', 'code']

        char_blocks = (
            CharBlock(content=content, block_type=block_type)
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
                        if current_length + len(line) + len("```\n") + len("\n```") + 1 <= DISCORD_MESSAGE_MAX_CHARS:
                            message_lines.append(line)
                            current_length += len(line) + 1  # plus one for newline
                        else:
                            messages.append(
                                "```\n"
                                + "\n".join(message_lines)
                                + "\n```"
                            )
                            message_lines = []
                            current_length = 0

                    if message_lines:
                        messages.append(
                            "```\n"
                            + "\n".join(message_lines)
                            + "\n```"
                        )
                else:  # empty code block
                    messages.append("```\n```")

        return messages
