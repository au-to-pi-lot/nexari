import discord
from discord.ext.commands import Bot

from src.services import registry

intents: discord.Intents = discord.Intents.default()
intents.message_content = True

bot = Bot(command_prefix="!", intents=intents)
registry.register_factory(
    svc_type=Bot,
    factory=lambda: bot
)
