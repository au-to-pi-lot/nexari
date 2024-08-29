from typing import List, Union

import discord
from discord.ext import commands

from src.config import Config
from src.db.models import LanguageModel, Webhook
from src.db.models.llm import LanguageModelCreate, LanguageModelUpdate
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

    async def setup_hook(self) -> None:
        """
        A coroutine to be called to setup the bot, by default this is blank.
        This performs an asynchronous setup after the bot is logged in,
        but before it has connected to the Websocket to receive events.
        """
        await self.load_extension("src.commands")

    async def add_llm_handler(self, language_model_data: LanguageModelCreate) -> None:
        """
        Add a new LLMHandler at runtime and save the transient language_model to the database.

        Args:
            language_model_data (LanguageModel): Transient LanguageModel object to be added.

        Raises:
            ValueError: If an LLMHandler with the same name already exists.
        """
        existing_model = await LanguageModel.get_by_name(language_model_data.name)
        if existing_model:
            raise ValueError(f"LLMHandler with name '{language_model_data.name}' already exists.")

        language_model = await LanguageModel.create(language_model_data)
        print(f"Added new LLMHandler: {language_model_data.name}")

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

        webhooks = await Webhook.get_by_language_model_id(language_model.id)

        for webhook in webhooks:
            discord_webhook = await discord.Webhook.partial(webhook.id, webhook.token, client=self).fetch()
            await discord_webhook.delete()
            await Webhook.delete(webhook.id)

        await LanguageModel.delete(language_model.id)
        print(f"Removed LLMHandler and associated webhooks: {language_model.name}")

    async def modify_llm_handler(self, id: int, data: LanguageModelUpdate) -> None:
        """
        Modify an existing LLMHandler at runtime using a transient SQLAlchemy object.

        Args:
            id (int): The id of the model to update
            data (LanguageModelUpdate): Data fields to change.

        Raises:
            ValueError: If no existing LanguageModel with the given primary key is found.
        """
        model = await LanguageModel.get(id)
        if not model:
            raise ValueError(f"No existing LanguageModel found with id: {data.id}")

        model = await model.update(id, data)
        print(f"Modified LLMHandler: {model.name}")

    async def on_ready(self):
        """
        Called when the bot is ready and connected to Discord.
        """
        print(f'{self.user} has connected to Discord!')

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

        llm_handlers = await self.get_llm_handlers()

        for llm_handler in llm_handlers:
            if llm_handler.language_model.name.lower() in message.content.lower():
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

    async def get_llm_handlers(self):
        models = await LanguageModel.get_many(limit=None)
        return [LLMHandler(model) for model in models]

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
