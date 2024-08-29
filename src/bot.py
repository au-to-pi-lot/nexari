from typing import Dict, List, Union

import discord
from discord.ext import commands

from src.config import Config
from src.const import GUILD_ID
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

    async def setup_hook(self) -> None:
        """
        A coroutine to be called to setup the bot, by default this is blank.
        This performs an asynchronous setup after the bot is logged in,
        but before it has connected to the Websocket to receive events.
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
        existing_model = await LanguageModel.get_by_name(language_model.name)
        if existing_model:
            raise ValueError(f"LLMHandler with name '{language_model.name}' already exists.")

        await language_model.create()

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
        if isinstance(identifier, int):
            language_model = await LanguageModel.get(identifier)
            if not language_model:
                raise ValueError(f"No LanguageModel found with id: {identifier}")
        else:
            language_model = identifier

        if language_model.name not in self.llm_handlers:
            raise ValueError(f"LLMHandler with name '{language_model.name}' does not exist.")

        webhooks = await Webhook.get_by_language_model_id(language_model.id)

        for webhook in webhooks:
            discord_webhook = await discord.Webhook.partial(webhook.id, webhook.token, client=self).fetch()
            await discord_webhook.delete()
            await webhook.delete()

        await language_model.delete()

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
        existing_model = await LanguageModel.get(transient_language_model.id)
        if not existing_model:
            raise ValueError(f"No existing LanguageModel found with id: {transient_language_model.id}")

        await existing_model.update(transient_language_model)
        
        self.llm_handlers[existing_model.name] = LLMHandler(existing_model)
        print(f"Modified LLMHandler: {existing_model.name}")

    async def on_ready(self):
        """
        Called when the bot is ready and connected to Discord.
        """
        print(f'{self.user} has connected to Discord!')

        language_models = await LanguageModel.get_many()
        for language_model in language_models:
            self.llm_handlers[language_model.name] = LLMHandler(language_model)

        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Error syncing command tree: {e}")

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

    @commands.command(name="sync")
    async def sync(self, ctx):
        synced = await self.tree.sync()
        await ctx.send(f"Synced {len(synced)} command(s).")
