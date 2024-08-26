from typing import Annotated, Optional, Dict, Any, Type
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
        model_data = {k: v for k, v in model_data.items() if v is not None}

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

from typing import get_origin, get_args, Union

def get_app_command_option_type(field_type: Type[Any]) -> discord.AppCommandOptionType:
    # Handle Optional types
    if get_origin(field_type) is Union:
        args = get_args(field_type)
        if len(args) == 2 and type(None) in args:
            # This is an Optional type, so we'll use the non-None type
            field_type = next(arg for arg in args if arg is not type(None))

    if field_type == str:
        return discord.AppCommandOptionType.string
    elif field_type == int:
        return discord.AppCommandOptionType.integer
    elif field_type == float:
        return discord.AppCommandOptionType.number
    elif field_type == bool:
        return discord.AppCommandOptionType.boolean
    else:
        return discord.AppCommandOptionType.string  # Default to string for unknown types

# Dynamically add options to the modify command
for field, info in LLMParams.model_fields.items():
    option_type = get_app_command_option_type(info.annotation)
    LLMCommands.modify.add_option(
        discord.app_commands.Option(
            name=field,
            description=info.field_info.description or field.replace('_', ' ').capitalize(),
            type=option_type,
            required=False
        )
    )

# The create command options are now explicitly defined in the method signature

async def setup(bot: DiscordBot):
    await bot.add_cog(LLMCommands(bot))
