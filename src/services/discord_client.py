import discord
from discord.ext.commands import Bot

from src.services import registry

intents: discord.Intents = discord.Intents.default()
intents.message_content = True

registry.register_factory(
    svc_type=Bot,
    factory=lambda: Bot(command_prefix="!", intents=intents)
)
