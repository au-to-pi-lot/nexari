import discord
from discord.ext.commands import Bot

intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = Bot(command_prefix="!", intents=intents)

