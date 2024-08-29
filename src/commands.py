from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from src.bot import DiscordBot
from src.db.engine import Session
from src.db.models import LLM
from src.db.models.llm import LLMCreate, LLMUpdate


class LLMCommands(commands.GroupCog, name="llm"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot
        super().__init__()

    async def _get_model_by_name(self, name: str) -> Optional[LLM]:
        async with Session() as session:
            result = await session.execute(select(LLM).where(LLM.name == name))
            return result.scalar_one_or_none()

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def list(self, interaction: discord.Interaction):
        """List all available LLM handlers"""
        handlers = await self.bot.get_llm_handlers()
        if handlers:
            await interaction.response.send_message(f"Available LLM handlers: {', '.join((handler.language_model.name for handler in handlers))}")
        else:
            await interaction.response.send_message("No LLM handlers available.")

    @app_commands.command(description="Register a new LLM")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="Name of the new LLM handler",
        api_base="API base URL",
        llm_name="Name of the model",
        api_key="API key for the LLM",
        max_tokens="Maximum number of tokens",
        system_prompt="System prompt",
        context_length="Context length",
        message_limit="Message limit",
        temperature="Temperature (default is 1.0)",
        top_p="Top P value",
        top_k="Top K value",
        frequency_penalty="Frequency penalty",
        presence_penalty="Presence penalty",
        repetition_penalty="Repetition penalty",
        min_p="Minimum P value",
        top_a="Top A value"
    )
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        api_base: str,
        llm_name: str,
        api_key: str,
        max_tokens: int,
        system_prompt: str,
        context_length: int,
        message_limit: int,
        temperature: float = 1.0,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        min_p: Optional[float] = None,
        top_a: Optional[float] = None
    ):
        """Create a new LLM handler"""
        await interaction.response.defer(ephemeral=True)
        
        model_data = LLMCreate(
            name=name,
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
            top_a=top_a
        )

        try:
            await self.bot.add_llm_handler(model_data)
            await interaction.followup.send(f"LLM handler '{name}' created successfully!")
        except ValueError as e:
            await interaction.followup.send(f"Error creating LLM handler: {str(e)}")

    @app_commands.command(description="Modify an existing LLM handler")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="Name of the LLM handler to modify",
        new_name="New name for the LLM handler",
        api_base="API base URL",
        llm_name="Name of the model",
        max_tokens="Maximum number of tokens",
        system_prompt="System prompt",
        context_length="Context length",
        message_limit="Message limit",
        temperature="Temperature (default is 1.0)",
        top_p="Top P value",
        top_k="Top K value",
        frequency_penalty="Frequency penalty",
        presence_penalty="Presence penalty",
        repetition_penalty="Repetition penalty",
        min_p="Minimum P value",
        top_a="Top A value"
    )
    async def modify(
        self,
        interaction: discord.Interaction,
        name: str,
        new_name: Optional[str] = None,
        api_base: Optional[str] = None,
        llm_name: Optional[str] = None,
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
        top_a: Optional[float] = None
    ):
        await interaction.response.defer(ephemeral=True)

        model = await self._get_model_by_name(name)
        if not model:
            await interaction.followup.send(f"LLM handler '{name}' not found.")
            return

        update_data = LLMUpdate(
            name=new_name,
            api_base=api_base,
            llm_name=llm_name,
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
            top_a=top_a
        )

        try:
            await self.bot.modify_llm_handler(model.id, update_data)
            await interaction.followup.send(f"LLM handler '{name}' modified successfully!")
        except ValueError as e:
            await interaction.followup.send(f"Error modifying LLM handler: {str(e)}")

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, name: str):
        """Delete an existing LLM handler"""
        handler = await self.bot.get_handler(name)
        if not handler:
            await interaction.response.send_message(f"LLM handler '{name}' not found.")
            return

        try:
            await self.bot.remove_llm_handler(handler.language_model)
            await interaction.response.send_message(f"LLM handler '{name}' deleted successfully!")
        except ValueError as e:
            await interaction.response.send_message(f"Error deleting LLM handler: {str(e)}")

    @app_commands.command(description="Create a deep copy of an existing LLM handler with a new name")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        source_name="Name of the existing LLM handler to copy",
        new_name="Name for the new copy of the LLM handler"
    )
    async def copy(self, interaction: discord.Interaction, source_name: str, new_name: str):
        """Create a deep copy of an existing LLM handler with a new name"""
        await interaction.response.defer(ephemeral=True)

        source_handler = await self.bot.get_handler(source_name)
        if not source_handler:
            await interaction.followup.send(f"Source LLM handler '{source_name}' not found.")
            return

        existing_handler = await self.bot.get_handler(new_name)
        if existing_handler:
            await interaction.followup.send(f"An LLM handler with the name '{new_name}' already exists.")
            return

        source_model = source_handler.language_model

        # Create a new LLM instance with the same attributes as the source
        new_model_data = LLMCreate(
            name=new_name,
            api_base=source_model.api_base,
            llm_name=source_model.llm_name,
            api_key=source_model.api_key,
            max_tokens=source_model.max_tokens,
            system_prompt=source_model.system_prompt,
            context_length=source_model.context_length,
            message_limit=source_model.message_limit,
            temperature=source_model.temperature,
            top_p=source_model.top_p,
            top_k=source_model.top_k,
            frequency_penalty=source_model.frequency_penalty,
            presence_penalty=source_model.presence_penalty,
            repetition_penalty=source_model.repetition_penalty,
            min_p=source_model.min_p,
            top_a=source_model.top_a
        )

        try:
            await self.bot.add_llm_handler(new_model_data)
            await interaction.followup.send(f"LLM handler '{source_name}' successfully copied to '{new_name}'!")
        except ValueError as e:
            await interaction.followup.send(f"Error creating copy of LLM handler: {str(e)}")

async def setup(bot: DiscordBot):
    await bot.add_cog(LLMCommands(bot))
