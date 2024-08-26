from typing import Dict, List, Union

import discord
from discord.ext import commands
from sqlalchemy import delete, select

from src.config import Config
from src.db.engine import Session
from src.db.models import LanguageModel, Webhook
from src.llm import LLMHandler, LiteLLMMessage


class DiscordBot(commands.Bot):
    """
    A Discord bot that manages multiple webhooks and uses LiteLLM for generating responses.
    """

    def __init__(self, config: Config):
        """
        Initialize the DiscordBot.

        Args:
            config (Config): Configuration for the bot.
        """
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.llm_handlers: Dict[str, LLMHandler] = {}

    async def setup_hook(self):
        """
        A coroutine to be called to setup the bot, by default this is blank.
        This performs an asynchronous setup after the bot is logged in,
        but before it has connected to the Websocket.
        """
        await self.load_extension("src.commands")

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

        async with Session() as session:
            query = select(LanguageModel)
            language_models = (await session.scalars(query)).all()
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

        await self.process_commands(message)

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
                        messages = LLMHandler.break_messages(response_str)

                        await DiscordBot.send_messages(messages, webhook)
                    except Exception as e:
                        error_message = str(e)
                        print(f"An error occurred: {error_message}")
                        await channel.send(f"[Script error: {error_message}]")

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
