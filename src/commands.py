from typing import Annotated, Optional, Dict, Any, Type
import discord
from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.bot import DiscordBot
from src.db.engine import Session
from src.db.models import LanguageModel

class LLMCommands(commands.GroupCog, name="llm"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot
        super().__init__()

    async def _get_model_by_name(self, name: str) -> Optional[LanguageModel]:
        async with Session() as session:
            result = await session.execute(select(LanguageModel).where(LanguageModel.name == name))
            return result.scalar_one_or_none()

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def list(self, interaction: discord.Interaction):
        """List all available LLM handlers"""
        handlers = list(self.bot.llm_handlers.keys())
        if handlers:
            await interaction.response.send_message(f"Available LLM handlers: {', '.join(handlers)}")
        else:
            await interaction.response.send_message("No LLM handlers available.")

    @app_commands.command(description="Register a new LLM")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="Name of the new LLM handler",
        api_base="API base URL",
        model_name="Name of the model",
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
        model_name: str,
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
        
        model_data = {
            'name': name,
            'api_base': api_base,
            'model_name': model_name,
            'api_key': api_key,
            'max_tokens': max_tokens,
            'system_prompt': system_prompt,
            'context_length': context_length,
            'message_limit': message_limit,
            'temperature': temperature,
            'top_p': top_p,
            'top_k': top_k,
            'frequency_penalty': frequency_penalty,
            'presence_penalty': presence_penalty,
            'repetition_penalty': repetition_penalty,
            'min_p': min_p,
            'top_a': top_a
        }

        try:
            new_model = LanguageModel(**model_data)
            await self.bot.add_llm_handler(new_model)
            await interaction.followup.send(f"LLM handler '{name}' created successfully!")
        except ValueError as e:
            await interaction.followup.send(f"Error creating LLM handler: {str(e)}")

    @app_commands.command(description="Modify an existing LLM handler")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="Name of the LLM handler to modify",
        api_base="API base URL",
        model_name="Name of the model",
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
        api_base: str = None,
        model_name: str = None,
        max_tokens: int = None,
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

        update_data = {
            'api_base': api_base,
            'model_name': model_name,
            'max_tokens': max_tokens,
            'system_prompt': system_prompt,
            'context_length': context_length,
            'message_limit': message_limit,
            'temperature': temperature,
            'top_p': top_p,
            'top_k': top_k,
            'frequency_penalty': frequency_penalty,
            'presence_penalty': presence_penalty,
            'repetition_penalty': repetition_penalty,
            'min_p': min_p,
            'top_a': top_a
        }
        
        update_data = {k: v for k, v in update_data.items() if v is not None}

        for key, value in update_data.items():
            setattr(model, key, value)

        try:
            await self.bot.modify_llm_handler(model)
            await interaction.followup.send(f"LLM handler '{name}' modified successfully!")
        except ValueError as e:
            await interaction.followup.send(f"Error modifying LLM handler: {str(e)}")

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, name: str):
        """Delete an existing LLM handler"""
        if name not in self.bot.llm_handlers:
            await interaction.response.send_message(f"LLM handler '{name}' not found.")
            return

        try:
            await self.bot.remove_llm_handler(self.bot.llm_handlers[name].language_model)
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

        if source_name not in self.bot.llm_handlers:
            await interaction.followup.send(f"Source LLM handler '{source_name}' not found.")
            return

        if new_name in self.bot.llm_handlers:
            await interaction.followup.send(f"An LLM handler with the name '{new_name}' already exists.")
            return

        source_model = self.bot.llm_handlers[source_name].language_model

        # Create a new LanguageModel instance with the same attributes as the source
        new_model_data = {
            'name': new_name,
            'api_base': source_model.api_base,
            'model_name': source_model.model_name,
            'api_key': source_model.api_key,
            'max_tokens': source_model.max_tokens,
            'system_prompt': source_model.system_prompt,
            'context_length': source_model.context_length,
            'message_limit': source_model.message_limit,
            'temperature': source_model.temperature,
            'top_p': source_model.top_p,
            'top_k': source_model.top_k,
            'frequency_penalty': source_model.frequency_penalty,
            'presence_penalty': source_model.presence_penalty,
            'repetition_penalty': source_model.repetition_penalty,
            'min_p': source_model.min_p,
            'top_a': source_model.top_a
        }

        new_model = LanguageModel(**new_model_data)

        try:
            await self.bot.add_llm_handler(new_model)
            await interaction.followup.send(f"LLM handler '{source_name}' successfully copied to '{new_name}'!")
        except ValueError as e:
            await interaction.followup.send(f"Error creating copy of LLM handler: {str(e)}")

async def setup(bot: DiscordBot):
    await bot.add_cog(LLMCommands(bot))
