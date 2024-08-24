import textwrap
from itertools import groupby, cycle
from typing import List, Union, Iterable, Literal

import discord
from pydantic import BaseModel

from src.config import BotConfig
from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.util import drop_both_ends
from src.llm import LLMHandler, LiteLLMMessage
from src.config import WebhookConfig

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
        self.llm_handlers = {}
        for llm_name, llm_config in bot_config.llms.items():
            for webhook_name, webhook_config in bot_config.webhooks[llm_name].items():
                self.llm_handlers[webhook_name] = LLMHandler(llm_config, webhook_config)

    async def add_llm_handler(self, webhook_config: WebhookConfig) -> None:
        """
        Add a new LLMHandler at runtime.

        Args:
            webhook_config (WebhookConfig): Configuration for the new webhook.
        """
        if webhook_config.name in self.llm_handlers:
            raise ValueError(f"LLMHandler with name '{webhook_config.name}' already exists.")
        
        llm_handler = LLMHandler(webhook_config)
        await llm_handler.setup_webhook(self)
        self.llm_handlers[webhook_config.name] = llm_handler
        print(f"Added new LLMHandler: {webhook_config.name}")

    def remove_llm_handler(self, name: str) -> None:
        """
        Remove an LLMHandler at runtime.

        Args:
            name (str): The name of the LLMHandler to remove.
        """
        if name not in self.llm_handlers:
            raise ValueError(f"LLMHandler with name '{name}' does not exist.")
        
        del self.llm_handlers[name]
        print(f"Removed LLMHandler: {name}")

    async def modify_llm_handler(self, name: str, new_webhook_config: WebhookConfig) -> None:
        """
        Modify an existing LLMHandler at runtime.

        Args:
            name (str): The name of the LLMHandler to modify.
            new_webhook_config (WebhookConfig): The new configuration for the webhook.
        """
        if name not in self.llm_handlers:
            raise ValueError(f"LLMHandler with name '{name}' does not exist.")
        
        # Remove the old handler
        del self.llm_handlers[name]
        
        # Create and add the new handler
        llm_handler = LLMHandler(new_webhook_config)
        await llm_handler.setup_webhook(self)
        self.llm_handlers[new_webhook_config.name] = llm_handler
        print(f"Modified LLMHandler: {name} -> {new_webhook_config.name}")

    async def on_ready(self):
        """
        Called when the bot is ready and connected to Discord.
        """
        print(f'{self.user} has connected to Discord!')

    async def on_message(self, message: discord.Message):
        """
        Called when a message is received.

        Args:
            message (discord.Message): The received message.
        """
        if message.author == self.user:
            return

        for webhook_name, llm_handler in self.llm_handlers.items():
            if webhook_name.lower() in message.content.lower():
                async with message.channel.typing():
                    try:
                        history: List[LiteLLMMessage] = await self.fetch_message_history(message.channel)

                        system_prompt = llm_handler.get_system_prompt(
                            message.guild.name,
                            message.channel.name
                        )

                        messages: List[LiteLLMMessage] = [
                            LiteLLMMessage(role="system", content=system_prompt),
                            *history,
                        ]

                        await self.post_llm_response(messages=messages, channel=message.channel, llm_handler=llm_handler)
                    except Exception as e:
                        error_message = str(e)
                        print(f"An error occurred: {error_message}")
                        await message.channel.send(f"[Script error: {error_message}]")

    async def fetch_message_history(self, channel: Union[discord.TextChannel, discord.DMChannel]) -> List[LiteLLMMessage]:
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

    async def post_llm_response(self, messages: List[LiteLLMMessage], channel: discord.TextChannel, llm_handler: LLMHandler) -> str:
        """
        Generate a LLM response and post it to a Discord channel using the appropriate webhook.

        Args:
            messages (List[LiteLLMMessage]): The message history in the channel.
            channel (discord.TextChannel): The channel to send the response to.
            llm_handler (LLMHandler): The LLMHandler instance to use.

        Returns:
            str: The literal response as generated by the LLM.
        """
        response = await llm_handler.generate_response(messages)
        response_str = response.choices[0].message.content

        content = LLMHandler.parse_llm_response(response_str)

        print(f"{llm_handler.webhook_config.name}: {content}")
        await self.send_webhook_message(content, channel, llm_handler)

        return response_str

    async def send_webhook_message(self, content: str, channel: discord.TextChannel, llm_handler: LLMHandler) -> None:
        """
        Send a message to a Discord channel using the appropriate webhook, breaking it into multiple messages if necessary.

        Args:
            content (str): The content to send.
            channel (discord.TextChannel): The channel to send the message to.
            llm_handler (LLMHandler): The LLMHandler instance to use.
        """
        content = content.strip()

        if not content:
            return None

        messages = self.break_messages(content)

        webhook = await llm_handler.get_webhook(self, channel)
        for message in messages:
            await webhook.send(content=message)

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
