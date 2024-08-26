from typing import Optional, Dict, Any
import inspect
import discord
from discord import app_commands
from discord.ext import commands

from src.bot import DiscordBot
from src.db.models import LanguageModel
from src.config import Config

class LLMCommands(commands.GroupCog, name="llm"):
    def __init__(self, bot: DiscordBot):
        self.bot = bot
        super().__init__()

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def list(self, interaction: discord.Interaction):
        """List all available LLM handlers"""
        handlers = list(self.bot.llm_handlers.keys())
        if handlers:
            await interaction.response.send_message(f"Available LLM handlers: {', '.join(handlers)}")
        else:
            await interaction.response.send_message("No LLM handlers available.")

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="Name of the LLM handler",
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
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
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
        """Create a new LLM handler"""
        await interaction.response.defer(ephemeral=True)
        
        model_fields = inspect.signature(LanguageModel).parameters
        model_data = {
            'name': name,
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

        # Prompt for required fields that weren't provided
        for field, param in model_fields.items():
            if field == 'id':
                continue
            if model_data[field] is None and param.default == param.empty:
                if field == 'api_key':
                    await interaction.followup.send("Please enter the API key for this LLM handler (your response will be deleted immediately):")
                    api_key_message = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
                    await api_key_message.delete()
                    model_data[field] = api_key_message.content
                else:
                    await interaction.followup.send(f"Enter {field}:")
                    response = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
                    
                    if param.annotation == int:
                        model_data[field] = int(response.content)
                    elif param.annotation == float:
                        model_data[field] = float(response.content)
                    else:
                        model_data[field] = response.content

        new_model = LanguageModel(**model_data)

        try:
            await self.bot.add_llm_handler(new_model)
            await interaction.followup.send(f"LLM handler '{name}' created successfully!")
        except ValueError as e:
            await interaction.followup.send(f"Error creating LLM handler: {str(e)}")

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        name="Name of the LLM handler to modify",
        api_base="API base URL",
        model_name="Name of the model",
        max_tokens="Maximum number of tokens",
        system_prompt="System prompt",
        context_length="Context length",
        message_limit="Message limit",
        temperature="Temperature",
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
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
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
        """Modify an existing LLM handler"""
        await interaction.response.defer(ephemeral=True)

        if name not in self.bot.llm_handlers:
            await interaction.followup.send(f"LLM handler '{name}' not found.")
            return

        current_model = self.bot.llm_handlers[name].language_model
        update_data = {
            k: v for k, v in locals().items()
            if k not in ['self', 'interaction', 'name'] and v is not None
        }

        # Prompt for API key if it needs to be changed
        if 'api_key' in update_data:
            await interaction.followup.send("Please enter the new API key (your response will be deleted immediately):")
            api_key_message = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
            await api_key_message.delete()
            update_data['api_key'] = api_key_message.content

        for key, value in update_data.items():
            setattr(current_model, key, value)

        try:
            await self.bot.modify_llm_handler(current_model)
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

async def setup(bot: DiscordBot):
    await bot.add_cog(LLMCommands(bot))
