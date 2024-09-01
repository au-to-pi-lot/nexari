from typing import List, Union, Optional

import discord
from discord.ext import commands

from src.config import Config
from src.db.models import LLM, Webhook, Guild
from src.db.models.llm import LLMCreate, LLMUpdate
from src.llm import LLMHandler, LiteLLMMessage
from src.db.models.guild import GuildCreate
from src.db.engine import Session


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

    async def add_llm_handler(self, language_model_data: LLMCreate) -> None:
        """
        Add a new LLMHandler at runtime and save the transient language_model to the database.

        Args:
            language_model_data (LLM): Transient LLM object to be added.

        Raises:
            ValueError: If an LLMHandler with the same name already exists.
        """
        existing_model = await LLM.get_by_name(language_model_data.name)
        if existing_model:
            raise ValueError(f"LLMHandler with name '{language_model_data.name}' already exists.")

        language_model = await LLM.create(language_model_data)
        print(f"Added new LLMHandler: {language_model_data.name}")

    async def remove_llm_handler(self, identifier: Union[int, LLM]) -> None:
        """
        Remove an LLMHandler at runtime, delete the corresponding database entry,
        and remove all associated Discord webhooks.

        Args:
            identifier (Union[int, LLM]): Either the ID of the LLM to remove,
                                                    or a transient LLM object.

        Raises:
            ValueError: If no LLMHandler with the given identifier exists.
        """
        if isinstance(identifier, int):
            language_model = await LLM.get(identifier)
            if not language_model:
                raise ValueError(f"No LLM found with id: {identifier}")
        else:
            language_model = identifier

        webhooks = await Webhook.get_by_language_model_id(language_model.id)

        for webhook in webhooks:
            discord_webhook = await discord.Webhook.partial(webhook.id, webhook.token, client=self).fetch()
            await discord_webhook.delete()
            await Webhook.delete(webhook.id)

        await LLM.delete(language_model.id)
        print(f"Removed LLMHandler and associated webhooks: {language_model.name}")

    async def modify_llm_handler(self, id: int, data: LLMUpdate) -> None:
        """
        Modify an existing LLMHandler at runtime using a transient SQLAlchemy object.

        Args:
            id (int): The id of the model to update
            data (LLMUpdate): Data fields to change.

        Raises:
            ValueError: If no existing LLM with the given primary key is found.
        """
        model = await LLM.get(id)
        if not model:
            raise ValueError(f"No existing LLM found with id: {data.id}")

        model = await model.update(id, data)
        print(f"Modified LLMHandler: {model.name}")

    async def on_ready(self):
        """
        Called when the bot is ready and connected to Discord.
        """
        print(f'{self.user} has connected to Discord!')

        for guild in self.guilds:
            await self.ensure_guild_exists(guild)

        try:
            guild = await self.fetch_guild(307011228293660683)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Error syncing command tree: {e}")

    async def ensure_guild_exists(self, guild: discord.Guild):
        """
        Ensure that a guild exists in the database.
        """
        async with Session() as session:
            db_guild = await Guild.get(guild.id, session=session)
            if not db_guild:
                guild_data = GuildCreate(id=guild.id, name=guild.name)
                await Guild.create(guild_data, session=session)
                print(f"Added new guild to database: {guild.name} (ID: {guild.id})")

    async def on_guild_join(self, guild: discord.Guild):
        """
        Called when the bot joins a new guild.
        """
        await self.ensure_guild_exists(guild)

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
            if llm_handler.llm.name.lower() in message.content.lower():
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
        models = await LLM.get_many(limit=None)
        return [LLMHandler(model) for model in models]

    async def get_handler(self, name: str) -> Optional[LLMHandler]:
        model = await LLM.get_by_name(name)
        return LLMHandler(model) if model else None

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
