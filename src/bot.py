import textwrap
from itertools import groupby, cycle
from typing import List, Union, Iterable, Literal, Dict

import discord
from pydantic import BaseModel
from sqlalchemy import select

from src.config import Config
from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.db.engine import Session
from src.db.models import LanguageModel
from src.util import drop_both_ends
from src.llm import LLMHandler, LiteLLMMessage

class DiscordBot(discord.Client):
    """
    A Discord bot that manages multiple webhooks and uses LiteLLM for generating responses.
    """

    def __init__(self, config: Config):
        """
        Initialize the DiscordBot.

        Args:
            config (BotConfig): Configuration for the bot.
        """
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.llm_handlers: Dict[str, LLMHandler] = {}


    async def add_llm_handler(self) -> None:
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

    async def modify_llm_handler(self, name: str) -> None:
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

        with Session() as session:
            query = select(LanguageModel)
            language_models = await session.scalars(query).all()
        for language_model in language_models:
            self.llm_handlers[language_model.name] = LLMHandler(language_model)

    async def on_message(self, message: discord.Message):
        """
        Called when a message is received.

        Args:
            message (discord.Message): The received message.
        """
        if message.author == self.user:
            return

        channel = message.channel

        for llm_name, llm_handler in self.llm_handlers.items():
            if llm_name.lower() in message.content.lower():
                async with channel.typing():
                    try:
                        history: List[LiteLLMMessage] = await llm_handler.fetch_message_history(self, channel)

                        system_prompt = llm_handler.get_system_prompt(
                            message.guild.name,
                            channel.name
                        )

                        history = [
                            LiteLLMMessage(role="system", content=system_prompt),
                            *history,
                        ]

                        response_str = await llm_handler.get_response(history)
                        webhook = await llm_handler.get_webhook(self, channel)
                        messages = DiscordBot.break_messages(response_str)

                        await DiscordBot.send_messages(messages, webhook)
                    except Exception as e:
                        error_message = str(e)
                        print(f"An error occurred: {error_message}")
                        await channel.send(f"[Script error: {error_message}]")

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

    @staticmethod
    async def send_messages(messages: List[str], webhook: discord.Webhook) -> None:
        """
        Send a message to a Discord channel using the appropriate webhook, breaking it into multiple messages if necessary.

        Args:
            messages (List[str]): A list of messages to send via the webhook.
            webhook (discord.Webhook): The webhook with which to send the message.
        """
        for message in messages:
            await webhook.send(content=message)
