import logging
from textwrap import dedent
from typing import List, Optional

import aiohttp
import discord
from discord import Embed, Interaction, app_commands
from discord.ext import commands
from discord.ext.commands import Bot

from src.const import AVATAR_DIR
from src.db.models import LLM
from src.db.models.llm import LLMCreate, LLMUpdate
from src.proxies import LLMProxy

logger = logging.getLogger(__name__)


class LLMCommands(commands.GroupCog, name="llm"):
    """A group of commands for managing LLMs."""

    def __init__(self, bot: Bot):
        """Initialize the LLMCommands cog.

        Args:
            bot (DiscordBot): The DiscordBot instance.
        """
        self.bot = bot
        super().__init__()

    async def get_llm_names(self, interaction: Interaction) -> List[str]:
        """Get a list of LLM names for the current guild.

        Args:
            interaction (Interaction): The Discord interaction.

        Returns:
            List[str]: A list of LLM names.
        """
        llms = await LLMProxy.get_all(interaction.guild_id)
        return [llm.name for llm in llms]

    async def autocomplete_llm_name(
        self, interaction: Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete LLM names based on the current input.

        Args:
            interaction: The Discord interaction.
            current: The current input string.

        Returns:
            List[app_commands.Choice[str]]: A list of autocomplete choices.
        """
        llm_names = await self.get_llm_names(interaction)
        return [
            app_commands.Choice(name=name, value=name)
            for name in llm_names
            if current.lower() in name.lower()
        ]

    @app_commands.command()
    async def list(self, interaction: discord.Interaction):
        """List all available LLMs for the current guild"""
        llms = await LLMProxy.get_all(interaction.guild_id)
        embed = Embed(title="Available LLMs", color=discord.Color.blue())
        if llms:
            for llm in llms:
                embed.add_field(
                    name=llm.name,
                    value=f"Model: {llm.llm_name}",
                    inline=False,
                )
        else:
            embed.description = "No LLMs configured."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Register a new LLM")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="Name of the new LLM",
        api_base="API base URL path",
        llm_name="Name of the model",
        api_key="API secret key (don't share this!)",
        max_tokens="Maximum number of tokens per response",
        system_prompt="System prompt to be displayed at start of context",
        context_length="Context length in tokens",
        message_limit="Number of messages to put in LLM's context",
        temperature="Sampling temperature (default is 1.0)",
        top_p="Sampling top_p value",
        top_k="Sampling top_k value (not supported by all APIs)",
        frequency_penalty="Sampling frequency penalty",
        presence_penalty="Sampling presence penalty",
        repetition_penalty="Sampling repetition penalty (not supported by all APIs)",
        min_p="Sampling min_p value (not supported by all APIs)",
        top_a="Sampling top_a value (not supported by all APIs)",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        api_base: str,
        llm_name: str,
        api_key: str,
        max_tokens: int,
        context_length: int,
        message_limit: int,
        system_prompt: str = "",
        temperature: float = 1.0,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        min_p: Optional[float] = None,
        top_a: Optional[float] = None,
    ):
        """Create a new LLM"""
        await interaction.response.defer(ephemeral=True)

        model_data = LLMCreate(
            name=name,
            guild_id=interaction.guild_id,
            api_base=api_base,
            llm_name=llm_name,
            api_key=api_key,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            context_length=context_length,
            message_limit=message_limit,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            min_p=min_p,
            top_a=top_a,
        )

        try:
            await self.bot.add_llm_handler(model_data, interaction.guild)
            embed = Embed(title="LLM Created", color=discord.Color.green())
            embed.add_field(name="Name", value=name, inline=False)
            embed.add_field(name="Model", value=llm_name, inline=False)
            embed.add_field(name="Max Tokens", value=str(max_tokens), inline=True)
            embed.add_field(name="Temperature", value=str(temperature), inline=True)
            await interaction.followup.send(embed=embed)
        except ValueError as e:
            embed = Embed(title="Error Creating LLM", color=discord.Color.red())
            embed.description = str(e)
            await interaction.followup.send(embed=embed)

    @app_commands.command(description="Modify an existing LLM")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.autocomplete(name=autocomplete_llm_name)
    @app_commands.describe(
        name="Name of the LLM to modify",
        new_name="New name for the LLM",
        api_base="API base URL path",
        llm_name="Name of the model",
        api_key="API secret key (don't share this!)",
        max_tokens="Maximum number of tokens per response",
        system_prompt="System prompt to be displayed at start of context",
        context_length="Context length in tokens",
        message_limit="Number of messages to put in LLM's context",
        temperature="Sampling temperature (default is 1.0)",
        top_p="Sampling top_p value",
        top_k="Sampling top_k value (not supported by all APIs)",
        frequency_penalty="Sampling frequency penalty",
        presence_penalty="Sampling presence penalty",
        repetition_penalty="Sampling repetition penalty (not supported by all APIs)",
        min_p="Sampling min_p value (not supported by all APIs)",
        top_a="Sampling top_a value (not supported by all APIs)",
    )
    async def modify(
        self,
        interaction: discord.Interaction,
        name: str,
        new_name: Optional[str] = None,
        api_base: Optional[str] = None,
        llm_name: Optional[str] = None,
        api_key: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        context_length: Optional[int] = None,
        message_limit: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        min_p: Optional[float] = None,
        top_a: Optional[float] = None,
    ):
        await interaction.response.defer(ephemeral=True)

        model = await LLM.get_by_name(name, interaction.guild_id)
        if not model:
            embed = Embed(title="Error Modifying LLM", color=discord.Color.red())
            embed.description = f"LLM '{name}' not found in this guild."
            await interaction.followup.send(embed=embed)
            return

        update_data = LLMUpdate(
            name=new_name,
            api_base=api_base,
            llm_name=llm_name,
            api_key=api_key,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            context_length=context_length,
            message_limit=message_limit,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            min_p=min_p,
            top_a=top_a,
        )

        try:
            await self.bot.modify_llm_handler(model.id, update_data)
            embed = Embed(title="LLM Modified", color=discord.Color.green())
            embed.add_field(name="Name", value=new_name or name, inline=False)
            if llm_name:
                embed.add_field(name="Model", value=llm_name, inline=False)
            if max_tokens:
                embed.add_field(name="Max Tokens", value=str(max_tokens), inline=True)
            if temperature:
                embed.add_field(name="Temperature", value=str(temperature), inline=True)
            await interaction.followup.send(embed=embed)
        except ValueError as e:
            embed = Embed(title="Error Modifying LLM", color=discord.Color.red())
            embed.description = str(e)
            await interaction.followup.send(embed=embed)

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.autocomplete(name=autocomplete_llm_name)
    @app_commands.describe(
        name="Name of the LLM to delete",
    )
    async def delete(self, interaction: discord.Interaction, name: str):
        """Delete an existing LLM"""
        llm = await LLMProxy.get_by_name(name, interaction.guild_id)
        if not llm:
            embed = Embed(title="Error Deleting LLM", color=discord.Color.red())
            embed.description = f"'{name}' not found."
            await interaction.response.send_message(embed=embed)
            return

        try:
            await llm.delete()
            embed = Embed(title="LLM Deleted", color=discord.Color.green())
            embed.description = f"'{name}' deleted successfully!"
            await interaction.response.send_message(embed=embed)
        except ValueError as e:
            embed = Embed(title="Error Deleting LLM", color=discord.Color.red())
            embed.description = str(e)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(
        description="Create a deep copy of an existing LLM with a new name"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        source_name="Name of the existing LLM", new_name="Name for the new copy"
    )
    @app_commands.autocomplete(source_name=autocomplete_llm_name)
    async def copy(
        self, interaction: discord.Interaction, source_name: str, new_name: str
    ):
        """Create a deep copy of an existing LLM with a new name"""
        await interaction.response.defer(ephemeral=True)

        source_llm = await LLMProxy.get_by_name(source_name, interaction.guild_id)
        if not source_llm:
            embed = Embed(title="Error Copying LLM", color=discord.Color.red())
            embed.description = f"'{source_name}' not found in this guild."
            await interaction.followup.send(embed=embed)
            return

        existing_llm = await LLMProxy.get_by_name(new_name, interaction.guild_id)
        if existing_llm:
            embed = Embed(title="Error Copying LLM", color=discord.Color.red())
            embed.description = (
                f"An LLM with the name '{new_name}' already exists in this guild."
            )
            await interaction.followup.send(embed=embed)
            return




        try:
            new_llm = await source_llm.copy(new_name)
            embed = Embed(title="LLM Copied", color=discord.Color.green())
            embed.description = (
                f"LLM '{source_name}' successfully copied to '{new_name}'!"
            )
            embed.add_field(name="Model", value=new_llm.llm_name, inline=False)
            embed.add_field(
                name="Max Tokens", value=str(new_llm.max_tokens), inline=True
            )
            embed.add_field(
                name="Temperature", value=str(new_llm.temperature), inline=True
            )
            await interaction.followup.send(embed=embed)
        except ValueError as e:
            embed = Embed(title="Error Copying LLM", color=discord.Color.red())
            embed.description = str(e)
            await interaction.followup.send(embed=embed)

    @app_commands.command(description="Set an avatar for an LLM")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.autocomplete(name=autocomplete_llm_name)
    async def set_avatar(
        self, interaction: discord.Interaction, name: str, image_url: str
    ):
        """Set an avatar for an LLM"""
        await interaction.response.defer(ephemeral=True)

        llm = await LLMProxy.get_by_name(name, interaction.guild_id)
        if not llm:
            embed = Embed(title="Error Setting Avatar", color=discord.Color.red())
            embed.description = f"'{name}' not found in this guild."
            await interaction.followup.send(embed=embed)
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        raise ValueError(f"Failed to download image from URL: {image_url}")
                    
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if content_type not in ["image/jpeg", "image/png", "image/gif"]:
                        raise ValueError("The image must be a JPEG, PNG, or GIF file.")
                    
                    image_data = await resp.read()
                    if len(image_data) > 8 * 1024 * 1024:  # 8MB
                        raise ValueError("The image file size must be less than 8MB.")

            await llm.set_avatar(discord.File(image_data, filename=f"avatar.{content_type.split('/')[-1]}"))
            
            embed = Embed(title="Avatar Set", color=discord.Color.green())
            embed.description = f"Avatar for '{name}' has been set and applied to all webhooks."
            await interaction.followup.send(embed=embed)
        except ValueError as e:
            embed = Embed(title="Error Setting Avatar", color=discord.Color.red())
            embed.description = str(e)
            await interaction.followup.send(embed=embed)

    @app_commands.command(description="Sync the bot commands with the current guild")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        """Sync the bot commands with the current guild"""
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            embed = Embed(title="Bot Synced", color=discord.Color.green())
            embed.description = f"Synced {len(synced)} command(s) to the current guild."
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = Embed(title="Sync Error", color=discord.Color.red())
            embed.description = f"An error occurred while syncing: {str(e)}"
            await interaction.followup.send(embed=embed)

    @app_commands.command(description="Print the configuration of an LLM")
    @app_commands.autocomplete(name=autocomplete_llm_name)
    async def print(self, interaction: discord.Interaction, name: str):
        """Print the configuration of an LLM"""
        await interaction.response.defer(ephemeral=True)

        llm = await LLMProxy.get_by_name(name, interaction.guild_id)
        if not llm:
            embed = Embed(title="Error", color=discord.Color.red())
            embed.description = f"LLM '{name}' not found in this guild."
            await interaction.followup.send(embed=embed)
            return
        embed = Embed(title=f"Configuration for {llm.name}", color=discord.Color.blue())
        embed.add_field(name="API Base", value=llm.api_base, inline=False)
        embed.add_field(name="LLM Name", value=llm.llm_name, inline=False)
        embed.add_field(name="Max Tokens", value=str(llm.max_tokens), inline=True)
        embed.add_field(
            name="Context Length", value=str(llm.context_length), inline=True
        )
        embed.add_field(name="Message Limit", value=str(llm.message_limit), inline=True)
        embed.add_field(name="Temperature", value=str(llm.temperature), inline=True)
        embed.add_field(
            name="Top P",
            value=str(llm.top_p) if llm.top_p is not None else "N/A",
            inline=True,
        )
        embed.add_field(
            name="Top K",
            value=str(llm.top_k) if llm.top_k is not None else "N/A",
            inline=True,
        )
        embed.add_field(
            name="Frequency Penalty",
            value=(
                str(llm.frequency_penalty)
                if llm.frequency_penalty is not None
                else "N/A"
            ),
            inline=True,
        )
        embed.add_field(
            name="Presence Penalty",
            value=(
                str(llm.presence_penalty) if llm.presence_penalty is not None else "N/A"
            ),
            inline=True,
        )
        embed.add_field(
            name="Repetition Penalty",
            value=(
                str(llm.repetition_penalty)
                if llm.repetition_penalty is not None
                else "N/A"
            ),
            inline=True,
        )
        embed.add_field(
            name="Min P",
            value=str(llm.min_p) if llm.min_p is not None else "N/A",
            inline=True,
        )
        embed.add_field(
            name="Top A",
            value=str(llm.top_a) if llm.top_a is not None else "N/A",
            inline=True,
        )
        embed.add_field(
            name="System Prompt", value=llm.system_prompt or "N/A", inline=False
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(description="Get help on bot commands and LLM interaction")
    async def help(self, interaction: discord.Interaction):
        """Provide help information about bot commands and LLM interaction"""
        embed = Embed(title="LLM Bot Help", color=discord.Color.blue())

        # General description
        embed.description = "This bot allows you to interact with various Language Models (LLMs) through Discord. Here's how to use it:"

        # Commands section
        embed.add_field(
            name="Commands",
            value=dedent(
                """
        `/llm list`: List all available LLMs
        `/llm create`: Register a new LLM (Admin only)
        `/llm modify`: Modify an existing LLM (Admin only)
        `/llm delete`: Delete an existing LLM (Admin only)
        `/llm copy`: Create a copy of an existing LLM (Admin only)
        `/llm set_avatar`: Set an avatar for an LLM (Admin only)
        `/llm print`: Print the configuration of an LLM
        `/llm sync`: Sync bot commands with the current guild (Admin only)
        `/llm help`: Show this help message
        """
            ),
            inline=False,
        )

        # LLM Interaction section
        embed.add_field(
            name="Interacting with LLMs",
            value=dedent(
                """
        To interact with an LLM, simply mention it in your message:
        `@LLM_Name Your message here`

        The LLM will then respond to your message in the channel.
        You can have conversations by continuing to mention the LLM in your replies.
        You can also trigger a response by replying to a message sent by the LLM.
        """
            ),
            inline=False,
        )

        # Tips section
        embed.add_field(
            name="Tips",
            value=dedent(
                """
        - Each LLM has its own personality and capabilities based on its configuration.
        - You can use the `/llm print` command to view an LLM's configuration.
        - Administrators can manage LLMs using the create, modify, delete, and copy commands.
        - If you're unsure which LLMs are available, use the `/llm list` command.
        """
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)
