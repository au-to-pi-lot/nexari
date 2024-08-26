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
    async def create(self, interaction: discord.Interaction, name: str):
        """Create a new LLM handler"""
        await interaction.response.defer(ephemeral=True)
        
        model_fields = inspect.signature(LanguageModel).parameters
        field_prompts = {
            'api_key': "Please enter the API key for this LLM handler (your response will be deleted immediately):",
            'api_base': "Enter the API base URL:",
            'model_name': "Enter the model name:",
            'max_tokens': "Enter the maximum number of tokens:",
            'system_prompt': "Enter the system prompt:",
            'context_length': "Enter the context length:",
            'message_limit': "Enter the message limit:",
            'temperature': "Enter the temperature (default is 1.0):",
        }

        model_data = {'name': name}

        for field, param in model_fields.items():
            if field == 'id' or field == 'name':
                continue

            if field == 'api_key':
                await interaction.followup.send(field_prompts[field])
                api_key_message = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
                await api_key_message.delete()
                model_data[field] = api_key_message.content
            else:
                prompt = field_prompts.get(field, f"Enter the value for {field}:")
                await interaction.followup.send(prompt)
                response = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
                
                if param.annotation == int:
                    model_data[field] = int(response.content)
                elif param.annotation == float:
                    model_data[field] = float(response.content)
                elif param.annotation == Optional[float]:
                    model_data[field] = float(response.content) if response.content.lower() != 'none' else None
                elif param.annotation == Optional[int]:
                    model_data[field] = int(response.content) if response.content.lower() != 'none' else None
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
    async def modify(self, interaction: discord.Interaction, name: str):
        """Modify an existing LLM handler"""
        await interaction.response.defer(ephemeral=True)

        if name not in self.bot.llm_handlers:
            await interaction.followup.send(f"LLM handler '{name}' not found.")
            return

        current_model = self.bot.llm_handlers[name].language_model
        model_fields = inspect.signature(LanguageModel).parameters

        update_data: Dict[str, Any] = {}

        for field, param in model_fields.items():
            if field in ['id', 'name']:
                continue

            current_value = getattr(current_model, field)
            await interaction.followup.send(f"Current value of {field}: {current_value}\nEnter new value or 'skip' to keep current:")
            response = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)

            if response.content.lower() != 'skip':
                if param.annotation == int:
                    update_data[field] = int(response.content)
                elif param.annotation == float:
                    update_data[field] = float(response.content)
                elif param.annotation == Optional[float]:
                    update_data[field] = float(response.content) if response.content.lower() != 'none' else None
                elif param.annotation == Optional[int]:
                    update_data[field] = int(response.content) if response.content.lower() != 'none' else None
                else:
                    update_data[field] = response.content

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
