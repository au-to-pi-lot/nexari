from typing import Optional
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
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        api_base: str,
        model_name: str,
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
        
        # Request API key separately for security
        await interaction.followup.send("Please enter the API key for this LLM handler (your response will be deleted immediately):")
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        
        api_key_message = await self.bot.wait_for('message', check=check)
        await api_key_message.delete()
        
        api_key = api_key_message.content

        new_model = LanguageModel(
            name=name,
            api_base=api_base,
            model_name=model_name,
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
            await self.bot.add_llm_handler(new_model)
            await interaction.followup.send(f"LLM handler '{name}' created successfully!")
        except ValueError as e:
            await interaction.followup.send(f"Error creating LLM handler: {str(e)}")

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
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

        # Update fields if provided
        update_dict = {
            k: v for k, v in locals().items()
            if k not in ['self', 'interaction', 'name'] and v is not None
        }

        for key, value in update_dict.items():
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
