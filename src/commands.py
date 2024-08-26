from typing import Annotated, Optional
import discord
from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.bot import DiscordBot
from src.db.engine import Session
from src.db.models import LanguageModel

class LLMParams(BaseModel):
    api_base: Optional[str] = Field(None, description="API base URL")
    model_name: Optional[str] = Field(None, description="Name of the model")
    max_tokens: Optional[int] = Field(None, description="Maximum number of tokens")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    context_length: Optional[int] = Field(None, description="Context length")
    message_limit: Optional[int] = Field(None, description="Message limit")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature (default is 1.0)")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top P value")
    top_k: Optional[int] = Field(None, ge=0, description="Top K value")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Presence penalty")
    repetition_penalty: Optional[float] = Field(None, ge=0.0, description="Repetition penalty")
    min_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum P value")
    top_a: Optional[float] = Field(None, ge=0.0, description="Top A value")

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
    async def create(self, interaction: discord.Interaction, name: str, **kwargs: Annotated[LLMParams, discord.app_commands.Transformer]):
        """Create a new LLM handler"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            llm_params = LLMParams(**kwargs)
        except ValueError as e:
            await interaction.followup.send(f"Invalid parameters: {str(e)}")
            return

        model_data = llm_params.dict(exclude_unset=True)
        model_data['name'] = name

        # Prompt for required fields that weren't provided
        for field in LanguageModel.__table__.columns:
            if field.name not in model_data and not field.nullable and field.name != 'id':
                if field.name == 'api_key':
                    await interaction.followup.send("Please enter the API key for this LLM handler (your response will be deleted immediately):")
                    api_key_message = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
                    await api_key_message.delete()
                    model_data[field.name] = api_key_message.content
                else:
                    await interaction.followup.send(f"Enter {field.name}:")
                    response = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
                    model_data[field.name] = response.content

        new_model = LanguageModel(**model_data)

        try:
            await self.bot.add_llm_handler(new_model)
            await interaction.followup.send(f"LLM handler '{name}' created successfully!")
        except ValueError as e:
            await interaction.followup.send(f"Error creating LLM handler: {str(e)}")

    @app_commands.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(name="Name of the LLM handler to modify")
    async def modify(
        self,
        interaction: discord.Interaction,
        name: str,
        **kwargs: Annotated[LLMParams, discord.app_commands.Transformer]
    ):
        await interaction.response.defer(ephemeral=True)

        model = await self._get_model_by_name(name)
        if not model:
            await interaction.followup.send(f"LLM handler '{name}' not found.")
            return

        try:
            llm_params = LLMParams(**kwargs)
        except ValueError as e:
            await interaction.followup.send(f"Invalid parameters: {str(e)}")
            return

        update_data = llm_params.dict(exclude_unset=True)

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

# Dynamically add options to create and modify commands
for command in [LLMCommands.create, LLMCommands.modify]:
    for field, info in LLMParams.__fields__.items():
        command.add_option(
            discord.app_commands.Option(
                name=field,
                description=info.field_info.description or field.replace('_', ' ').capitalize(),
                type=discord.AppCommandOptionType.string,  # Adjust based on field type if needed
                required=False
            )
        )

async def setup(bot: DiscordBot):
    await bot.add_cog(LLMCommands(bot))
