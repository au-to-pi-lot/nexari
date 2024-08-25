import textwrap
from itertools import groupby, cycle
from typing import List, Union, Iterable, Literal, Dict
from src.db.models import LanguageModel, Webhook

import discord
from pydantic import BaseModel
from sqlalchemy import select, delete

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


    async def add_llm_handler(self, language_model: LanguageModel) -> None:
        """
        Add a new LLMHandler at runtime and save the transient language_model to the database.

        Args:
            language_model (LanguageModel): Transient LanguageModel object to be added.

        Raises:
            ValueError: If an LLMHandler with the same name already exists.
        """
        async with Session() as session:
            # Check if an LLMHandler with the same name already exists
            existing_model = await session.execute(
                select(LanguageModel).where(LanguageModel.name == language_model.name)
            )
            if existing_model.scalar_one_or_none():
                raise ValueError(f"LLMHandler with name '{language_model.name}' already exists.")

            # Add the language_model to the session and commit to save it to the database
            session.add(language_model)
            await session.commit()
            
            # Refresh the language_model to ensure it has the database-assigned ID
            await session.refresh(language_model)

        # Create and add the LLMHandler
        llm_handler = LLMHandler(language_model)
        self.llm_handlers[language_model.name] = llm_handler
        print(f"Added new LLMHandler: {language_model.name}")

    async def remove_llm_handler(self, identifier: Union[int, LanguageModel]) -> None:
        """
        Remove an LLMHandler at runtime, delete the corresponding database entry,
        and remove all associated Discord webhooks.

        Args:
            identifier (Union[int, LanguageModel]): Either the ID of the LanguageModel to remove,
                                                    or a transient LanguageModel object.

        Raises:
            ValueError: If no LLMHandler with the given identifier exists.
        """
        async with Session() as session:
            if isinstance(identifier, int):
                # If identifier is an ID, fetch the LanguageModel from the database
                query = select(LanguageModel).where(LanguageModel.id == identifier)
                language_model = await session.execute(query)
                language_model = language_model.scalar_one_or_none()
                if not language_model:
                    raise ValueError(f"No LanguageModel found with id: {identifier}")
            else:
                # If identifier is a LanguageModel object, use it directly
                language_model = identifier

            # Check if the LLMHandler exists
            if language_model.name not in self.llm_handlers:
                raise ValueError(f"LLMHandler with name '{language_model.name}' does not exist.")

            # Fetch all associated webhooks
            webhook_query = select(Webhook).where(Webhook.language_model_id == language_model.id)
            webhooks = await session.execute(webhook_query)
            webhooks = webhooks.scalars().all()

            # Delete Discord webhooks
            for webhook in webhooks:
                discord_webhook = await discord.Webhook.partial(webhook.id, webhook.token, client=self).fetch()
                await discord_webhook.delete()

            # Delete all associated webhooks from the database
            delete_query = delete(Webhook).where(Webhook.language_model_id == language_model.id)
            await session.execute(delete_query)

            # Delete the LanguageModel from the database
            await session.delete(language_model)
            await session.commit()

        # Remove the LLMHandler from the local dictionary
        del self.llm_handlers[language_model.name]
        print(f"Removed LLMHandler and associated webhooks: {language_model.name}")

    async def modify_llm_handler(self, transient_language_model: LanguageModel) -> None:
        """
        Modify an existing LLMHandler at runtime using a transient SQLAlchemy object.

        Args:
            transient_language_model (LanguageModel): A transient SQLAlchemy object with updated data.

        Raises:
            ValueError: If no existing LanguageModel with the given primary key is found.
        """
        async with Session() as session:
            # Attempt to merge the transient object with the existing database object
            merged_model = await session.merge(transient_language_model)
            
            # Check if the merge resulted in an existing object or created a new one
            if merged_model not in session.new:
                # The object existed and was updated
                await session.commit()
                
                # Update the LLMHandler
                self.llm_handlers[merged_model.name] = LLMHandler(merged_model)
                print(f"Modified LLMHandler: {merged_model.name}")
            else:
                # The merge created a new object, which means no existing object was found
                await session.rollback()
                raise ValueError(f"No existing LanguageModel found with id: {transient_language_model.id}")

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
