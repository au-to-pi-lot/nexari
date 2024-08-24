import textwrap
from datetime import datetime
from itertools import groupby, cycle
from typing import List, Union, Iterable, Literal, Dict

import discord
import litellm
from litellm import acompletion
from litellm.types.utils import ModelResponse
from pydantic import BaseModel

from src.config import BotConfig, WebhookConfig
from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.util import drop_both_ends

litellm.set_verbose = True

class LiteLLMMessage(BaseModel):
    """
    A message in the LiteLLM format.
    """
    role: Literal["user", "assistant", "system"]
    content: str


class DiscordBot(discord.Client):
    """
    A Discord bot that manages multiple webhooks and uses LiteLLM for generating responses.
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
        self.webhooks: Dict[str, discord.Webhook] = {}

    async def on_ready(self):
        """
        Called when the bot is ready and connected to Discord.
        """
        print(f'{self.user} has connected to Discord!')
        await self.setup_webhooks()

    async def setup_webhooks(self):
        """
        Set up webhooks for each configured webhook in the bot.
        """
        for webhook_config in self.config.webhooks:
            channel = self.get_channel(webhook_config.channel_id)
            if channel:
                webhook = await channel.create_webhook(name=webhook_config.name)
                self.webhooks[webhook_config.name] = webhook
                print(f"Created webhook {webhook_config.name} in channel {channel.name}")
            else:
                print(f"Could not find channel with ID {webhook_config.channel_id}")

    async def on_message(self, message: discord.Message):
        """
        Called when a message is received.

        Args:
            message (discord.Message): The received message.
        """
        if message.author == self.user:
            return

        for webhook_config in self.config.webhooks:
            if webhook_config.name.lower() in message.content.lower():
                async with message.channel.typing():
                    try:
                        history: List[LiteLLMMessage] = await self.fetch_message_history(message.channel)

                        system_prompt = f"""\
{webhook_config.system_prompt}

You are: {webhook_config.name}
Current Time: {datetime.now().isoformat()}
Current Discord Guild: {message.guild.name}
Current Discord Channel: {message.channel.name}
"""

                        messages: List[LiteLLMMessage] = [
                            LiteLLMMessage(role="system", content=system_prompt),
                            *history,
                        ]

                        await self.post_llm_response(messages=messages, channel=message.channel, webhook_config=webhook_config)
                    except Exception as e:
                        if hasattr(e, 'message'):
                            error_message = e.message
                        else:
                            error_message = str(e)

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
            role: str = "assistant" if first_message.author.bot else "user"
            msg_content = "\n\n".join((message.content for message in message_group))
            content = f"""\
{msg_content}
<|begin_metadata|>
Author: {first_message.author.display_name + ("" if first_message.author.bot else f" ({first_message.author.name})") }
Author ID: {first_message.author.id}
Sent at: {first_message.created_at}
<|end_metadata|>
"""

            history.append(LiteLLMMessage(role=role, content=content))

        return history

    async def generate_response(self, messages: List[LiteLLMMessage], webhook_config: WebhookConfig) -> ModelResponse:
        """
        Generate a response using LiteLLM.

        Args:
            messages (List[LiteLLMMessage]): The messages to generate a response for.
            webhook_config (WebhookConfig): The configuration for the webhook.

        Returns:
            ModelResponse: The generated response.

        Raises:
            Exception: If an error occurs during response generation.
        """
        try:
            sampling_config = webhook_config.litellm.sampling
            response = await acompletion(
                model=webhook_config.litellm.llm_name,
                messages=messages,
                max_tokens=webhook_config.litellm.max_tokens,
                **{key: val for key, val in sampling_config if val is not None},
                api_base=webhook_config.litellm.api_base,
                api_key=webhook_config.litellm.api_key,
                stop=["<|begin_metadata|>"],
            )
            return response
        except Exception as e:
            print(f"Error in generate_response: {str(e)}")
            raise

    async def post_llm_response(self, messages: List[LiteLLMMessage], channel: discord.TextChannel, webhook_config: WebhookConfig) -> str:
        """
        Generate a LLM response and post it to a Discord channel using the appropriate webhook.

        Args:
            messages (List[LiteLLMMessage]): The message history in the channel.
            channel (discord.TextChannel): The channel to send the response to.
            webhook_config (WebhookConfig): The configuration for the webhook.

        Returns:
            str: The literal response as generated by the LLM.
        """
        response = await self.generate_response(messages, webhook_config)
        response_str = response.choices[0].message.content

        content = self.parse_llm_response(response_str)

        print(f"{webhook_config.name}: {content}")
        await self.send_webhook_message(content, channel, webhook_config.name)

        return response_str

    async def send_webhook_message(self, content: str, channel: discord.TextChannel, webhook_name: str) -> None:
        """
        Send a message to a Discord channel using the appropriate webhook, breaking it into multiple messages if necessary.

        Args:
            content (str): The content to send.
            channel (discord.TextChannel): The channel to send the message to.
            webhook_name (str): The name of the webhook to use.
        """
        content = content.strip()

        if not content:
            return None

        messages = self.break_messages(content)

        webhook = self.webhooks.get(webhook_name)
        if webhook:
            for message in messages:
                await webhook.send(content=message)
        else:
            print(f"Webhook {webhook_name} not found. Sending message as bot instead.")
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
        if "<|begin_metadata|>" in content:
            content = content.split("<|begin_metadata|>", 1)[0]
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

        blocks = []
        for block in char_blocks:
            if block.block_type == "text":
                block.content = block.content.strip()
                if block:
                    blocks.append(block)
            else:
                blocks.append(block)

        messages = []
        if blocks:
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
        else:
            messages.append("[LLM declined to respond]")

        return messages
